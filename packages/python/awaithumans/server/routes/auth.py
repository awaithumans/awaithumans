"""Dashboard auth routes — login, logout, session introspection.

Public endpoints (these are what the rest of the API needs to be auth'd):

    POST   /api/auth/login     { email, password }     → 204 + cookie
    POST   /api/auth/logout                             → 204 + clear cookie
    GET    /api/auth/me                                 → { authenticated, user }

No `auth_enabled: false` path anymore — auth is always on in v1. The
dashboard uses `/api/setup/status` to distinguish first-run (show the
`/setup` wizard) from normal (show the login form).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.server.core.auth import (
    InvalidSessionError,
    sign_session,
    verify_session,
)
from awaithumans.server.core.config import settings
from awaithumans.server.core.password import dummy_verify, verify_password
from awaithumans.server.db.connection import get_session
from awaithumans.server.schemas.auth import LoginRequest, MeResponse
from awaithumans.server.services.user_service import get_user, get_user_by_email
from awaithumans.utils.constants import (
    DASHBOARD_SESSION_COOKIE_NAME,
    DASHBOARD_SESSION_MAX_AGE_SECONDS,
)

router = APIRouter(prefix="/auth", tags=["auth"])
logger = logging.getLogger("awaithumans.server.routes.auth")


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
async def login(
    body: LoginRequest,
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Verify credentials against the user directory and set a signed
    session cookie.

    Returns 401 for unknown email, inactive account, no password set,
    or wrong password — uniform error so we don't leak which field
    was wrong.
    """
    user = await get_user_by_email(session, body.email)
    reject = HTTPException(status_code=401, detail="Invalid credentials.")

    # Timing equalization: without this, the unknown-user path skips
    # argon2 and returns ~100ms faster than the known-user path,
    # letting an attacker probe for registered emails. Burn the same
    # CPU budget either way.
    if user is None or not user.active or not user.password_hash:
        dummy_verify(body.password)
        logger.info("Failed login (no match / inactive / no password): %s", body.email)
        raise reject

    if not verify_password(body.password, user.password_hash):
        logger.info("Failed login (wrong password): %s", body.email)
        raise reject

    token = sign_session(user_id=user.id, is_operator=user.is_operator)
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
async def me(
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> MeResponse:
    """Session introspection. Returns the current user record when
    signed in, or `authenticated=false` otherwise. Dashboard mounts
    call this to decide whether to render the queue or the login form."""
    cookie = request.cookies.get(DASHBOARD_SESSION_COOKIE_NAME)
    if not cookie:
        return MeResponse(authenticated=False)

    try:
        claims = verify_session(cookie)
    except InvalidSessionError:
        return MeResponse(authenticated=False)

    # Fresh read — if the user was deleted or deactivated, treat as
    # logged out. The cookie's `is_operator` claim is overridden by
    # the current DB value to keep role changes snappy.
    user = await get_user(session, claims.user_id)
    if user is None or not user.active:
        return MeResponse(authenticated=False)

    return MeResponse(
        authenticated=True,
        user_id=user.id,
        email=user.email,
        display_name=user.display_name,
        is_operator=user.is_operator,
    )
