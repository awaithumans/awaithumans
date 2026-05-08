"""Service-key CRUD and verification.

Public API: create_service_key, verify_service_key, list_service_keys,
            revoke_service_key.
Private helpers: _hash, _ulid.

No FastAPI imports. Session is passed explicitly by the caller.
"""

from __future__ import annotations

import hashlib
import secrets
import time
from datetime import UTC, datetime

from sqlmodel import Session, select

from awaithumans.server.db.models import ServiceAPIKey
from awaithumans.server.services.exceptions import ServiceKeyNotFoundError
from awaithumans.utils.constants import (
    SERVICE_KEY_DISPLAY_PREFIX_LENGTH,
    SERVICE_KEY_MAX_NAME_LENGTH,
    SERVICE_KEY_PREFIX,
    SERVICE_KEY_RAW_BYTES,
)

# ── Private helpers ────────────────────────────────────────────────────────────


def _hash(raw_key: str) -> str:
    """Return the SHA-256 hex digest of a raw service key string."""
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()


def _ulid() -> str:
    """Generate a sortable unique ID: 13-hex timestamp-ms + 16-hex random.

    Produces a 29-character lowercase hex string. Not a true ULID (no
    Crockford base32) but satisfies timestamp-ms + secrets.token_hex(8)
    uniqueness — same shape as _token_id in embed_token_service.py.
    """
    ts_hex = format(int(time.time() * 1000), "013x")
    rand_hex = secrets.token_hex(8)
    return f"{ts_hex}{rand_hex}"


# ── Public API ─────────────────────────────────────────────────────────────────


def create_service_key(session: Session, *, name: str) -> tuple[str, ServiceAPIKey]:
    """Create a new service key and persist its hash.

    Args:
        session: Active SQLModel session.
        name: Human-readable display name (1–80 chars).

    Returns:
        (raw, row) — the raw plaintext key (shown once, never stored) and the
        persisted ServiceAPIKey row.

    Raises:
        ValueError: if name is empty or exceeds SERVICE_KEY_MAX_NAME_LENGTH.
    """
    if not name or len(name) > SERVICE_KEY_MAX_NAME_LENGTH:
        raise ValueError(
            f"Service key name must be between 1 and {SERVICE_KEY_MAX_NAME_LENGTH} characters, "
            f"got {len(name)}."
        )

    raw = f"{SERVICE_KEY_PREFIX}{secrets.token_hex(SERVICE_KEY_RAW_BYTES)}"
    key_hash = _hash(raw)

    row = ServiceAPIKey(
        id=_ulid(),
        name=name,
        key_hash=key_hash,
        key_prefix=raw[:SERVICE_KEY_DISPLAY_PREFIX_LENGTH],
        created_at=datetime.now(UTC),
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return raw, row


def verify_service_key(session: Session, raw_key: str) -> ServiceAPIKey:
    """Verify a raw service key and update last_used_at.

    Args:
        session: Active SQLModel session.
        raw_key: The plaintext key presented by the caller.

    Returns:
        The matching ServiceAPIKey row.

    Raises:
        ServiceKeyNotFoundError: if no row matches the hash or the key is revoked.
            Revoked and missing keys raise the same error to avoid leaking state.
    """
    h = _hash(raw_key)
    row = session.exec(select(ServiceAPIKey).where(ServiceAPIKey.key_hash == h)).first()
    if row is None or row.revoked_at is not None:
        raise ServiceKeyNotFoundError()
    row.last_used_at = datetime.now(UTC)
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def list_service_keys(session: Session, *, include_revoked: bool = False) -> list[ServiceAPIKey]:
    """Return all service keys ordered by created_at.

    Args:
        session: Active SQLModel session.
        include_revoked: When False (default), excludes rows with revoked_at set.

    Returns:
        Ordered list of ServiceAPIKey rows.
    """
    stmt = select(ServiceAPIKey).order_by(ServiceAPIKey.created_at)
    if not include_revoked:
        stmt = stmt.where(ServiceAPIKey.revoked_at.is_(None))  # type: ignore[union-attr]
    return list(session.exec(stmt).all())


def revoke_service_key(session: Session, key_id: str) -> ServiceAPIKey:
    """Set revoked_at on a service key. Idempotent — safe to call twice.

    Args:
        session: Active SQLModel session.
        key_id: The primary-key id of the row to revoke.

    Returns:
        The (now-revoked) ServiceAPIKey row.

    Raises:
        ServiceKeyNotFoundError: if no row exists with the given key_id.
    """
    row = session.get(ServiceAPIKey, key_id)
    if row is None:
        raise ServiceKeyNotFoundError()
    if row.revoked_at is None:
        row.revoked_at = datetime.now(UTC)
        session.add(row)
        session.commit()
        session.refresh(row)
    return row
