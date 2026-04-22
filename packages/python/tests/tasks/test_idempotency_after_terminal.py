"""Regression test: after a task reaches a terminal state, a new task
can be created with the same idempotency key.

The partial unique index on `tasks.idempotency_key` is conditional on
`status NOT IN (...terminal...)`, so terminal rows shouldn't block a
re-insert. Early on the WHERE clause used lowercase values
(`'completed'`) while SQLAlchemy serialized the enum as uppercase
names (`'COMPLETED'`), so the index never excluded anything and the
retry-after-terminal story silently failed with a raw UNIQUE violation.

This test pins that behaviour: create a task, complete it, create
another one with the same key — should succeed and return a distinct
row."""

from __future__ import annotations

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from awaithumans.server.db.models import (  # noqa: F401 — register models
    AuditEntry,
    EmailSenderIdentity,
    SlackInstallation,
    Task,
)
from awaithumans.server.services.task_service import (
    complete_task,
    create_task,
)


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
async def test_retry_after_terminal_with_same_idempotency_key(
    session: AsyncSession,
) -> None:
    # Create #1.
    first = await create_task(
        session,
        task="Approve refund",
        payload={"amount": 100},
        payload_schema={},
        response_schema={},
        timeout_seconds=900,
        idempotency_key="shared-key-xyz",
    )

    # Complete it — status moves to COMPLETED (terminal).
    await complete_task(
        session,
        task_id=first.id,
        response={"approved": True},
        completed_via_channel="test",
    )

    # Create #2 with the same idempotency key. Should succeed and
    # return a DIFFERENT row from the terminal one.
    second = await create_task(
        session,
        task="Approve refund",
        payload={"amount": 100},
        payload_schema={},
        response_schema={},
        timeout_seconds=900,
        idempotency_key="shared-key-xyz",
    )

    assert second.id != first.id
    assert second.status.value == "created"


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_while_active_returns_existing(
    session: AsyncSession,
) -> None:
    """Dedup semantics: while the original task is still non-terminal,
    creating with the same idempotency key returns the same row."""
    first = await create_task(
        session,
        task="Approve refund",
        payload={"amount": 100},
        payload_schema={},
        response_schema={},
        timeout_seconds=900,
        idempotency_key="shared-key-active",
    )

    second = await create_task(
        session,
        task="Approve refund",
        payload={"amount": 100},
        payload_schema={},
        response_schema={},
        timeout_seconds=900,
        idempotency_key="shared-key-active",
    )

    assert second.id == first.id
