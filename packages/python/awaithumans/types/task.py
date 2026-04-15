"""Task-related types — status, options, record."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Union

from pydantic import BaseModel, ConfigDict, Field

from awaithumans.types.routing import AssignTo
from awaithumans.types.verification import VerifierConfig, VerifierResult


class TaskStatus(str, enum.Enum):
    CREATED = "created"
    NOTIFIED = "notified"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    VERIFIED = "verified"
    COMPLETED = "completed"
    REJECTED = "rejected"
    TIMED_OUT = "timed_out"
    CANCELLED = "cancelled"
    VERIFICATION_EXHAUSTED = "verification_exhausted"


TERMINAL_STATUSES = frozenset({
    TaskStatus.COMPLETED,
    TaskStatus.TIMED_OUT,
    TaskStatus.CANCELLED,
    TaskStatus.VERIFICATION_EXHAUSTED,
})


class AwaitHumanOptions(BaseModel):
    """Options for the await_human() call."""

    task: str = Field(description="Human-readable description of the task.")
    payload_schema: type[BaseModel] = Field(description="Pydantic model class for the payload.")
    payload: BaseModel = Field(description="The data sent to the human.")
    response_schema: type[BaseModel] = Field(description="Pydantic model class for the response.")
    timeout_seconds: int = Field(
        ge=60,
        le=2_592_000,
        description="Timeout in seconds. Min: 60 (1 minute). Max: 2,592,000 (30 days).",
    )
    assign_to: AssignTo | None = Field(default=None, description="Who should handle this task.")
    notify: list[str] | None = Field(default=None, description='E.g., ["slack:#ops", "email:a@b.com"]')
    verifier: VerifierConfig | None = Field(default=None, description="AI verification config.")
    idempotency_key: str | None = Field(default=None, description="Explicit idempotency key.")
    redact_payload: bool = Field(default=False, description="If true, audit log hides payload.")

    model_config = ConfigDict(arbitrary_types_allowed=True)


class TaskRecord(BaseModel):
    """A task as returned by the SDK/API."""

    id: str
    idempotency_key: str
    task: str
    payload: Any
    payload_schema: dict
    response_schema: dict
    status: TaskStatus
    assign_to: Any | None = None
    response: Any | None = None
    verifier_result: VerifierResult | None = None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None
    timed_out_at: datetime | None = None
    timeout_seconds: int
    redact_payload: bool = False
