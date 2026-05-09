"""ASGI middleware that recognises ``Authorization: Bearer <embed JWT>`` and writes
decoded claims to ``request.state.embed_ctx``.

Public exports:
  EmbedAuthMiddleware — BaseHTTPMiddleware subclass; add via app.add_middleware().
  get_embed_ctx       — convenience accessor for route handlers (Task 13).

Spec references:
  §5.1 — EmbedAuthMiddleware design and bearer-prefix matching rules.
  §7   — Security: ah_sk_ pass-through, disabled-embed pass-through, 401 shape.
"""

from __future__ import annotations

from collections.abc import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from awaithumans.server.services.embed_token_service import EmbedClaims, verify_embed_token
from awaithumans.server.services.exceptions import InvalidEmbedTokenError

# ── Type aliases ──────────────────────────────────────────────────────────

SecretProvider = Callable[[], str | None]


# ── Middleware ────────────────────────────────────────────────────────────


class EmbedAuthMiddleware(BaseHTTPMiddleware):
    """Verify embed JWTs from ``Authorization: Bearer <token>`` headers.

    On success, ``request.state.embed_ctx`` is set to the decoded
    :class:`~awaithumans.server.services.embed_token_service.EmbedClaims`.
    On every other path (no header, non-bearer scheme, service key, or
    embed feature disabled), ``request.state.embed_ctx`` is set to ``None``
    and the request proceeds normally.

    Only malformed or cryptographically invalid JWTs cause an early 401 —
    they never reach ``call_next``.

    Args:
        app: The ASGI application to wrap.
        secret_provider: A zero-argument callable that returns the current
            HMAC-SHA256 signing secret (or ``None`` / empty string if the
            embed feature is disabled). Invoked **per request** so secret
            rotations take effect without a restart.
    """

    def __init__(self, app: ASGIApp, *, secret_provider: SecretProvider) -> None:
        super().__init__(app)
        self._secret_provider = secret_provider

    async def dispatch(self, request: Request, call_next: Callable[..., Response]) -> Response:
        # Always set a default so downstream handlers never hit AttributeError.
        request.state.embed_ctx = None

        header = request.headers.get("authorization", "")
        if not header.lower().startswith("bearer "):
            # No Authorization header, or a non-bearer scheme (Basic, etc.).
            return await call_next(request)

        token = header.split(" ", 1)[1].strip()

        # Service keys (ah_sk_...) belong to the mint endpoint's
        # require_service_key dependency, not here. Pass through so they
        # don't hit verify_embed_token (which would raise on a non-JWT).
        if token.startswith("ah_sk_"):
            return await call_next(request)

        # Only handle JWT-shaped tokens (header.payload.signature). Other
        # bearer credentials — admin API tokens, dashboard session JWTs from
        # core/auth.py, etc. — must pass through untouched. Without this
        # guard the middleware would 401 on any non-embed bearer.
        if token.count(".") != 2:
            return await call_next(request)

        secret = self._secret_provider()
        if not secret:
            # EMBED_SIGNING_SECRET unset → embed feature disabled at the
            # server level. Pass through anonymous; route layer decides
            # whether to 401.
            return await call_next(request)

        try:
            claims = verify_embed_token(token, secret=secret)
        except InvalidEmbedTokenError as e:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "INVALID_EMBED_TOKEN",
                        "message": str(e),
                    },
                },
            )

        request.state.embed_ctx = claims
        return await call_next(request)


# ── Accessor ──────────────────────────────────────────────────────────────


def get_embed_ctx(request: Request) -> EmbedClaims | None:
    """Return the decoded embed claims from ``request.state``, or ``None``.

    Convenience wrapper for route handlers (used by Task 13 and beyond).
    Safe to call even when the middleware is not installed — returns ``None``
    if ``embed_ctx`` is absent from ``request.state``.
    """
    return getattr(request.state, "embed_ctx", None)  # type: ignore[no-any-return]
