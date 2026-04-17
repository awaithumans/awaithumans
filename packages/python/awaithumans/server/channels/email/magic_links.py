"""Magic-link tokens for one-click email actions.

When an email goes out for a switch or a small single_select, we embed
per-option URLs like:

    {PUBLIC_URL}/api/channels/email/action/{token}

where `token` is a self-verifying blob carrying (task_id, field_name,
value, expiry). The route verifies the HMAC + expiry and, on POST,
completes the task with a single-field response.

Anti-prefetch: GET shows a confirmation page with a POST form. Bots
and mail clients (Outlook SafeLinks, Google image proxy) that prefetch
GET never accidentally submit the response.

HMAC key: HKDF-derived from PAYLOAD_KEY with a channel-specific salt.
Using the encryption key directly for HMAC would blur two different
primitives under one key — HKDF gives us a cryptographically distinct
key without a second env var for operators to manage.
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

from awaithumans.server.channels.email.types import ActionClaim
from awaithumans.server.core.encryption import get_key
from awaithumans.utils.constants import (
    HMAC_SHA256_DIGEST_BYTES,
    MAGIC_LINK_HKDF_INFO,
    MAGIC_LINK_HKDF_SALT,
    MAGIC_LINK_MAX_AGE_SECONDS,
)

logger = logging.getLogger("awaithumans.server.channels.email.magic_links")


class InvalidActionTokenError(Exception):
    """Token failed HMAC verification, was tampered, or is expired."""


def _hmac_key() -> bytes:
    """Derive a 32-byte HMAC key from PAYLOAD_KEY via HKDF-SHA256."""
    return HKDF(
        algorithm=SHA256(),
        length=HMAC_SHA256_DIGEST_BYTES,
        salt=MAGIC_LINK_HKDF_SALT,
        info=MAGIC_LINK_HKDF_INFO,
    ).derive(get_key())


def _canonical(payload: dict[str, Any]) -> bytes:
    """Stable JSON encoding for HMAC input. Sort keys, no whitespace."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()


def sign_action_token(
    *,
    task_id: str,
    field_name: str,
    value: Any,
    ttl_seconds: int | None = None,
) -> str:
    """Produce a signed token encoding (task_id, field_name, value, expiry)."""
    ttl = ttl_seconds if ttl_seconds is not None else MAGIC_LINK_MAX_AGE_SECONDS
    payload = {
        "t": task_id,
        "f": field_name,
        "v": value,
        "e": int(time.time()) + ttl,
    }
    body = _canonical(payload)
    mac = hmac.new(_hmac_key(), body, hashlib.sha256).digest()
    blob = mac + body
    return base64.urlsafe_b64encode(blob).decode().rstrip("=")


def verify_action_token(token: str) -> ActionClaim:
    """Decode + verify a signed token. Raises InvalidActionTokenError on any failure."""
    if not token:
        raise InvalidActionTokenError("empty token")

    padded = token + "=" * (-len(token) % 4)
    try:
        blob = base64.urlsafe_b64decode(padded)
    except Exception as exc:
        raise InvalidActionTokenError(f"not base64: {exc}") from exc

    if len(blob) < HMAC_SHA256_DIGEST_BYTES + 2:
        raise InvalidActionTokenError("too short")

    mac, body = blob[:HMAC_SHA256_DIGEST_BYTES], blob[HMAC_SHA256_DIGEST_BYTES:]
    expected = hmac.new(_hmac_key(), body, hashlib.sha256).digest()
    if not hmac.compare_digest(expected, mac):
        raise InvalidActionTokenError("signature mismatch")

    try:
        payload = json.loads(body)
    except Exception as exc:
        raise InvalidActionTokenError(f"body not JSON: {exc}") from exc

    try:
        task_id = str(payload["t"])
        field_name = str(payload["f"])
        value = payload["v"]
        expires_at = int(payload["e"])
    except (KeyError, TypeError, ValueError) as exc:
        raise InvalidActionTokenError(f"missing fields: {exc}") from exc

    if time.time() > expires_at:
        raise InvalidActionTokenError("expired")

    return ActionClaim(
        task_id=task_id,
        field_name=field_name,
        value=value,
        expires_at=expires_at,
    )
