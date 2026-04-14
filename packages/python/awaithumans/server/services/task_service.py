"""Task lifecycle service — core business logic."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.server.db.models import (
    AuditEntry,
    Task,
    TaskStatus,
    TERMINAL_STATUSES,
)


class TaskAlreadyExistsError(Exception):
    """Raised when a task with the same idempotency key already exists and is non-terminal."""

    def __init__(self, existing_task: Task) -> None:
        self.existing_task = existing_task
        super().__init__(f"Task with idempotency key '{existing_task.idempotency_key}' already exists.")


class TaskNotFoundError(Exception):
    """Raised when a task is not found."""

    def __init__(self, task_id: str) -> None:
        self.task_id = task_id
        super().__init__(f"Task '{task_id}' not found.")


class TaskAlreadyTerminalError(Exception):
    """Raised when trying to modify a task that is already in a terminal state."""

    def __init__(self, task_id: str, status: TaskStatus) -> None:
        self.task_id = task_id
        self.status = status
        super().__init__(f"Task '{task_id}' is already in terminal status '{status.value}'.")


async def create_task(
    session: AsyncSession,
    *,
    task: str,
    payload: dict,
    payload_schema: dict,
    response_schema: dict,
    timeout_seconds: int,
    idempotency_key: str,
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

    # Create the task
    new_task = Task(
        task=task,
        payload=payload,
        payload_schema=payload_schema,
        response_schema=response_schema,
        timeout_seconds=timeout_seconds,
        idempotency_key=idempotency_key,
        assign_to=assign_to,
        notify=notify,
        verifier_config=verifier_config,
        redact_payload=redact_payload,
        callback_url=callback_url,
        status=TaskStatus.CREATED,
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

    await session.commit()
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

    if task.status in TERMINAL_STATUSES:
        raise TaskAlreadyTerminalError(task_id, task.status)

    now = datetime.now(timezone.utc)

    # Atomic update — only succeeds if status is still non-terminal
    result = await session.execute(
        update(Task)
        .where(Task.id == task_id)
        .where(Task.status.notin_([s.value for s in TERMINAL_STATUSES]))
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
        metadata={"response_keys": list(response.keys())} if response else None,
    )
    session.add(audit)
    await session.commit()

    await session.refresh(task)
    return task


async def timeout_task(session: AsyncSession, task_id: str) -> Task:
    """Mark a task as timed out. Called by the timeout scheduler."""
    task = await get_task(session, task_id)

    if task.status in TERMINAL_STATUSES:
        return task  # Already terminal, no-op

    now = datetime.now(timezone.utc)

    result = await session.execute(
        update(Task)
        .where(Task.id == task_id)
        .where(Task.status.notin_([s.value for s in TERMINAL_STATUSES]))
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
        metadata={"timeout_seconds": task.timeout_seconds},
    )
    session.add(audit)
    await session.commit()

    await session.refresh(task)
    return task


async def cancel_task(session: AsyncSession, task_id: str) -> Task:
    """Cancel a task. Called by the agent or admin."""
    task = await get_task(session, task_id)

    if task.status in TERMINAL_STATUSES:
        raise TaskAlreadyTerminalError(task_id, task.status)

    now = datetime.now(timezone.utc)

    await session.execute(
        update(Task)
        .where(Task.id == task_id)
        .where(Task.status.notin_([s.value for s in TERMINAL_STATUSES]))
        .values(
            status=TaskStatus.CANCELLED,
            updated_at=now,
        )
    )

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
        .where(Task.status.notin_([s.value for s in TERMINAL_STATUSES]))
    )
    return result.scalar_one_or_none()
