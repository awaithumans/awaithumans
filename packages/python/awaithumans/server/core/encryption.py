"""At-rest encryption for sensitive DB columns.

Uses AES-256-GCM (authenticated encryption). Every value on the wire
to the database is:

    base64( key_id_byte || nonce(12) || ciphertext || tag(16) )

The `key_id_byte` is 0x01 — reserved for future key rotation. When we
rotate, we bump it and the decrypt path picks the right key.

The key itself is read from `AWAITHUMANS_PAYLOAD_KEY` (32 raw bytes
encoded as base64, urlsafe or standard — either works). Generate with:

    python -c 'import secrets; print(secrets.token_urlsafe(32))'

The DB never sees plaintext. `EncryptedString` is a SQLAlchemy
TypeDecorator, so any column declared with it encrypts on INSERT/UPDATE
and decrypts on SELECT transparently — service code reads and writes
plain strings, the crypto happens at the binding layer.
"""

from __future__ import annotations

import base64
import logging
import os
from functools import lru_cache

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy.types import String, TypeDecorator

from awaithumans.server.core.config import settings

logger = logging.getLogger("awaithumans.server.core.encryption")

# Current key version. Bumped when we rotate. Ciphertext from the old
# version is still decryptable as long as the old key material lives in
# a (future) key registry.
_CURRENT_KEY_ID = 0x01
_NONCE_BYTES = 12


class EncryptionNotConfiguredError(RuntimeError):
    """Raised when a sensitive column is read/written without PAYLOAD_KEY set."""


class EncryptionKeyError(RuntimeError):
    """Raised when PAYLOAD_KEY is set but not a valid 32-byte base64 value."""


@lru_cache(maxsize=1)
def get_key() -> bytes:
    """Resolve and validate the encryption key once per process."""
    raw = settings.PAYLOAD_KEY
    if not raw:
        raise EncryptionNotConfiguredError(
            "AWAITHUMANS_PAYLOAD_KEY is not set. Generate with:\n"
            "  python -c 'import secrets; print(secrets.token_urlsafe(32))'\n"
            "Required for any server deployment that stores encrypted data "
            "(Slack OAuth installs, redacted payloads, etc.)."
        )

    # Accept urlsafe-base64 or standard base64. Pad to a multiple of 4 if needed.
    # We use `validate=True` on the standard decoder because the default
    # silently discards non-alphabet chars (including urlsafe's `-` and `_`),
    # which can produce a short result from a well-formed urlsafe key.
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
        raise EncryptionKeyError(
            "AWAITHUMANS_PAYLOAD_KEY is not valid base64. "
            "Regenerate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    if len(decoded) != 32:
        raise EncryptionKeyError(
            f"AWAITHUMANS_PAYLOAD_KEY must decode to 32 bytes; got {len(decoded)}. "
            "Generate with: python -c 'import secrets; print(secrets.token_urlsafe(32))'"
        )
    return decoded


def reset_key_cache() -> None:
    """Drop the cached key — used by tests that swap PAYLOAD_KEY."""
    get_key.cache_clear()


def encrypt_str(plaintext: str) -> str:
    """AES-GCM encrypt a string → base64(version || nonce || ciphertext || tag)."""
    aesgcm = AESGCM(get_key())
    nonce = os.urandom(_NONCE_BYTES)
    ct = aesgcm.encrypt(nonce, plaintext.encode("utf-8"), None)
    blob = bytes([_CURRENT_KEY_ID]) + nonce + ct
    return base64.b64encode(blob).decode("ascii")


def decrypt_str(ciphertext_b64: str) -> str:
    """Inverse of encrypt_str. Raises on bad key, bad version, or tampering."""
    try:
        blob = base64.b64decode(ciphertext_b64)
    except Exception as exc:  # noqa: BLE001
        raise EncryptionKeyError(f"Ciphertext is not valid base64: {exc}") from exc

    if len(blob) < 1 + _NONCE_BYTES + 16:  # min: version + nonce + tag
        raise EncryptionKeyError("Ciphertext too short to be valid.")

    version = blob[0]
    if version != _CURRENT_KEY_ID:
        raise EncryptionKeyError(
            f"Ciphertext uses key version {version}; this server only knows "
            f"{_CURRENT_KEY_ID}. Key rotation registry not yet implemented."
        )

    nonce = blob[1 : 1 + _NONCE_BYTES]
    ct = blob[1 + _NONCE_BYTES :]
    aesgcm = AESGCM(get_key())
    # AES-GCM raises cryptography.exceptions.InvalidTag on tampered ciphertext
    # or wrong key — we let it propagate so callers see the failure.
    return aesgcm.decrypt(nonce, ct, None).decode("utf-8")


class EncryptedString(TypeDecorator):
    """Transparent AES-GCM encryption for a String/Text column.

    Declared on a SQLModel/SQLAlchemy column:

        bot_token: str = Field(sa_column=Column(EncryptedString))

    Service code reads and writes plain strings; the binding layer runs
    encrypt/decrypt on each round-trip. A row written by the old plaintext
    schema will fail to decrypt — no silent fallback (that would defeat
    the point).
    """

    impl = String
    cache_ok = True

    def process_bind_param(  # type: ignore[override]
        self, value: str | None, dialect: object
    ) -> str | None:
        if value is None:
            return None
        return encrypt_str(value)

    def process_result_value(  # type: ignore[override]
        self, value: str | None, dialect: object
    ) -> str | None:
        if value is None:
            return None
        return decrypt_str(value)
