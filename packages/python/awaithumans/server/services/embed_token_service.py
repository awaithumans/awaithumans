"""Embed token sign and verify primitives.

Spec references:
  §4.2 — JWT claim shape (EmbedClaims fields: task_id, sub, kind,
          parent_origin, iat, exp, jti).
  §7.1 — Security threats: algorithm-pinning (alg=none attack), audience
          binding, issuer binding, expiry enforcement, clock-skew leeway.

Public exports: EmbedClaims, sign_embed_token, verify_embed_token.
No DB access, no FastAPI, no origin allowlist (that is Task 5).
"""

from __future__ import annotations

import secrets
import time
from dataclasses import dataclass

import jwt as pyjwt

from awaithumans.server.services.exceptions import InvalidEmbedTokenError
from awaithumans.utils.constants import (
    EMBED_TOKEN_AUDIENCE,
    EMBED_TOKEN_ISSUER,
    EMBED_TOKEN_LEEWAY_SECONDS,
    EMBED_TOKEN_MAX_TTL_SECONDS,
    EMBED_TOKEN_MIN_TTL_SECONDS,
)

# ── Constants ──────────────────────────────────────────────────────────────

# Algorithm allow-list passed to pyjwt.decode() — MUST be a list, not a
# single string, so PyJWT's algorithm-pinning defence applies (rejects
# alg=none and RS*/ES* tokens signed against an HS key, etc.).
_ALGORITHM = "HS256"
_ALGORITHMS = [_ALGORITHM]

# Supported token kinds. When operator-kind lands (Phase 4), add "operator" here.
_SUPPORTED_KINDS = ("end_user",)


# ── Data shape ─────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class EmbedClaims:
    """Decoded, verified payload from an embed JWT.

    All fields are present and validated before this dataclass is returned.
    Downstream callers (Task 5 origin-match, Task 11 middleware) must not
    re-validate the JWT — they receive this already-verified object.
    """

    task_id: str
    sub: str | None
    kind: str
    parent_origin: str
    iat: int
    exp: int
    jti: str


# ── Private helpers ────────────────────────────────────────────────────────


def _token_id() -> str:
    """Generate a sortable, unique token ID: 13-hex timestamp-ms + 16-hex random.

    Produces a 29-character lowercase hex string. Not a true ULID (no
    Crockford base32) but satisfies the spec's requirement of timestamp-ms +
    secrets.token_hex(8) uniqueness.
    """
    ts_hex = format(int(time.time() * 1000), "013x")
    rand_hex = secrets.token_hex(8)
    return f"{ts_hex}{rand_hex}"


# ── Public API ─────────────────────────────────────────────────────────────


def sign_embed_token(
    *,
    secret: str,
    task_id: str,
    sub: str | None,
    kind: str,
    parent_origin: str,
    ttl_seconds: int,
) -> tuple[str, int]:
    """Sign and return an embed JWT plus its expiry unix timestamp.

    Args:
        secret: HMAC-SHA256 signing key (the operator's embed secret).
        task_id: The task the embed iframe will display.
        sub: End-user identifier (email, user-id, etc.). May be None.
        kind: Token kind — currently only "end_user" is supported.
        parent_origin: The iframe parent origin (e.g. "https://app.example.com").
        ttl_seconds: Desired lifetime in seconds. Clamped to
                     [EMBED_TOKEN_MIN_TTL_SECONDS, EMBED_TOKEN_MAX_TTL_SECONDS].
                     Raises ValueError if negative.

    Returns:
        (token, exp_unix) — the signed JWT string and its expiry as a Unix
        timestamp so callers can forward exp to the client without re-parsing.
    """
    if ttl_seconds < 0:
        raise ValueError(f"ttl_seconds must be non-negative, got {ttl_seconds}")

    clamped_ttl = max(EMBED_TOKEN_MIN_TTL_SECONDS, min(ttl_seconds, EMBED_TOKEN_MAX_TTL_SECONDS))

    now = int(time.time())
    exp = now + clamped_ttl
    jti = _token_id()

    payload: dict[str, object] = {
        "iss": EMBED_TOKEN_ISSUER,
        "aud": EMBED_TOKEN_AUDIENCE,
        "iat": now,
        "exp": exp,
        "task_id": task_id,
        "sub": sub,
        "kind": kind,
        "parent_origin": parent_origin,
        "jti": jti,
    }

    token: str = pyjwt.encode(payload, secret, algorithm=_ALGORITHM)
    return token, exp


def verify_embed_token(token: str, *, secret: str) -> EmbedClaims:
    """Verify an embed JWT and return its decoded claims.

    Performs full cryptographic verification: signature, audience, issuer,
    expiry (with leeway), and algorithm-pinning (alg=none rejected). Also
    validates that required custom claims are present and that kind is
    a supported value.

    Args:
        token: The raw JWT string from the Authorization header.
        secret: HMAC-SHA256 signing key (must match the key used to sign).

    Returns:
        EmbedClaims — a frozen dataclass with all decoded fields.

    Raises:
        InvalidEmbedTokenError: for any verification failure, with a
            human-readable reason string.
    """
    try:
        decoded: dict[str, object] = pyjwt.decode(
            token,
            secret,
            algorithms=_ALGORITHMS,  # allowlist pins HS256; rejects alg=none
            audience=EMBED_TOKEN_AUDIENCE,
            issuer=EMBED_TOKEN_ISSUER,
            leeway=EMBED_TOKEN_LEEWAY_SECONDS,
            options={
                "require": ["exp", "iat", "aud", "iss"]
            },  # reject tokens missing required claims
        )
    except pyjwt.ExpiredSignatureError as exc:
        raise InvalidEmbedTokenError(reason="token has expired") from exc
    except pyjwt.InvalidAudienceError as exc:
        raise InvalidEmbedTokenError(reason="invalid audience") from exc
    except pyjwt.InvalidIssuerError as exc:
        raise InvalidEmbedTokenError(reason="invalid issuer") from exc
    except pyjwt.InvalidAlgorithmError as exc:
        raise InvalidEmbedTokenError(reason="invalid algorithm") from exc
    except pyjwt.PyJWTError as exc:
        raise InvalidEmbedTokenError(reason=f"token verification failed: {exc}") from exc

    # Validate required custom claims are present
    for field in ("task_id", "kind", "parent_origin", "jti"):
        if not decoded.get(field):
            raise InvalidEmbedTokenError(reason=f"missing required claim: {field}")

    kind = decoded["kind"]
    if kind not in _SUPPORTED_KINDS:
        raise InvalidEmbedTokenError(reason=f"unsupported kind: {kind}")

    return EmbedClaims(
        task_id=str(decoded["task_id"]),
        sub=str(decoded["sub"]) if decoded.get("sub") is not None else None,
        kind=str(decoded["kind"]),
        parent_origin=str(decoded["parent_origin"]),
        iat=int(decoded["iat"]),  # type: ignore[arg-type]
        exp=int(decoded["exp"]),  # type: ignore[arg-type]
        jti=str(decoded["jti"]),
    )
