"""Admin-only guard — accepts either an operator session OR the
admin bearer token.

Operators (logged-in users with `is_operator=True`) get dashboard
access automatically. Automation (CI, ops scripts, migration tools)
uses the `X-Admin-Token` bearer header. Either proves admin intent;
the route doesn't care which.

When both `ADMIN_API_TOKEN` is unset AND the caller has no operator
session, the route returns 403 (standard forbidden, not 503 —
operators can still reach it via the dashboard login).
"""

from __future__ import annotations

import hmac
import logging

from fastapi import HTTPException, Request

from awaithumans.server.core.auth import SessionClaims
from awaithumans.server.core.config import settings

logger = logging.getLogger("awaithumans.server.core.admin_auth")


def _has_valid_admin_token(request: Request, header_value: str | None) -> bool:
    """Accept both `X-Admin-Token: <token>` (legacy) and
    `Authorization: Bearer <token>` (more standard). The dashboard
    middleware already stripped the bearer form when `Bearer` matched
    the admin token — in that case `request.state.auth_admin_token`
    is set and we trust it."""
    if getattr(request.state, "auth_admin_token", False):
        return True
    if not settings.ADMIN_API_TOKEN:
        return False
    if not header_value:
        return False
    return hmac.compare_digest(header_value, settings.ADMIN_API_TOKEN)


def _is_operator_session(request: Request) -> bool:
    claims = getattr(request.state, "auth_claims", None)
    return isinstance(claims, SessionClaims) and claims.is_operator


async def require_admin(request: Request) -> None:
    """FastAPI dependency — raise 403 if the caller isn't an operator
    (by session) or an admin-token holder (by bearer header)."""
    header_value = request.headers.get("x-admin-token")
    if _has_valid_admin_token(request, header_value):
        return
    if _is_operator_session(request):
        return
    raise HTTPException(status_code=403, detail="Admin access required.")
