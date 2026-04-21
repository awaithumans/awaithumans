"""Per-test installation of PAYLOAD_KEY + DASHBOARD_PASSWORD + isolated DB."""

from __future__ import annotations

import secrets
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from awaithumans.server import db as db_module
from awaithumans.server.core import encryption
from awaithumans.server.core.config import settings


@pytest.fixture(autouse=True)
def _isolated_db() -> Iterator[None]:
    """Route every test in this module to a fresh SQLite tempfile.

    Without this, the TestClient-based tests hit the project's default
    `.awaithumans/dev.db` which may carry stale schema from earlier runs.
    """
    import awaithumans.server.db.connection as conn

    # Snapshot
    original_db_path = settings.DB_PATH
    original_db_url = settings.DATABASE_URL
    original_engine = conn._async_engine
    original_factory = conn._async_session_factory

    tmpdir = tempfile.mkdtemp()
    settings.DB_PATH = str(Path(tmpdir) / "test.db")
    settings.DATABASE_URL = None
    conn._async_engine = None
    conn._async_session_factory = None

    yield

    settings.DB_PATH = original_db_path
    settings.DATABASE_URL = original_db_url
    conn._async_engine = original_engine
    conn._async_session_factory = original_factory


@pytest.fixture
def auth_enabled() -> Iterator[None]:
    """Set a valid PAYLOAD_KEY + DASHBOARD_PASSWORD for the test."""
    original_key = settings.PAYLOAD_KEY
    original_pw = settings.DASHBOARD_PASSWORD
    original_user = settings.DASHBOARD_USER
    settings.PAYLOAD_KEY = secrets.token_urlsafe(32)
    settings.DASHBOARD_PASSWORD = "correct-horse-battery-staple"
    settings.DASHBOARD_USER = "admin"
    encryption.reset_key_cache()
    yield
    settings.PAYLOAD_KEY = original_key
    settings.DASHBOARD_PASSWORD = original_pw
    settings.DASHBOARD_USER = original_user
    encryption.reset_key_cache()


@pytest.fixture
def auth_disabled() -> Iterator[None]:
    """Explicit no-auth mode — DASHBOARD_PASSWORD unset."""
    original = settings.DASHBOARD_PASSWORD
    settings.DASHBOARD_PASSWORD = None
    yield
    settings.DASHBOARD_PASSWORD = original
