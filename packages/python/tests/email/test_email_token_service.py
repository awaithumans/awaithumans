"""Single-use marker for magic-link tokens.

Wire-level "second POST returns 410" is in test_admin_and_action_routes.py.
This file pins the service primitive: the PK constraint catches
concurrent replays at the DB layer."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from awaithumans.server.db.models import (  # noqa: F401 — register models
    AuditEntry,
    ConsumedEmailToken,
    EmailSenderIdentity,
    SlackInstallation,
    Task,
    User,
)
from awaithumans.server.services.email_token_service import try_consume_token


@pytest_asyncio.fixture
async def session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as s:
        yield s
    await engine.dispose()


@pytest.mark.asyncio
async def test_first_consume_returns_true(session: AsyncSession) -> None:
    assert await try_consume_token(session, "jti-fresh") is True


@pytest.mark.asyncio
async def test_second_consume_returns_false(session: AsyncSession) -> None:
    """Replay protection: the same jti can never be consumed twice."""
    assert await try_consume_token(session, "jti-replay") is True
    assert await try_consume_token(session, "jti-replay") is False


@pytest.mark.asyncio
async def test_distinct_jtis_are_independent(session: AsyncSession) -> None:
    assert await try_consume_token(session, "jti-a") is True
    assert await try_consume_token(session, "jti-b") is True
    # Both blocked on replay, independently.
    assert await try_consume_token(session, "jti-a") is False
    assert await try_consume_token(session, "jti-b") is False
