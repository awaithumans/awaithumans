"""Task lifecycle service — core business logic.

Pure business logic. No HTTP, no routes, no framework concerns.
Raises domain exceptions from services/exceptions.py.

Verifier integration lives in `task_verifier.py`; this file only
sequences the lifecycle operations and the verifier-aware UPDATE.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.server.db.models import AuditEntry, Task, TaskStatus
from awaithumans.server.services.exceptions import (
    TaskAlreadyClaimedError,
    TaskAlreadyTerminalError,
    TaskNotFoundError,
)
from awaithumans.server.services.task_router import (
    derive_implicit_assignee,
    resolve_assign_to,
)
from awaithumans.server.services.task_verifier import (
    VerifierOutcome,
    audit_action_for,
    evaluate_submission,
)
from awaithumans.utils.constants import TERMINAL_STATUSES_SET

logger = logging.getLogger("awaithumans.server.services.task_service")


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

    # If the developer didn't pin an assignee but DID `notify=` a
    # specific person via Slack, treat that person as the assignee.
    # `notify=["slack:@alice"]` is the natural shorthand for "alice
    # is responsible" — without this, alice gets DMed but the
    # dashboard's "Assigned to" stays empty AND the Slack auth
    # check rejects her submission. See `derive_implicit_assignee`.
    if route.user_id is None and route.email is None:
        implicit = await derive_implicit_assignee(session, notify)
        if implicit.user_id is not None or implicit.email is not None:
            route = implicit

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
    assigned_to_user_id: str | None = None,
    limit: int = 50,
    offset: int = 0,
) -> list[Task]:
    """List tasks with optional filters.

    `assigned_to_user_id` is the authoritative scope for non-operator
    callers — it filters on the resolved directory user ID stamped at
    routing time, which is stable across email changes and works for
    Slack-only users (where `assigned_to_email` is null)."""
    query = select(Task).order_by(Task.created_at.desc()).limit(limit).offset(offset)
    if status is not None:
        query = query.where(Task.status == status)
    if assigned_to_email is not None:
        query = query.where(Task.assigned_to_email == assigned_to_email)
    if assigned_to_user_id is not None:
        query = query.where(Task.assigned_to_user_id == assigned_to_user_id)
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
    completed_by_user_id: str | None = None,
    completed_via_channel: str | None = None,
    raw_input: str | None = None,
) -> Task:
    """Complete a task with the human's response.

    First-writer-wins: if the task is already terminal (e.g., timed out),
    raises TaskAlreadyTerminalError.

    If `task.verifier_config` is set, the response is run through the
    server-side verifier before deciding the final status. The verifier
    does two things in one LLM call:

      - quality-check the response against the operator's `instructions`
      - parse `raw_input` (NL reply) into a structured `parsed_response`
        when no structured response was submitted

    Outcomes:
      - verifier passes → status COMPLETED, response stored (parsed if NL)
      - verifier rejects, attempts left → status REJECTED (non-terminal),
        attempt counter bumped, verifier_result kept; the human can
        resubmit and the channel layer surfaces the reason to them
      - verifier rejects, attempts exhausted → status VERIFICATION_EXHAUSTED
        (terminal); the agent is unblocked with a typed exhaustion error

    Provider-level failures (missing API key, vendor outage, missing
    SDK extra) propagate as ServiceError subclasses — they do NOT
    consume a retry attempt because the LLM never actually rendered a
    verdict. The caller's HTTP request fails; the human can retry by
    resubmitting once the operator fixes the config.
    """
    task = await get_task(session, task_id)

    if task.status in TERMINAL_STATUSES_SET:
        raise TaskAlreadyTerminalError(task_id, task.status)

    verifier_outcome: VerifierOutcome | None = None
    final_response = response
    if task.verifier_config and not task.redact_payload:
        # We do NOT ship redacted-task payloads to a third-party LLM
        # under any circumstance — the operator marked the payload
        # sensitive, and the verifier prompt would carry that same
        # payload off-server. Skip verification for redacted tasks;
        # the submission is treated as if no verifier were configured.

        # Snapshot the fields the verifier needs into a detached
        # `Task` instance BEFORE releasing the session, then commit to
        # release the DB connection back to the pool. Verifier round-
        # trips can take 5-30s; holding the connection in a transaction
        # would exhaust the pool on a moderately-loaded instance.
        #
        # Snapshotting (rather than reading task attrs after commit)
        # decouples the verifier-path correctness from
        # `expire_on_commit` / `expire_on_rollback` session config.
        # Anyone flipping those flags in `db/connection.py` or in a
        # test fixture can no longer silently break this code path —
        # the verifier sees a frozen copy of the task as it was at
        # submission time.
        task_snapshot = _snapshot_task_for_verifier(task)
        await session.commit()
        verifier_outcome = await evaluate_submission(
            task_snapshot, response=response, raw_input=raw_input
        )
        if verifier_outcome.parsed_response is not None:
            # NL parse path — the structured value the agent receives is
            # whatever the verifier extracted, not the raw form data
            # (which was likely empty when raw_input was the input).
            final_response = verifier_outcome.parsed_response

    now = datetime.now(timezone.utc)
    target_status = verifier_outcome.target_status if verifier_outcome else TaskStatus.COMPLETED

    update_values: dict[str, Any] = {
        "status": target_status,
        "response": final_response,
        "updated_at": now,
        "completed_by_email": completed_by_email,
        "completed_by_user_id": completed_by_user_id,
        "completed_via_channel": completed_via_channel,
    }
    # Only stamp completed_at on actual completion. REJECTED is
    # non-terminal — leaving completed_at null lets the dashboard
    # render "in review" correctly across a rejection cycle.
    if target_status == TaskStatus.COMPLETED:
        update_values["completed_at"] = now
    if verifier_outcome is not None:
        update_values["verifier_result"] = verifier_outcome.result.model_dump()
        update_values["verification_attempt"] = verifier_outcome.new_attempt

    # Atomic update — only succeeds if status is still non-terminal.
    # Note: verification can take seconds (LLM call) before we get here;
    # if the task got cancelled / timed-out during the verifier call,
    # this safely no-ops via the rowcount check.
    result = await session.execute(
        update(Task)
        .where(Task.id == task_id)
        .where(Task.status.notin_(list(TERMINAL_STATUSES_SET)))
        .values(**update_values)
    )

    if result.rowcount == 0:
        # Race condition: another writer got there first
        await session.refresh(task)
        raise TaskAlreadyTerminalError(task_id, task.status)

    # Audit entry — one per submission. When the verifier rejected,
    # we record the rejection action AND the reason so the audit trail
    # tells the full story without joining against verifier_result.
    audit_action = audit_action_for(target_status, verifier_outcome)
    audit_extra: dict[str, Any] = {}
    # Honour `redact_payload` here too — the audit trail is operator-
    # facing but ends up in logs, exports, and the dashboard. When the
    # operator said "redact this payload", that includes derived field
    # names. response_keys is marginal observability vs PII risk.
    if response and not task.redact_payload:
        audit_extra["response_keys"] = list(response.keys())
    if verifier_outcome is not None:
        audit_extra["verifier_passed"] = verifier_outcome.result.passed
        audit_extra["verification_attempt"] = verifier_outcome.new_attempt
        if not task.redact_payload:
            # Reason can quote payload back at us; gate on redaction.
            audit_extra["verifier_reason"] = verifier_outcome.result.reason

    audit = AuditEntry(
        task_id=task_id,
        from_status=task.status.value,
        to_status=target_status.value,
        action=audit_action,
        actor_type="human",
        actor_email=completed_by_email,
        channel=completed_via_channel,
        extra_data=audit_extra or None,
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


def _snapshot_task_for_verifier(task: Task) -> Task:
    """Build a detached `Task` carrying only the fields the verifier
    reads.

    The verifier path commits/closes the session before running the
    LLM call (see `complete_task`). After the commit, accessing
    attributes on the original ORM instance is technically still safe
    because the session factory pins `expire_on_commit=False`, but
    that's a fragile coupling — anyone flipping the flag in
    `db/connection.py` or a test fixture would silently break this
    code path. Snapshotting decouples the two concerns: we read the
    fields once while the session is unambiguously alive, then pass a
    plain Python object across the LLM-call boundary.

    Fields included match what `task_verifier.evaluate_submission`
    actually reads (verifier_config, payload, schemas, attempt
    counter, prior verifier_result, status, id, task description).
    """
    return Task(
        id=task.id,
        idempotency_key=task.idempotency_key,
        task=task.task,
        payload=task.payload,
        payload_schema=task.payload_schema,
        response_schema=task.response_schema,
        status=task.status,
        verifier_config=task.verifier_config,
        verifier_result=task.verifier_result,
        verification_attempt=task.verification_attempt,
        timeout_seconds=task.timeout_seconds,
        redact_payload=task.redact_payload,
    )


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


# Verifier helpers (`evaluate_submission`, `audit_action_for`,
# `previous_rejections_for`, `VerifierOutcome`) live in
# `task_verifier.py` — kept out of this file to stay under the 300-line
# file cap and isolate the LLM-call path from core lifecycle logic.
