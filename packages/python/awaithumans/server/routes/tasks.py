"""Task API routes — CRUD, long-poll, completion.

Route handlers only. All request/response models live in server/schemas.py.
Service exceptions (TaskNotFoundError, etc.) propagate to the centralized
handler in core/exceptions.py — no try/except in routes.
"""

from __future__ import annotations

import asyncio
import logging

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Request
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.server.channels.email import notify_task as notify_task_email
from awaithumans.server.channels.slack import notify_task as notify_task_slack
from awaithumans.server.db.connection import get_session
from awaithumans.server.db.models import Task, TaskStatus
from awaithumans.server.schemas import (
    AuditEntryResponse,
    CompleteTaskRequest,
    CreateTaskRequest,
    PollResponse,
    TaskResponse,
)
from awaithumans.server.core.admin_auth import require_admin
from awaithumans.server.core.auth import SessionClaims
from awaithumans.server.services.exceptions import TaskNotFoundError
from awaithumans.server.services.user_service import get_user
from awaithumans.server.services.task_service import (
    cancel_task,
    delete_task,
    complete_task,
    create_task,
    get_audit_trail,
    get_task,
    list_tasks,
)
from awaithumans.utils.constants import TERMINAL_STATUSES_SET

router = APIRouter(prefix="/tasks", tags=["tasks"])
logger = logging.getLogger("awaithumans.server.routes.tasks")


# ─── Helper ──────────────────────────────────────────────────────────────


def _task_to_response(task: Task, *, redact: bool = False) -> TaskResponse:
    """Convert a Task model to a TaskResponse, optionally redacting payload."""
    data = TaskResponse.model_validate(task)
    if redact and task.redact_payload:
        data.payload = {"_redacted": True}
    return data


# ─── Routes ──────────────────────────────────────────────────────────────


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task_route(
    body: CreateTaskRequest,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """Create a new HITL task (or return existing if idempotency key matches).

    Channel notifications fire in a FastAPI BackgroundTask *after* the
    response is sent, so a slow Slack API call never blocks task creation
    and a Slack outage never fails a successful task write.
    """
    task = await create_task(
        session,
        task=body.task,
        payload=body.payload,
        payload_schema=body.payload_schema,
        response_schema=body.response_schema,
        form_definition=body.form_definition,
        timeout_seconds=body.timeout_seconds,
        idempotency_key=body.idempotency_key,
        assign_to=body.assign_to,
        notify=body.notify,
        verifier_config=body.verifier_config,
        redact_payload=body.redact_payload,
        callback_url=body.callback_url,
    )

    if body.notify:
        background_tasks.add_task(
            notify_task_slack,
            task_id=task.id,
            task_title=task.task,
            notify=body.notify,
            form_definition=task.form_definition,
        )
        background_tasks.add_task(
            notify_task_email,
            task_id=task.id,
            task_title=task.task,
            task_payload=None if task.redact_payload else task.payload,
            redact_payload=task.redact_payload,
            notify=body.notify,
            form_definition=task.form_definition,
        )

    return _task_to_response(task)


@router.get("", response_model=list[TaskResponse])
async def list_tasks_route(
    status: TaskStatus | None = Query(None, description="Filter by status"),
    assigned_to: str | None = Query(None, description="Filter by assigned email"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[TaskResponse]:
    """List tasks with optional filters."""
    tasks = await list_tasks(
        session,
        status=status,
        assigned_to_email=assigned_to,
        limit=limit,
        offset=offset,
    )
    return [_task_to_response(t, redact=True) for t in tasks]


@router.get("/{task_id}", response_model=TaskResponse)
async def get_task_route(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """Get a single task by ID."""
    task = await get_task(session, task_id)
    return _task_to_response(task)


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task_route(
    task_id: str,
    body: CompleteTaskRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """Complete a task with the human's response.

    First-writer-wins: if the task is already terminal, returns 409 Conflict
    (handled by the centralized ServiceError handler).

    If the request didn't explicitly supply `completed_by_email` (the
    dashboard form doesn't — why would the browser lie about who it is)
    we read the logged-in user from the session cookie and record their
    email. That's the correct attribution: client can't fake it, server
    authoritatively stamps who clicked submit.
    """
    completer_email = body.completed_by_email
    if not completer_email:
        completer_email = await _session_user_email(request, session)

    task = await complete_task(
        session,
        task_id=task_id,
        response=body.response,
        completed_by_email=completer_email,
        completed_via_channel=body.completed_via_channel,
    )
    return _task_to_response(task)


async def _session_user_email(request: Request, session: AsyncSession) -> str | None:
    """Look up the logged-in user's email from the session cookie claims.

    Returns None when the caller isn't using a cookie (admin bearer
    token, magic-link email flow, etc.) — those callers already supply
    `completed_by_email` themselves through channel-specific paths.
    """
    claims = getattr(request.state, "auth_claims", None)
    if not isinstance(claims, SessionClaims):
        return None
    user = await get_user(session, claims.user_id)
    return user.email if user else None


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task_route(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """Cancel a task."""
    task = await cancel_task(session, task_id)
    return _task_to_response(task)


@router.delete(
    "/{task_id}",
    status_code=204,
    response_class=Response,
    dependencies=[Depends(require_admin)],
)
async def delete_task_route(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> Response:
    """Hard delete a task. Operator-only surface.

    Unlike `/cancel` (which keeps the row with status=CANCELLED),
    this removes the row entirely. Audit entries aren't cascaded —
    they persist as a historical record of what happened, orphaned.
    """
    if not await delete_task(session, task_id):
        raise TaskNotFoundError(task_id)
    return Response(status_code=204)


@router.get("/{task_id}/poll", response_model=PollResponse)
async def poll_task_route(
    task_id: str,
    timeout: int = Query(25, ge=1, le=30, description="Long-poll timeout in seconds"),
) -> PollResponse:
    """Long-poll for task completion.

    Holds the HTTP connection open for up to `timeout` seconds (default 25, max 30).
    Returns immediately if the task is already in a terminal state.
    If the task is still pending after the timeout, returns the current status
    so the client can reconnect.

    Note: does NOT hold a DB session open during the wait — acquires a fresh
    short-lived session for each 1-second check to avoid exhausting the pool.
    """
    from awaithumans.server.db.connection import get_async_session_factory

    factory = get_async_session_factory()

    # Check current state immediately
    async with factory() as session:
        task = await get_task(session, task_id)

        if task.status in TERMINAL_STATUSES_SET:
            return PollResponse(
                status=task.status.value,
                response=task.response,
                completed_at=task.completed_at,
                timed_out_at=task.timed_out_at,
            )

    # Long-poll: check every 1 second with a fresh session each time
    elapsed = 0
    last_status = task.status.value
    while elapsed < timeout:
        await asyncio.sleep(1)
        elapsed += 1

        async with factory() as session:
            task = await get_task(session, task_id)

            if task.status in TERMINAL_STATUSES_SET:
                return PollResponse(
                    status=task.status.value,
                    response=task.response,
                    completed_at=task.completed_at,
                    timed_out_at=task.timed_out_at,
                )
            last_status = task.status.value

    # Timeout — return current status so client can reconnect
    return PollResponse(
        status=last_status,
        response=None,
        completed_at=None,
        timed_out_at=None,
    )


@router.get("/{task_id}/audit", response_model=list[AuditEntryResponse])
async def get_audit_trail_route(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> list[AuditEntryResponse]:
    """Get the full audit trail for a task."""
    await get_task(session, task_id)  # Verify task exists (raises TaskNotFoundError if not)
    entries = await get_audit_trail(session, task_id)
    return [AuditEntryResponse.model_validate(e) for e in entries]
