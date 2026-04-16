"""Shared admin-only guard — used by identity management routes.

Clients pass `X-Admin-Token: <token>`; the server compares it against
`AWAITHUMANS_ADMIN_API_TOKEN` in constant time. When the env is unset,
all admin routes return 503 (feature explicitly disabled).

This is a pragmatic v1 gate. Multi-user auth with per-user roles is
future work; today an operator generates one token and shares it with
whoever needs to manage identities.
"""

from __future__ import annotations

import hmac
import logging

from fastapi import Header, HTTPException

from awaithumans.server.core.config import settings

logger = logging.getLogger("awaithumans.server.core.admin_auth")


async def require_admin(
    x_admin_token: str | None = Header(default=None, alias="X-Admin-Token"),
) -> None:
    """FastAPI dependency — raise 403/503 if the caller isn't an admin."""
    if not settings.ADMIN_API_TOKEN:
        raise HTTPException(
            status_code=503,
            detail=(
                "Admin endpoints are disabled. Set AWAITHUMANS_ADMIN_API_TOKEN "
                "to a high-entropy value (e.g. `python -c 'import secrets; "
                "print(secrets.token_urlsafe(32))'`)."
            ),
        )
    if not x_admin_token or not hmac.compare_digest(
        x_admin_token, settings.ADMIN_API_TOKEN
    ):
        raise HTTPException(status_code=403, detail="Admin token required.")
