"""Task lifecycle service — core business logic.

Pure business logic. No HTTP, no routes, no framework concerns.
Raises domain exceptions from services/exceptions.py.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.server.db.models import AuditEntry, Task, TaskStatus
from awaithumans.server.services.exceptions import (
    TaskAlreadyClaimedError,
    TaskAlreadyTerminalError,
    TaskNotFoundError,
)
from awaithumans.server.services.task_router import resolve_assign_to
from awaithumans.utils.constants import TERMINAL_STATUSES_SET


async def create_task(
    session: AsyncSession,
    *,
    task: str,
    payload: dict,
    payload_schema: dict,
    response_schema: dict,
    timeout_seconds: int,
    idempotency_key: str,
    form_definition: dict | None = None,
    assign_to: dict | None = None,
    notify: list[str] | None = None,
    verifier_config: dict | None = None,
    redact_payload: bool = False,
    callback_url: str | None = None,
) -> Task:
    """Create a new task, or return the existing one if idempotency key matches.

    If a non-terminal task with the same idempotency key exists, returns it
    (dedup behavior). If the existing task is terminal, creates a new one.
    """
    # Check for existing task with same idempotency key
    existing = await _find_active_task_by_idempotency_key(session, idempotency_key)
    if existing is not None:
        return existing

    # Route: resolve assign_to -> a specific user (or None for unassigned).
    # The router bumps last_assigned_at on the picked user within this
    # session; committing the task and the bump together keeps Option C
    # fairness in step with task creation.
    route = await resolve_assign_to(session, assign_to)

    # Create the task
    now = datetime.now(timezone.utc)
    new_task = Task(
        task=task,
        payload=payload,
        payload_schema=payload_schema,
        response_schema=response_schema,
        form_definition=form_definition,
        timeout_seconds=timeout_seconds,
        idempotency_key=idempotency_key,
        assign_to=assign_to,
        assigned_to_email=route.email,
        assigned_to_user_id=route.user_id,
        notify=notify,
        verifier_config=verifier_config,
        redact_payload=redact_payload,
        callback_url=callback_url,
        status=TaskStatus.CREATED,
        created_at=now,
        updated_at=now,
        timeout_at=now + timedelta(seconds=timeout_seconds),
    )
    session.add(new_task)

    # Audit entry
    audit = AuditEntry(
        task_id=new_task.id,
        from_status=None,
        to_status=TaskStatus.CREATED.value,
        action="created",
        actor_type="agent",
    )
    session.add(audit)

    try:
        await session.commit()
    except IntegrityError:
        # Race condition: another request inserted with the same idempotency key
        # between our SELECT and INSERT. Roll back and return the existing task.
        await session.rollback()
        existing = await _find_active_task_by_idempotency_key(session, idempotency_key)
        if existing is not None:
            return existing
        # The existing task went terminal between our attempts — re-raise
        raise

    await session.refresh(new_task)
    return new_task


async def get_task(session: AsyncSession, task_id: str) -> Task:
    """Get a task by ID. Raises TaskNotFoundError if not found."""
    result = await session.execute(select(Task).where(Task.id == task_id))
    task = result.scalar_one_or_none()
    if task is None:
        raise TaskNotFoundError(task_id)
    return task


async def list_tasks(
    session: AsyncSession,
    *,
    status: TaskStatus | None = None,
    assigned_to_email: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Task]:
    """List tasks with optional filters."""
    query = select(Task).order_by(Task.created_at.desc()).limit(limit).offset(offset)
    if status is not None:
        query = query.where(Task.status == status)
    if assigned_to_email is not None:
        query = query.where(Task.assigned_to_email == assigned_to_email)
    result = await session.execute(query)
    return list(result.scalars().all())


async def claim_task(
    session: AsyncSession,
    *,
    task_id: str,
    user_id: str,
    user_email: str | None = None,
    claimed_via_channel: str | None = None,
) -> Task:
    """Claim a broadcast task (first-writer-wins).

    Used when a task was posted to a channel with no specific assignee
    and a human clicked "Claim." Atomic `UPDATE ... WHERE
    assigned_to_user_id IS NULL` — second clicker sees
    `TaskAlreadyClaimedError` and the caller surfaces an ephemeral
    "already claimed by X" to them.

    `claimed_via_channel` is a free-form string ("slack", "dashboard",
    "email") mirroring `completed_via_channel` so audit trails stay
    consistent across lifecycle events.

    Raises `TaskNotFoundError` if no such task, `TaskAlreadyTerminalError`
    if it's already completed/cancelled/timed-out (a stale message from
    before a completion on another channel), `TaskAlreadyClaimedError`
    if another user beat us to it.
    """
    task = await get_task(session, task_id)

    if task.status in TERMINAL_STATUSES_SET:
        raise TaskAlreadyTerminalError(task_id, task.status)

    # Fast-path: already claimed by someone.
    if task.assigned_to_user_id is not None:
        raise TaskAlreadyClaimedError(task_id, task.assigned_to_user_id)

    now = datetime.now(timezone.utc)
    result = await session.execute(
        update(Task)
        .where(Task.id == task_id)
        .where(Task.assigned_to_user_id.is_(None))
        .where(Task.status.notin_(list(TERMINAL_STATUSES_SET)))
        .values(
            assigned_to_user_id=user_id,
            assigned_to_email=user_email,
            updated_at=now,
        )
    )

    if result.rowcount == 0:
        # Race: another claimer committed between our SELECT and UPDATE.
        # Re-read to tell the loser who actually won.
        await session.refresh(task)
        if task.assigned_to_user_id is not None:
            raise TaskAlreadyClaimedError(task_id, task.assigned_to_user_id)
        if task.status in TERMINAL_STATUSES_SET:
            raise TaskAlreadyTerminalError(task_id, task.status)
        # Shouldn't happen, but don't leave the caller guessing.
        raise TaskAlreadyClaimedError(task_id, None)

    audit = AuditEntry(
        task_id=task_id,
        from_status=task.status.value,
        to_status=task.status.value,  # claim doesn't change status
        action="claimed",
        actor_type="human",
        actor_email=user_email,
        channel=claimed_via_channel,
        extra_data={"user_id": user_id},
    )
    session.add(audit)
    await session.commit()

    await session.refresh(task)
    return task


async def complete_task(
    session: AsyncSession,
    *,
    task_id: str,
    response: dict,
    completed_by_email: str | None = None,
    completed_via_channel: str | None = None,
) -> Task:
    """Complete a task with the human's response.

    Uses first-writer-wins: if the task is already terminal (e.g., timed out),
    raises TaskAlreadyTerminalError.
    """
    task = await get_task(session, task_id)

    if task.status in TERMINAL_STATUSES_SET:
        raise TaskAlreadyTerminalError(task_id, task.status)

    now = datetime.now(timezone.utc)

    # Atomic update — only succeeds if status is still non-terminal
    result = await session.execute(
        update(Task)
        .where(Task.id == task_id)
        .where(Task.status.notin_(list(TERMINAL_STATUSES_SET)))
        .values(
            status=TaskStatus.COMPLETED,
            response=response,
            completed_at=now,
            updated_at=now,
            completed_by_email=completed_by_email,
            completed_via_channel=completed_via_channel,
        )
    )

    if result.rowcount == 0:
        # Race condition: another writer got there first
        await session.refresh(task)
        raise TaskAlreadyTerminalError(task_id, task.status)

    # Audit entry
    audit = AuditEntry(
        task_id=task_id,
        from_status=task.status.value,
        to_status=TaskStatus.COMPLETED.value,
        action="completed",
        actor_type="human",
        actor_email=completed_by_email,
        channel=completed_via_channel,
        extra_data={"response_keys": list(response.keys())} if response else None,
    )
    session.add(audit)
    await session.commit()

    await session.refresh(task)
    return task


async def timeout_task(session: AsyncSession, task_id: str) -> Task:
    """Mark a task as timed out. Called by the timeout scheduler."""
    task = await get_task(session, task_id)

    if task.status in TERMINAL_STATUSES_SET:
        return task  # Already terminal, no-op

    now = datetime.now(timezone.utc)

    result = await session.execute(
        update(Task)
        .where(Task.id == task_id)
        .where(Task.status.notin_(list(TERMINAL_STATUSES_SET)))
        .values(
            status=TaskStatus.TIMED_OUT,
            timed_out_at=now,
            updated_at=now,
        )
    )

    if result.rowcount == 0:
        await session.refresh(task)
        return task  # Race condition — someone completed it first, that's fine

    audit = AuditEntry(
        task_id=task_id,
        from_status=task.status.value,
        to_status=TaskStatus.TIMED_OUT.value,
        action="timed_out",
        actor_type="system",
        extra_data={"timeout_seconds": task.timeout_seconds},
    )
    session.add(audit)
    await session.commit()

    await session.refresh(task)
    return task


async def cancel_task(session: AsyncSession, task_id: str) -> Task:
    """Cancel a task. Called by the agent or admin."""
    task = await get_task(session, task_id)

    if task.status in TERMINAL_STATUSES_SET:
        raise TaskAlreadyTerminalError(task_id, task.status)

    now = datetime.now(timezone.utc)

    result = await session.execute(
        update(Task)
        .where(Task.id == task_id)
        .where(Task.status.notin_(list(TERMINAL_STATUSES_SET)))
        .values(
            status=TaskStatus.CANCELLED,
            updated_at=now,
        )
    )

    if result.rowcount == 0:
        # Race condition: task was completed/timed out between our check and update
        await session.refresh(task)
        raise TaskAlreadyTerminalError(task_id, task.status)

    audit = AuditEntry(
        task_id=task_id,
        from_status=task.status.value,
        to_status=TaskStatus.CANCELLED.value,
        action="cancelled",
        actor_type="agent",
    )
    session.add(audit)
    await session.commit()

    await session.refresh(task)
    return task


async def delete_task(session: AsyncSession, task_id: str) -> bool:
    """Hard delete a task row. Operator-only surface.

    Unlike `cancel_task` (which moves the task to a terminal CANCELLED
    state but keeps the row for history), this actually removes the row
    from the table. Audit entries are left in place, orphaned — they're
    a historical record of what happened to a task that no longer exists,
    and dropping them would erase evidence the operator may later need.

    Returns True if a row was removed, False if the task_id didn't exist.
    """
    result = await session.execute(delete(Task).where(Task.id == task_id))
    await session.commit()
    return result.rowcount > 0


async def get_audit_trail(session: AsyncSession, task_id: str) -> list[AuditEntry]:
    """Get the full audit trail for a task."""
    result = await session.execute(
        select(AuditEntry)
        .where(AuditEntry.task_id == task_id)
        .order_by(AuditEntry.created_at.asc())
    )
    return list(result.scalars().all())


async def _find_active_task_by_idempotency_key(
    session: AsyncSession, idempotency_key: str
) -> Task | None:
    """Find a non-terminal task with the given idempotency key."""
    result = await session.execute(
        select(Task)
        .where(Task.idempotency_key == idempotency_key)
        .where(Task.status.notin_(list(TERMINAL_STATUSES_SET)))
    )
    return result.scalar_one_or_none()
