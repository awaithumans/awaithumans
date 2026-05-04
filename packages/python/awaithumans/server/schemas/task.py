"""Task API request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_serializer

from awaithumans.server.schemas._datetime import utc_iso
from awaithumans.types import TaskStatus
from awaithumans.utils.constants import MAX_TIMEOUT_SECONDS, MIN_TIMEOUT_SECONDS


class CreateTaskRequest(BaseModel):
    task: str
    payload: dict[str, Any]
    payload_schema: dict[str, Any]
    response_schema: dict[str, Any]
    form_definition: dict[str, Any] | None = None
    timeout_seconds: int = Field(ge=MIN_TIMEOUT_SECONDS, le=MAX_TIMEOUT_SECONDS)
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


class TaskResponse(BaseModel):
    id: str
    idempotency_key: str
    task: str
    payload: dict[str, Any] | None = None
    payload_schema: dict[str, Any]
    response_schema: dict[str, Any]
    form_definition: dict[str, Any] | None = None
    status: TaskStatus
    assign_to: dict[str, Any] | None = None
    assigned_to_email: str | None = None
    # Populated for tasks assigned to a directory user. The dashboard
    # uses these to render the assignee in lists and the detail panel:
    # `display_name → email → @<slack_user_id> → "—"`. Without these
    # fields a Slack-only assignee (no email) shows as blank in the
    # UI even when routing knows who they are.
    assigned_to_user_id: str | None = None
    assigned_to_display_name: str | None = None
    assigned_to_slack_user_id: str | None = None
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

    @field_serializer("created_at", "updated_at", "completed_at", "timed_out_at")
    def _ser_dt(self, dt: datetime | None) -> str | None:
        return utc_iso(dt)


class PollResponse(BaseModel):
    status: str
    response: dict[str, Any] | None = None
    completed_at: datetime | None = None
    timed_out_at: datetime | None = None

    @field_serializer("completed_at", "timed_out_at")
    def _ser_dt(self, dt: datetime | None) -> str | None:
        return utc_iso(dt)
