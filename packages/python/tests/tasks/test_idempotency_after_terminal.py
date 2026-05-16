"""Stripe-style idempotency: same key always returns the same task.

While the task is active this gives in-flight dedup; after the task
is terminal it gives recovery — a restarted agent that re-invokes
`await_human()` with the same key gets the stored response (for
COMPLETED) or the typed terminal error (for TIMED_OUT / CANCELLED /
VERIFICATION_EXHAUSTED), instead of creating a duplicate.

Pre-Option-A this file pinned the opposite behavior — terminal keys
allowed a fresh task. That deviation from the documented Stripe model
is what made direct-mode `await_human()` lose the human's response on
agent restart. The new tests pin the corrected contract."""

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
    TaskStatus,
)
from awaithumans.server.services.task_service import (
    cancel_task,
    complete_task,
    create_task,
    timeout_task,
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


async def _make(session: AsyncSession, key: str) -> Task:
    task, _ = await create_task(
        session,
        task="Approve refund",
        payload={"amount": 100},
        payload_schema={},
        response_schema={},
        timeout_seconds=900,
        idempotency_key=key,
    )
    return task


@pytest.mark.asyncio
async def test_duplicate_idempotency_key_while_active_returns_existing(
    session: AsyncSession,
) -> None:
    """In-flight dedup: while the task is non-terminal, the same key
    returns the same row. Pins the unchanged half of the contract."""
    first = await _make(session, "shared-key-active")
    second = await _make(session, "shared-key-active")
    assert second.id == first.id
    assert second.status == TaskStatus.CREATED


@pytest.mark.asyncio
async def test_recover_after_completed_returns_existing_with_response(
    session: AsyncSession,
) -> None:
    """The recovery path. An agent that crashed mid-`await_human()`
    while a human was reviewing comes back up, the human has already
    submitted, and the agent re-calls with the same key. It MUST get
    the stored response back, not a fresh blank task."""
    first = await _make(session, "shared-key-completed")
    completed = await complete_task(
        session,
        task_id=first.id,
        response={"approved": True, "reason": "policy match"},
        completed_via_channel="test",
    )
    assert completed.status == TaskStatus.COMPLETED

    recovered = await _make(session, "shared-key-completed")
    assert recovered.id == first.id
    assert recovered.status == TaskStatus.COMPLETED
    assert recovered.response == {"approved": True, "reason": "policy match"}


@pytest.mark.asyncio
async def test_recover_after_timed_out_returns_existing_terminal_task(
    session: AsyncSession,
) -> None:
    """Recovery for TIMED_OUT: re-call returns the same terminal task,
    SDK's poll-branch translates it into TaskTimeoutError. Critically,
    we do NOT silently create a fresh task — that would mean the agent
    starts a SECOND human ticket for an event the first cycle already
    timed out on."""
    first = await _make(session, "shared-key-timed-out")
    await timeout_task(session, first.id)
    await session.refresh(first)
    assert first.status == TaskStatus.TIMED_OUT

    recovered = await _make(session, "shared-key-timed-out")
    assert recovered.id == first.id
    assert recovered.status == TaskStatus.TIMED_OUT


@pytest.mark.asyncio
async def test_recover_after_cancelled_returns_existing_terminal_task(
    session: AsyncSession,
) -> None:
    """Recovery for CANCELLED. SDK's poll-branch raises TaskCancelledError."""
    first = await _make(session, "shared-key-cancelled")
    await cancel_task(session, first.id)
    await session.refresh(first)
    assert first.status == TaskStatus.CANCELLED

    recovered = await _make(session, "shared-key-cancelled")
    assert recovered.id == first.id
    assert recovered.status == TaskStatus.CANCELLED


@pytest.mark.asyncio
async def test_distinct_keys_create_distinct_tasks(
    session: AsyncSession,
) -> None:
    """The escape hatch: callers who genuinely want a fresh task for
    the same logical event use a distinct key (e.g. an explicit
    retry-counter suffix). Pin that path so re-review workflows
    documented in `docs/concepts/idempotency.mdx` keep working."""
    first = await _make(session, "shared-key:original")
    await complete_task(
        session,
        task_id=first.id,
        response={"approved": True},
        completed_via_channel="test",
    )

    second = await _make(session, "shared-key:retry-1")
    assert second.id != first.id
    assert second.status == TaskStatus.CREATED


# ─── was_newly_created signal ─────────────────────────────────────────


@pytest.mark.asyncio
async def test_create_task_signals_new_creation_on_first_call(
    session: AsyncSession,
) -> None:
    """First call with a fresh idempotency key returns was_newly_created=True
    so the route knows to fire notify."""
    _, was_newly_created = await create_task(
        session,
        task="Approve refund",
        payload={"amount": 100},
        payload_schema={},
        response_schema={},
        timeout_seconds=900,
        idempotency_key="fresh-key-1",
    )
    assert was_newly_created is True


@pytest.mark.asyncio
async def test_create_task_signals_existing_on_duplicate_key(
    session: AsyncSession,
) -> None:
    """Same key on a second call returns was_newly_created=False — this is
    the gate the route uses to avoid re-sending notification emails /
    Slack pings on every agent retry of the same logical task. Before
    this signal existed, every `await_human()` retry re-emailed the
    reviewer for an already-in-flight task. Bug reported by test user
    who got a duplicate email on a retry attempt."""
    _, first_was_new = await create_task(
        session,
        task="Approve refund",
        payload={"amount": 100},
        payload_schema={},
        response_schema={},
        timeout_seconds=900,
        idempotency_key="duplicate-key-2",
    )
    _, second_was_new = await create_task(
        session,
        task="Approve refund",
        payload={"amount": 100},
        payload_schema={},
        response_schema={},
        timeout_seconds=900,
        idempotency_key="duplicate-key-2",
    )
    assert first_was_new is True
    assert second_was_new is False


@pytest.mark.asyncio
async def test_create_task_signals_existing_after_terminal(
    session: AsyncSession,
) -> None:
    """A terminal task (timed_out/completed/cancelled) returned via
    idempotency key still reports was_newly_created=False — the route
    must not re-notify even when the agent is "resuming" against a
    completed task."""
    first, first_was_new = await create_task(
        session,
        task="Approve refund",
        payload={"amount": 100},
        payload_schema={},
        response_schema={},
        timeout_seconds=900,
        idempotency_key="terminal-key-3",
    )
    await timeout_task(session, first.id)

    _, second_was_new = await create_task(
        session,
        task="Approve refund",
        payload={"amount": 100},
        payload_schema={},
        response_schema={},
        timeout_seconds=900,
        idempotency_key="terminal-key-3",
    )
    assert first_was_new is True
    assert second_was_new is False
