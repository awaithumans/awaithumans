"""API request/response schemas — Pydantic models for the HTTP API.

All request and response models live here, NOT in route files.
Route files import from this module.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from awaithumans.types import TaskStatus


# ─── Task Requests ───────────────────────────────────────────────────────


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


class CompleteTaskRequest(BaseModel):
    response: dict[str, Any]
    completed_by_email: str | None = None
    completed_via_channel: str | None = None


# ─── Task Responses ──────────────────────────────────────────────────────


class TaskResponse(BaseModel):
    id: str
    idempotency_key: str
    task: str
    payload: dict[str, Any] | None = None
    payload_schema: dict[str, Any]
    response_schema: dict[str, Any]
    status: TaskStatus
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


class PollResponse(BaseModel):
    status: str
    response: dict[str, Any] | None = None
    completed_at: datetime | None = None
    timed_out_at: datetime | None = None


# ─── Audit Responses ─────────────────────────────────────────────────────


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


# ─── Health ──────────────────────────────────────────────────────────────


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
