"""Embed token sign and verify primitives, plus origin allowlist matching.

Spec references:
  §4.2 — JWT claim shape (EmbedClaims fields: task_id, sub, kind,
          parent_origin, iat, exp, jti).
  §4.3 — Origin allowlist parsing and matching rules.
  §7.1 — Security threats: algorithm-pinning (alg=none attack), audience
          binding, issuer binding, expiry enforcement, clock-skew leeway.

Public exports: EmbedClaims, sign_embed_token, verify_embed_token,
                InvalidAllowlistEntryError, parse_origin_allowlist,
                origin_in_allowlist.
No DB access, no FastAPI.
"""

from __future__ import annotations

import re
import secrets
import time
from dataclasses import dataclass
from urllib.parse import urlparse

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


# ── Origin allowlist ───────────────────────────────────────────────────────

# RFC 1123 DNS label: starts and ends with alnum, may contain hyphens, 1–63 chars.
# The single-char case (`^[a-z0-9]$`) is covered by the optional group being absent.
_LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$", re.IGNORECASE)

# Hosts allowed to use http (non-TLS). Everything else must be https.
_HTTP_ALLOWED_HOSTS = {"localhost", "127.0.0.1"}


class InvalidAllowlistEntryError(ValueError):
    """Raised when an origin allowlist entry fails validation (§4.3)."""


def _default_port(scheme: str) -> int:
    """Return the default TCP port for a given URL scheme."""
    return 443 if scheme == "https" else 80


def _validate_origin_entry(s: str) -> None:
    """Validate a single origin allowlist entry string.

    Raises InvalidAllowlistEntryError if the entry is malformed per §4.3.
    """
    parsed = urlparse(s)

    # Scheme must be http or https.
    if parsed.scheme not in ("http", "https"):
        raise InvalidAllowlistEntryError(
            f"Invalid allowlist entry {s!r}: scheme must be 'http' or 'https', "
            f"got {parsed.scheme!r}."
        )

    # No path, query, or fragment — origin is scheme+host+port only.
    # urlparse puts a trailing slash into path when there is no path component
    # for entries like "https://acme.com/", so check path, query, and fragment.
    if parsed.path not in ("", "/"):
        raise InvalidAllowlistEntryError(
            f"Invalid allowlist entry {s!r}: must not contain a path component "
            f"(got path={parsed.path!r}). An origin is scheme+host+port only."
        )
    # Reject explicit trailing slash even if path == "/"
    if parsed.path == "/":
        raise InvalidAllowlistEntryError(
            f"Invalid allowlist entry {s!r}: trailing slash is not allowed. "
            "Use 'https://example.com' not 'https://example.com/'."
        )
    if parsed.query:
        raise InvalidAllowlistEntryError(
            f"Invalid allowlist entry {s!r}: must not contain a query string."
        )
    if parsed.fragment:
        raise InvalidAllowlistEntryError(
            f"Invalid allowlist entry {s!r}: must not contain a fragment."
        )

    host = parsed.hostname or ""
    if not host:
        raise InvalidAllowlistEntryError(f"Invalid allowlist entry {s!r}: host is empty.")

    # http is only allowed for localhost / loopback.
    if parsed.scheme == "http" and host not in _HTTP_ALLOWED_HOSTS:
        raise InvalidAllowlistEntryError(
            f"Invalid allowlist entry {s!r}: http is only permitted for "
            f"localhost/127.0.0.1. Use https for production origins."
        )

    # Count wildcards — at most one, and it must be the leading label.
    wildcard_count = host.count("*")
    if wildcard_count > 1:
        raise InvalidAllowlistEntryError(
            f"Invalid allowlist entry {s!r}: multiple wildcards are not allowed. "
            "Use a single leading wildcard label, e.g. 'https://*.example.com'."
        )

    if wildcard_count == 1:
        # The wildcard must be the leading label: host must start with "*.".
        if not host.startswith("*."):
            raise InvalidAllowlistEntryError(
                f"Invalid allowlist entry {s!r}: wildcard must be the leading label "
                "(e.g. '*.example.com'). Embedded wildcards like 'a.*.com' are not allowed."
            )
        # Validate the remaining labels (the apex domain).
        apex = host[2:]  # strip leading "*."
        labels = apex.split(".")
        for label in labels:
            if not _LABEL_RE.match(label):
                raise InvalidAllowlistEntryError(
                    f"Invalid allowlist entry {s!r}: label {label!r} contains invalid "
                    "characters. DNS labels must match [a-z0-9][a-z0-9-]*[a-z0-9]."
                )
    else:
        # Exact host — skip wildcard label, validate all labels.
        # For IP literals like 127.0.0.1, skip label validation.
        if host not in _HTTP_ALLOWED_HOSTS and not host.replace(".", "").isdigit():
            labels = host.split(".")
            for label in labels:
                if not _LABEL_RE.match(label):
                    raise InvalidAllowlistEntryError(
                        f"Invalid allowlist entry {s!r}: label {label!r} contains invalid "
                        "characters. DNS labels must match [a-z0-9][a-z0-9-]*[a-z0-9]."
                    )


def _matches_entry(origin: str, entry: str) -> bool:
    """Return True if *origin* matches the given allowlist *entry*.

    Matching rules per §4.3:
    - Schemes must match exactly.
    - Ports must match (using scheme defaults for omitted ports).
    - Hosts: exact (case-insensitive) or single-leading-wildcard label match.
    """
    o = urlparse(origin)
    e = urlparse(entry)

    # Scheme must match exactly.
    if o.scheme != e.scheme:
        return False

    # Effective ports must match (substitute scheme default for omitted port).
    o_port = o.port if o.port is not None else _default_port(o.scheme)
    e_port = e.port if e.port is not None else _default_port(e.scheme)
    if o_port != e_port:
        return False

    origin_host = (o.hostname or "").lower()
    entry_host = (e.hostname or "").lower()

    if "*" not in entry_host:
        # Exact host comparison.
        return origin_host == entry_host

    # Wildcard: entry_host is "*.apex" — strip leading "*.".
    apex = entry_host[2:]  # e.g. "acme.com"

    # Origin host must end with ".<apex>" (not just apex — apex itself doesn't match).
    suffix = f".{apex}"
    if not origin_host.endswith(suffix):
        return False

    # The prefix before ".<apex>" must be a single DNS label (no dots, non-empty).
    prefix = origin_host[: -len(suffix)]
    if not prefix or "." in prefix:
        return False

    # The prefix label must also be a valid DNS label.
    return bool(_LABEL_RE.match(prefix))


def parse_origin_allowlist(raw: str) -> tuple[str, ...]:
    """Parse and validate a comma-separated origin allowlist string.

    Args:
        raw: Comma-separated origin entries, e.g.
             "https://app.acme.com, https://*.staging.acme.com".
             Typically sourced from ``settings.EMBED_PARENT_ORIGINS``.

    Returns:
        A frozen tuple of validated entry strings, in input order.
        Empty input (or all-whitespace) returns ``()``.

    Raises:
        InvalidAllowlistEntryError: if any non-empty entry fails validation.
    """
    entries = []
    for chunk in raw.split(","):
        stripped = chunk.strip()
        if not stripped:
            continue
        _validate_origin_entry(stripped)
        entries.append(stripped)
    return tuple(entries)


def origin_in_allowlist(origin: str, allowlist: tuple[str, ...]) -> bool:
    """Return True if *origin* matches any entry in *allowlist*.

    Args:
        origin: The incoming ``Origin`` header value to test, e.g.
                ``"https://app.acme.com"``.
        allowlist: A validated allowlist produced by :func:`parse_origin_allowlist`.

    Returns:
        ``True`` on the first matching entry, ``False`` if none match.
    """
    parsed = urlparse(origin)
    if parsed.scheme not in ("http", "https"):
        return False
    if not parsed.hostname:
        return False
    return any(_matches_entry(origin, entry) for entry in allowlist)
