"""Dashboard auth routes — login, logout, session introspection.

Public endpoints (auth is what these routes bootstrap):

    POST   /api/auth/login     { user, password }  → 204 + cookie
    POST   /api/auth/logout                         → 204 + clear cookie
    GET    /api/auth/me                             → { user, authenticated }

If `AWAITHUMANS_DASHBOARD_PASSWORD` is unset, login returns 503 —
server is in no-auth mode, logging in would be meaningless. /me
returns `{ authenticated: false }` so the dashboard can render a
"no auth required" banner rather than a login page.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from awaithumans.server.core.auth import (
    InvalidSessionError,
    sign_session,
    verify_password,
    verify_session,
)
from awaithumans.server.core.config import settings
from awaithumans.utils.constants import (
    DASHBOARD_SESSION_COOKIE_NAME,
    DASHBOARD_SESSION_MAX_AGE_SECONDS,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("awaithumans.server.routes.auth")


class LoginRequest(BaseModel):
    user: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class MeResponse(BaseModel):
    authenticated: bool
    user: str | None = None
    # True when the operator has left the dashboard in no-auth mode
    # (no DASHBOARD_PASSWORD). The dashboard shows a "running behind
    # proxy — no password required" banner instead of a login form.
    auth_enabled: bool


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
async def login(body: LoginRequest, response: Response) -> Response:
    """Verify credentials and set a signed session cookie."""
    if not settings.DASHBOARD_PASSWORD:
        raise HTTPException(
            status_code=503,
            detail=(
                "Dashboard auth is not configured. "
                "Set AWAITHUMANS_DASHBOARD_PASSWORD to enable login."
            ),
        )

    if not verify_password(user=body.user, password=body.password):
        # Log at info, not warning — brute-forcers will spam this.
        logger.info("Failed login attempt for user=%s", body.user)
        raise HTTPException(status_code=401, detail="Invalid credentials.")

    token = sign_session(user=body.user)
    response.set_cookie(
        key=DASHBOARD_SESSION_COOKIE_NAME,
        value=token,
        max_age=DASHBOARD_SESSION_MAX_AGE_SECONDS,
        httponly=True,
        secure=settings.PUBLIC_URL.startswith("https://"),
        samesite="lax",
        path="/",
    )
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(response: Response) -> Response:
    response.delete_cookie(DASHBOARD_SESSION_COOKIE_NAME, path="/")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/me", response_model=MeResponse)
async def me(request: Request) -> MeResponse:
    """Session introspection. Dashboard calls this on mount to decide
    whether to render the login page or the task queue."""
    auth_enabled = bool(settings.DASHBOARD_PASSWORD)
    if not auth_enabled:
        return MeResponse(authenticated=False, auth_enabled=False)

    cookie = request.cookies.get(DASHBOARD_SESSION_COOKIE_NAME)
    if not cookie:
        return MeResponse(authenticated=False, auth_enabled=True)

    try:
        user = verify_session(cookie)
    except InvalidSessionError:
        return MeResponse(authenticated=False, auth_enabled=True)

    return MeResponse(authenticated=True, user=user, auth_enabled=True)
