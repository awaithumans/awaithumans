"""Tests for service_key_service CRUD and verification.

All tests use an in-memory SQLite engine + Session fixture — no FastAPI, no
real DB connection.

Covered:
  1. create_service_key returns (raw, row); raw starts with ah_sk_, len > 20.
  2. row.key_hash != raw; row.key_prefix == raw[:12]; row.name == "acme-prod".
  3. verify_service_key(raw) round-trips to the same row.
  4. verify_service_key("ah_sk_doesnotexist") raises ServiceKeyNotFoundError.
  5. revoking then verifying raises ServiceKeyNotFoundError.
  6. list_service_keys(include_revoked=False) excludes revoked rows.
  7. list_service_keys(include_revoked=True) includes revoked rows.
  8. oversize name (> 80 chars) raises ValueError.
"""

from __future__ import annotations

import pytest
from sqlmodel import Session, SQLModel, create_engine

from awaithumans.server.services.exceptions import ServiceKeyNotFoundError
from awaithumans.server.services.service_key_service import (
    create_service_key,
    list_service_keys,
    revoke_service_key,
    verify_service_key,
)
from awaithumans.utils.constants import SERVICE_KEY_DISPLAY_PREFIX_LENGTH, SERVICE_KEY_PREFIX


@pytest.fixture
def session() -> Session:  # type: ignore[return]
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s  # type: ignore[misc]


# ── 1 & 2: create_service_key shape ──────────────────────────────────────────


def test_create_returns_raw_and_row(session: Session) -> None:
    """create_service_key returns (raw, row); raw has correct prefix and length."""
    raw, row = create_service_key(session, name="acme-prod")

    assert raw.startswith(SERVICE_KEY_PREFIX)
    assert len(raw) > 20
    assert row.key_hash != raw
    assert row.key_prefix == raw[:SERVICE_KEY_DISPLAY_PREFIX_LENGTH]
    assert row.name == "acme-prod"
    assert row.id is not None
    assert row.created_at is not None
    assert row.last_used_at is None
    assert row.revoked_at is None


# ── 3: verify round-trip ──────────────────────────────────────────────────────


def test_verify_round_trips_to_row(session: Session) -> None:
    """verify_service_key(raw) returns the same row and updates last_used_at."""
    raw, created_row = create_service_key(session, name="round-trip")

    verified_row = verify_service_key(session, raw)

    assert verified_row.id == created_row.id
    assert verified_row.name == created_row.name
    assert verified_row.last_used_at is not None


# ── 4: verify unknown key ─────────────────────────────────────────────────────


def test_verify_unknown_key_raises(session: Session) -> None:
    """verify_service_key with an unknown raw key raises ServiceKeyNotFoundError."""
    with pytest.raises(ServiceKeyNotFoundError):
        verify_service_key(session, "ah_sk_doesnotexist")


# ── 5: revoke then verify ─────────────────────────────────────────────────────


def test_revoked_key_raises_on_verify(session: Session) -> None:
    """Revoking a key then verifying it raises ServiceKeyNotFoundError."""
    raw, row = create_service_key(session, name="to-revoke")

    revoke_service_key(session, row.id)

    with pytest.raises(ServiceKeyNotFoundError):
        verify_service_key(session, raw)


# ── 6: list excludes revoked by default ──────────────────────────────────────


def test_list_excludes_revoked_by_default(session: Session) -> None:
    """list_service_keys(include_revoked=False) omits revoked rows."""
    _raw1, active_row = create_service_key(session, name="active")
    _raw2, revoked_row = create_service_key(session, name="revoked")
    revoke_service_key(session, revoked_row.id)

    results = list_service_keys(session, include_revoked=False)
    ids = [r.id for r in results]

    assert active_row.id in ids
    assert revoked_row.id not in ids


# ── 7: list includes revoked when flag is True ────────────────────────────────


def test_list_includes_revoked_when_flag_set(session: Session) -> None:
    """list_service_keys(include_revoked=True) includes revoked rows."""
    _raw1, active_row = create_service_key(session, name="active2")
    _raw2, revoked_row = create_service_key(session, name="revoked2")
    revoke_service_key(session, revoked_row.id)

    results = list_service_keys(session, include_revoked=True)
    ids = [r.id for r in results]

    assert active_row.id in ids
    assert revoked_row.id in ids


# ── 8: oversize name raises ValueError ───────────────────────────────────────


def test_oversize_name_raises_value_error(session: Session) -> None:
    """A name longer than 80 chars raises ValueError."""
    bad_name = "x" * 81
    with pytest.raises(ValueError):
        create_service_key(session, name=bad_name)
