"""HMAC signing for outbound webhooks.

Lives in `utils/` rather than `server/services/` so the durable
adapters (Temporal, LangGraph) can verify callback signatures
WITHOUT pulling in the full `[server]` extra (FastAPI, SQLModel,
slack-sdk, etc.) — see PR #71. The previous home transitively
imported half the server package via `from awaithumans.server.db.models
import Task`, which meant a Temporal callback receiver hit
`ModuleNotFoundError: cryptography` (and several others) on the
first webhook.

What this module does:

  - Derive a 32-byte HMAC key from `AWAITHUMANS_PAYLOAD_KEY` via
    HKDF-SHA256 with channel-scoped salt + info, so a leak of any
    other downstream subkey (sessions, magic links) doesn't
    compromise webhook signing.
  - Sign a request body to produce the `sha256=<hex>` value of the
    `X-Awaithumans-Signature` header.
  - Verify an incoming signature with constant-time comparison,
    tolerating a header value with or without the `sha256=` prefix
    (some routing layers strip it).

Cross-language compat is the source of truth: the TS adapters do the
SAME HKDF derivation in `signBody` / `verifySignature`, so a Python
server can ship a webhook to a TS receiver and vice versa.

Dependencies: `cryptography` (HKDF). NOT `awaithumans.server.*` —
the import surface is intentionally tiny.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import os
from functools import lru_cache

from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from awaithumans.utils.constants import (
    HMAC_SHA256_DIGEST_BYTES,
    WEBHOOK_HKDF_INFO,
    WEBHOOK_HKDF_SALT,
)


class PayloadKeyMissingError(RuntimeError):
    """Raised when AWAITHUMANS_PAYLOAD_KEY is unset or unreadable.

    Distinct error class so callers can choose to surface a clearer
    "the webhook receiver isn't configured" message instead of a
    generic 500."""


class PayloadKeyInvalidError(RuntimeError):
    """Raised when AWAITHUMANS_PAYLOAD_KEY is set but not a valid
    32-byte base64 value. Most often a copy-paste truncation."""


def _decode_payload_key(raw: str) -> bytes:
    """Accept urlsafe-base64 or standard base64, with or without
    padding. Mirrors `server.core.encryption.get_key` exactly so
    a single PAYLOAD_KEY produces the same bytes whether it's used
    for AES at the storage layer or HKDF here."""
    padded = raw + "=" * (-len(raw) % 4)
    decoded: bytes | None = None
    try:
        decoded = base64.urlsafe_b64decode(padded)
    except Exception:  # noqa: BLE001
        try:
            decoded = base64.b64decode(padded, validate=True)
        except Exception:  # noqa: BLE001
            decoded = None
    if decoded is None:
        raise PayloadKeyInvalidError(
            "AWAITHUMANS_PAYLOAD_KEY is not valid base64. "
            "Regenerate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    if len(decoded) != HMAC_SHA256_DIGEST_BYTES:
        raise PayloadKeyInvalidError(
            f"AWAITHUMANS_PAYLOAD_KEY must decode to {HMAC_SHA256_DIGEST_BYTES} "
            f"bytes; got {len(decoded)}. Generate with: "
            "python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    return decoded


@lru_cache(maxsize=1)
def _root_key() -> bytes:
    """Resolve and validate the root PAYLOAD_KEY once per process.

    Reads directly from `os.environ` so the utils module stays free
    of the server's `pydantic-settings` dependency. Production
    deployments set the env var via their normal config; tests can
    monkeypatch `os.environ` and call `reset_cache()`."""
    raw = os.environ.get("AWAITHUMANS_PAYLOAD_KEY")
    if not raw:
        raise PayloadKeyMissingError(
            "AWAITHUMANS_PAYLOAD_KEY is not set. The webhook signing "
            "key derives from it; both the awaithumans server AND "
            "any callback receiver verifying webhooks need the same "
            "value. Generate with:\n"
            "  python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    return _decode_payload_key(raw)


@lru_cache(maxsize=1)
def _hmac_key() -> bytes:
    """HKDF-SHA256 over the root key, channel-scoped to webhooks.

    Channel-scoped salt — the same root key signs sessions, magic
    links, AND webhooks, but each one derives a distinct subkey so
    a leak of any one downstream key doesn't compromise the others.
    Bumping `WEBHOOK_HKDF_INFO` is a versioned breaking change —
    old signatures stop verifying, callers must migrate."""
    return HKDF(
        algorithm=SHA256(),
        length=HMAC_SHA256_DIGEST_BYTES,
        salt=WEBHOOK_HKDF_SALT,
        info=WEBHOOK_HKDF_INFO,
    ).derive(_root_key())


def reset_cache() -> None:
    """Drop both cached keys — used by tests that swap PAYLOAD_KEY.
    Without this, a fixture that mutates the env var sees stale
    bytes from the first test that ran in the process."""
    _root_key.cache_clear()
    _hmac_key.cache_clear()


def sign_body(body: bytes) -> str:
    """Compute the `sha256=<hex>` signature header value.

    Public so callback handlers in the SDK adapters (and the docs
    examples) can produce signatures the same way the awaithumans
    server does. Receivers should use `verify_signature` instead —
    constant-time and tolerant of the optional `sha256=` prefix."""
    mac = hmac.new(_hmac_key(), body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def verify_signature(*, body: bytes, signature: str | None) -> bool:
    """Constant-time check of the `X-Awaithumans-Signature` header.

    Used by the SDK adapters' callback handlers (Temporal, LangGraph)
    to verify incoming webhook bodies before signalling a workflow.
    `signature` is the header value as received (may include the
    `sha256=` prefix or just be the hex digest). Both shapes are
    accepted; missing/empty signatures fail closed.
    """
    if not signature:
        return False
    expected = sign_body(body)
    if hmac.compare_digest(signature, expected):
        return True
    # Tolerate header-value-without-prefix (some routing layers strip).
    return hmac.compare_digest(signature, expected.removeprefix("sha256="))
