"""Shared fixtures for Slack tests that need a DB session."""

from __future__ import annotations

import secrets
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from awaithumans.server.core import encryption
from awaithumans.server.core.config import settings

# Importing the models registers them on SQLModel.metadata so create_all works.
from awaithumans.server.db.models import (  # noqa: F401
    AuditEntry,
    SlackInstallation,
    Task,
)


@pytest.fixture(autouse=True)
def _encryption_key() -> None:
    """Install a valid 32-byte key for every Slack test.

    SlackInstallation.bot_token is an EncryptedString column — without a key
    configured, upserts raise EncryptionNotConfiguredError. Tests that want
    to exercise the missing-key path can swap it themselves.
    """
    original = settings.PAYLOAD_KEY
    settings.PAYLOAD_KEY = secrets.token_urlsafe(32)
    encryption.reset_key_cache()
    yield
    settings.PAYLOAD_KEY = original
    encryption.reset_key_cache()


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    """Fresh in-memory SQLite DB per test — isolated, no file I/O."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s

    await engine.dispose()
