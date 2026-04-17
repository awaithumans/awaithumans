"""Dashboard password auth — optional HMAC session cookies.

Turned on by setting `AWAITHUMANS_DASHBOARD_PASSWORD`. When unset the
middleware is a no-op and every route is public (operator is responsible
for fronting the server with their own auth proxy).

Wire format: `cookie = base64url(hmac(body) || body)` where
`body = json({u: user, e: expiry_unix})` — same shape as the email
magic-link tokens. The HMAC key is HKDF-derived from PAYLOAD_KEY with
a channel-scoped salt, so the same root key never signs two primitives.

The middleware enforces auth before routes run:
- public paths (`/api/auth/*`, `/api/health`, static assets) skip the check
- a valid `Authorization: Bearer <ADMIN_API_TOKEN>` acts as a skeleton key
  (lets ops + the admin identity CRUD work without a session)
- otherwise a valid session cookie is required, else 401
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import time
from typing import Any

from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from fastapi import HTTPException, Request, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from awaithumans.server.core.config import settings
from awaithumans.server.core.encryption import get_key
from awaithumans.utils.constants import (
    DASHBOARD_SESSION_COOKIE_NAME,
    DASHBOARD_SESSION_HKDF_INFO,
    DASHBOARD_SESSION_HKDF_SALT,
    DASHBOARD_SESSION_MAX_AGE_SECONDS,
    HMAC_SHA256_DIGEST_BYTES,
)

logger = logging.getLogger("awaithumans.server.core.auth")


# Paths that stay public even when auth is on. Auth routes (so the
# login page can reach them), health probes, and the OAuth install
# callbacks (signed by Slack, not us).
_PUBLIC_PREFIXES = (
    "/api/auth/",
    "/api/health",
    "/api/channels/slack/oauth/",   # Slack-signed state already gates these
    "/api/channels/email/action/",  # magic links are self-signed
)


class InvalidSessionError(Exception):
    """Session cookie failed HMAC, expiry, or format validation."""


# ─── Key derivation ─────────────────────────────────────────────────────


def _hmac_key() -> bytes:
    """Derive a 32-byte HMAC key from PAYLOAD_KEY via HKDF-SHA256."""
    return HKDF(
        algorithm=SHA256(),
        length=HMAC_SHA256_DIGEST_BYTES,
        salt=DASHBOARD_SESSION_HKDF_SALT,
        info=DASHBOARD_SESSION_HKDF_INFO,
    ).derive(get_key())


# ─── Cookie sign/verify ─────────────────────────────────────────────────


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sign_session(*, user: str, ttl_seconds: int | None = None) -> str:
    """Produce a signed session cookie value."""
    ttl = ttl_seconds if ttl_seconds is not None else DASHBOARD_SESSION_MAX_AGE_SECONDS
    body = _canonical({"u": user, "e": int(time.time()) + ttl})
    mac = hmac.new(_hmac_key(), body, hashlib.sha256).digest()
    return base64.urlsafe_b64encode(mac + body).decode().rstrip("=")


def verify_session(cookie: str) -> str:
    """Decode + verify a session cookie. Returns the username. Raises
    `InvalidSessionError` on any failure."""
    if not cookie:
        raise InvalidSessionError("empty cookie")

    padded = cookie + "=" * (-len(cookie) % 4)
    try:
        blob = base64.urlsafe_b64decode(padded)
    except Exception as exc:
        raise InvalidSessionError(f"not base64: {exc}") from exc

    if len(blob) < HMAC_SHA256_DIGEST_BYTES + 2:
        raise InvalidSessionError("too short")

    mac, body = blob[:HMAC_SHA256_DIGEST_BYTES], blob[HMAC_SHA256_DIGEST_BYTES:]
    expected = hmac.new(_hmac_key(), body, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, mac):
        raise InvalidSessionError("signature mismatch")

    try:
        payload = json.loads(body)
        user = str(payload["u"])
        expires_at = int(payload["e"])
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise InvalidSessionError(f"malformed body: {exc}") from exc

    if time.time() > expires_at:
        raise InvalidSessionError("expired")

    return user


# ─── Password check ─────────────────────────────────────────────────────


def verify_password(*, user: str, password: str) -> bool:
    """Constant-time compare of submitted credentials against settings.

    Auth is OFF when DASHBOARD_PASSWORD is unset; callers shouldn't
    reach this function in that state. Returns False rather than
    raising so login routes can return a uniform 401.
    """
    if not settings.DASHBOARD_PASSWORD:
        return False
    # Both branches run compare_digest so a mismatched username doesn't
    # short-circuit faster than a wrong password (timing-leak defense).
    user_ok = hmac.compare_digest(user, settings.DASHBOARD_USER)
    pw_ok = hmac.compare_digest(password, settings.DASHBOARD_PASSWORD)
    return user_ok and pw_ok


# ─── Middleware ─────────────────────────────────────────────────────────


def _is_public_path(path: str) -> bool:
    return any(path.startswith(p) for p in _PUBLIC_PREFIXES)


def _has_valid_admin_token(request: Request) -> bool:
    """Bearer admin token acts as a skeleton key (ops use)."""
    if not settings.ADMIN_API_TOKEN:
        return False
    header = request.headers.get("authorization", "")
    if not header.lower().startswith("bearer "):
        return False
    supplied = header.split(" ", 1)[1].strip()
    return hmac.compare_digest(supplied, settings.ADMIN_API_TOKEN)


class DashboardAuthMiddleware(BaseHTTPMiddleware):
    """Gate the API behind the optional dashboard password."""

    async def dispatch(self, request: Request, call_next):  # type: ignore[override]
        # Auth off entirely — no password set.
        if not settings.DASHBOARD_PASSWORD:
            return await call_next(request)

        path = request.url.path

        # Non-API requests (static assets served by the bundled
        # dashboard, /docs, etc.) pass through. The dashboard itself
        # enforces its own redirect via middleware.ts.
        if not path.startswith("/api/"):
            return await call_next(request)

        if _is_public_path(path):
            return await call_next(request)

        if _has_valid_admin_token(request):
            return await call_next(request)

        cookie = request.cookies.get(DASHBOARD_SESSION_COOKIE_NAME)
        if cookie:
            try:
                request.state.auth_user = verify_session(cookie)
                return await call_next(request)
            except InvalidSessionError as exc:
                logger.info("Rejected session cookie: %s", exc)

        return JSONResponse(
            {"detail": "Authentication required."},
            status_code=status.HTTP_401_UNAUTHORIZED,
        )


# ─── FastAPI dep (optional — most routes covered by middleware) ─────────


def require_session(request: Request) -> str:
    """Dep for routes that need the logged-in user name (not just "auth").

    Routes covered by the middleware can rely on `request.state.auth_user`
    being set. This dep is the typed accessor.
    """
    user = getattr(request.state, "auth_user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required.")
    return user
