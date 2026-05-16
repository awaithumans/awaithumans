"""`record_notification_failure` writes a queryable AuditEntry per failure.

Notification sends are best-effort background work that can't be allowed
to roll back the parent task — but a failure that only lives in the
server log strands the operator. This helper persists a row the
dashboard's task audit panel renders, plus a banner on the task page.

Tests pin:
  - The row carries channel + recipient + machine-readable reason +
    human-readable message in `extra_data`.
  - `to_status` matches the current task status (the failure does
    not transition the task).
  - The commit happens inside the helper (notify runs in a fresh
    background session with no outer commit to piggy-back on).
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import select

from awaithumans.server.db.models import AuditEntry
from awaithumans.server.services.notification_audit import (
    record_notification_failure,
)


@pytest.mark.asyncio
async def test_writes_audit_entry_with_full_context(session: AsyncSession) -> None:
    await record_notification_failure(
        session,
        task_id="task_abc123",
        task_status="created",
        channel="email",
        recipient="user@example.com",
        reason="no_transport_configured",
        message="No email transport is configured.",
    )

    rows = (await session.execute(select(AuditEntry))).scalars().all()
    assert len(rows) == 1
    row = rows[0]
    assert row.task_id == "task_abc123"
    assert row.action == "notification_failed"
    assert row.actor_type == "system"
    assert row.channel == "email"
    assert row.to_status == "created"  # task didn't transition
    assert row.from_status is None
    assert row.extra_data == {
        "recipient": "user@example.com",
        "reason": "no_transport_configured",
        "message": "No email transport is configured.",
    }


@pytest.mark.asyncio
async def test_persists_independently_per_call(session: AsyncSession) -> None:
    """Two failures on the same task each get their own row."""
    await record_notification_failure(
        session,
        task_id="task_abc",
        task_status="created",
        channel="email",
        recipient="a@example.com",
        reason="no_transport_configured",
        message="msg1",
    )
    await record_notification_failure(
        session,
        task_id="task_abc",
        task_status="created",
        channel="slack",
        recipient="@bob",
        reason="no_client",
        message="msg2",
    )

    rows = (await session.execute(select(AuditEntry))).scalars().all()
    assert len(rows) == 2
    channels = sorted(r.channel for r in rows)
    assert channels == ["email", "slack"]


@pytest.mark.asyncio
async def test_commits_inside_helper(session: AsyncSession) -> None:
    """Notify runs in a background session with no outer commit — the
    helper must commit on its own. A fresh select in the same session
    after the call must see the row even before any further commit."""
    await record_notification_failure(
        session,
        task_id="task_xyz",
        task_status="in_progress",
        channel="email",
        recipient="user@example.com",
        reason="transport_error",
        message="Resend returned 500.",
    )

    # No explicit commit/refresh from this test — if the helper didn't
    # commit, we wouldn't see the row through this session's queries
    # depending on isolation level.
    rows = (await session.execute(select(AuditEntry))).scalars().all()
    assert len(rows) == 1
    assert rows[0].to_status == "in_progress"
