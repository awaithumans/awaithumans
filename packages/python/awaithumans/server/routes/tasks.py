"""Task API routes — CRUD, long-poll, completion."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.server.db.connection import get_session
from awaithumans.server.db.models import TaskStatus
from awaithumans.server.services.task_service import (
    TaskAlreadyTerminalError,
    TaskNotFoundError,
    cancel_task,
    complete_task,
    create_task,
    get_audit_trail,
    get_task,
    list_tasks,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


# ─── Request / Response Models ───────────────────────────────────────────


class CreateTaskRequest(BaseModel):
    task: str
    payload: dict[str, Any]
    payload_schema: dict[str, Any]
    response_schema: dict[str, Any]
    timeout_seconds: int = Field(ge=60, le=2_592_000)
    idempotency_key: str
    assign_to: dict[str, Any] | None = None
    notify: list[str] | None = None
    verifier_config: dict[str, Any] | None = None
    redact_payload: bool = False
    callback_url: str | None = None


class TaskResponse(BaseModel):
    id: str
    idempotency_key: str
    task: str
    payload: dict[str, Any] | None = None
    payload_schema: dict[str, Any]
    response_schema: dict[str, Any]
    status: str
    assign_to: dict[str, Any] | None = None
    assigned_to_email: str | None = None
    response: dict[str, Any] | None = None
    verifier_result: dict[str, Any] | None = None
    verification_attempt: int = 0
    timeout_seconds: int
    redact_payload: bool
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    timed_out_at: datetime | None = None
    completed_by_email: str | None = None
    completed_via_channel: str | None = None

    model_config = {"from_attributes": True}


class CompleteTaskRequest(BaseModel):
    response: dict[str, Any]
    completed_by_email: str | None = None
    completed_via_channel: str | None = None


class AuditEntryResponse(BaseModel):
    id: str
    task_id: str
    from_status: str | None = None
    to_status: str
    action: str
    actor_type: str
    actor_email: str | None = None
    channel: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class PollResponse(BaseModel):
    status: str
    response: dict[str, Any] | None = None
    completed_at: datetime | None = None
    timed_out_at: datetime | None = None


# ─── Helper ──────────────────────────────────────────────────────────────


def _task_to_response(task: Any, *, redact: bool = False) -> TaskResponse:
    """Convert a Task model to a TaskResponse, optionally redacting payload."""
    data = TaskResponse.model_validate(task)
    if redact and task.redact_payload:
        data.payload = {"_redacted": True}
    return data


# ─── Routes ──────────────────────────────────────────────────────────────


@router.post("", response_model=TaskResponse, status_code=201)
async def create_task_route(
    body: CreateTaskRequest,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """Create a new HITL task (or return existing if idempotency key matches)."""
    task = await create_task(
        session,
        task=body.task,
        payload=body.payload,
        payload_schema=body.payload_schema,
        response_schema=body.response_schema,
        timeout_seconds=body.timeout_seconds,
        idempotency_key=body.idempotency_key,
        assign_to=body.assign_to,
        notify=body.notify,
        verifier_config=body.verifier_config,
        redact_payload=body.redact_payload,
        callback_url=body.callback_url,
    )
    return _task_to_response(task)


@router.get("", response_model=list[TaskResponse])
async def list_tasks_route(
    status: str | None = Query(None, description="Filter by status"),
    assigned_to: str | None = Query(None, description="Filter by assigned email"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
) -> list[TaskResponse]:
    """List tasks with optional filters."""
    status_enum = TaskStatus(status) if status else None
    tasks = await list_tasks(
        session,
        status=status_enum,
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
    try:
        task = await get_task(session, task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    return _task_to_response(task)


@router.post("/{task_id}/complete", response_model=TaskResponse)
async def complete_task_route(
    task_id: str,
    body: CompleteTaskRequest,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """Complete a task with the human's response.

    First-writer-wins: if the task is already terminal (e.g., timed out),
    returns 409 Conflict.
    """
    try:
        task = await complete_task(
            session,
            task_id=task_id,
            response=body.response,
            completed_by_email=body.completed_by_email,
            completed_via_channel=body.completed_via_channel,
        )
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    except TaskAlreadyTerminalError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Task '{task_id}' is already in terminal status '{e.status.value}'.",
        )
    return _task_to_response(task)


@router.post("/{task_id}/cancel", response_model=TaskResponse)
async def cancel_task_route(
    task_id: str,
    session: AsyncSession = Depends(get_session),
) -> TaskResponse:
    """Cancel a task."""
    try:
        task = await cancel_task(session, task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")
    except TaskAlreadyTerminalError as e:
        raise HTTPException(
            status_code=409,
            detail=f"Task '{task_id}' is already in terminal status '{e.status.value}'.",
        )
    return _task_to_response(task)


@router.get("/{task_id}/poll", response_model=PollResponse)
async def poll_task_route(
    task_id: str,
    timeout: int = Query(25, ge=1, le=30, description="Long-poll timeout in seconds"),
    session: AsyncSession = Depends(get_session),
) -> PollResponse:
    """Long-poll for task completion.

    Holds the connection open for up to `timeout` seconds (default 25, max 30).
    Returns immediately if the task is already in a terminal state.
    If the task is still pending after the timeout, returns the current status
    so the client can reconnect.
    """
    # Check current state immediately
    try:
        task = await get_task(session, task_id)
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    if task.status in {TaskStatus.COMPLETED, TaskStatus.TIMED_OUT,
                       TaskStatus.CANCELLED, TaskStatus.VERIFICATION_EXHAUSTED}:
        return PollResponse(
            status=task.status.value,
            response=task.response,
            completed_at=task.completed_at,
            timed_out_at=task.timed_out_at,
        )

    # Long-poll: check every 1 second until timeout or terminal state
    elapsed = 0
    while elapsed < timeout:
        await asyncio.sleep(1)
        elapsed += 1

        # Re-fetch from DB to see if status changed
        await session.expire(task)
        task = await get_task(session, task_id)

        if task.status in {TaskStatus.COMPLETED, TaskStatus.TIMED_OUT,
                           TaskStatus.CANCELLED, TaskStatus.VERIFICATION_EXHAUSTED}:
            return PollResponse(
                status=task.status.value,
                response=task.response,
                completed_at=task.completed_at,
                timed_out_at=task.timed_out_at,
            )

    # Timeout — return current status so client can reconnect
    return PollResponse(
        status=task.status.value,
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
    try:
        await get_task(session, task_id)  # Verify task exists
    except TaskNotFoundError:
        raise HTTPException(status_code=404, detail=f"Task '{task_id}' not found.")

    entries = await get_audit_trail(session, task_id)
    return [AuditEntryResponse.model_validate(e) for e in entries]
