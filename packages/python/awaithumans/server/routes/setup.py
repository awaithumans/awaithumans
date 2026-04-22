"""First-run setup routes — publicly reachable (gates itself on token).

The middleware leaves `/api/setup/*` in the public prefix list so a
brand-new server with zero users can be set up without an admin
token. Authorization here is the single-shot in-memory bootstrap
token (see `core/bootstrap.py`).

    GET  /api/setup/status                       → is setup needed?
    POST /api/setup/operator   { token, email,   → create first operator
                                  password, name }

`/api/setup/operator` is a one-shot — subsequent calls (even with a
fresh token after a restart-before-completion) return 409 once any
user exists in the DB.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.server.core import bootstrap
from awaithumans.server.core.auth import sign_session
from awaithumans.server.core.config import settings
from awaithumans.server.db.connection import get_session
from awaithumans.server.services.user_service import count_users, create_user
from awaithumans.utils.constants import (
    DASHBOARD_SESSION_COOKIE_NAME,
    DASHBOARD_SESSION_MAX_AGE_SECONDS,
)

router = APIRouter(prefix="/setup", tags=["setup"])
logger = logging.getLogger("awaithumans.server.routes.setup")


class SetupStatusResponse(BaseModel):
    """Tells the dashboard which landing page to show."""

    needs_setup: bool
    # `token_active` is true only on the server's own loopback — the
    # actual token is never returned; operators read it from the server
    # log. This field just lets the /setup page show a "server is
    # ready, paste your token" state vs. "setup already done" state.
    token_active: bool


class CreateOperatorRequest(BaseModel):
    token: str = Field(min_length=1)
    email: str = Field(min_length=1, max_length=320)
    password: str = Field(min_length=8)
    display_name: str | None = None


@router.get("/status", response_model=SetupStatusResponse)
async def setup_status(
    session: AsyncSession = Depends(get_session),
) -> SetupStatusResponse:
    user_count = await count_users(session)
    return SetupStatusResponse(
        needs_setup=user_count == 0,
        token_active=bootstrap.is_active() and user_count == 0,
    )


@router.post(
    "/operator",
    status_code=status.HTTP_201_CREATED,
)
async def create_first_operator(
    body: CreateOperatorRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> dict[str, str]:
    """Create the first operator and issue their session in one shot.

    The dashboard posts here after the operator pastes the setup token
    and their desired credentials. On success, the response sets the
    session cookie so the operator lands directly on the queue —
    no redundant login step.
    """
    # Re-check on the DB rather than only trusting the bootstrap flag:
    # two concurrent /setup posts could both see `_completed=False`
    # before the row commits. The user service's unique constraints
    # back-stop that, but this check catches the common case with a
    # cleaner error.
    if await count_users(session) > 0:
        bootstrap.mark_complete()
        raise HTTPException(
            status_code=409,
            detail="Setup has already been completed. Use /api/auth/login.",
        )

    if not bootstrap.verify_token(body.token):
        logger.info("Rejected setup token (mismatch or already completed)")
        raise HTTPException(status_code=403, detail="Invalid setup token.")

    user = await create_user(
        session,
        email=body.email,
        display_name=body.display_name,
        is_operator=True,
        password=body.password,
    )
    bootstrap.mark_complete()
    logger.info("First-run setup complete: operator=%s (%s)", user.id, user.email)

    # Sign them in immediately.
    token = sign_session(user_id=user.id, is_operator=True)
    response.set_cookie(
        key=DASHBOARD_SESSION_COOKIE_NAME,
        value=token,
        max_age=DASHBOARD_SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.PUBLIC_URL.startswith("https://"),
        samesite="lax",
        path="/",
    )
    return {"user_id": user.id, "email": user.email or ""}
