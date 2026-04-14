"""Database models — SQLModel schema for tasks and audit trail."""

from __future__ import annotations

import enum
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlmodel import JSON, Column, Field, SQLModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid4().hex


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


class Task(SQLModel, table=True):
    """Core task record — one row per awaitHuman() call."""

    __tablename__ = "tasks"

    id: str = Field(default_factory=_new_id, primary_key=True)
    idempotency_key: str = Field(index=True)

    # Task description
    task: str = Field(description="Human-readable task description.")
    payload: dict[str, Any] = Field(sa_column=Column(JSON), default_factory=dict)
    payload_schema: dict[str, Any] = Field(sa_column=Column(JSON), default_factory=dict)
    response_schema: dict[str, Any] = Field(sa_column=Column(JSON), default_factory=dict)

    # State
    status: TaskStatus = Field(default=TaskStatus.CREATED)

    # Routing
    assign_to: dict[str, Any] | None = Field(sa_column=Column(JSON), default=None)
    assigned_to_email: str | None = Field(default=None, index=True)

    # Notification
    notify: list[str] | None = Field(sa_column=Column(JSON), default=None)

    # Response
    response: dict[str, Any] | None = Field(sa_column=Column(JSON), default=None)

    # Verification
    verifier_config: dict[str, Any] | None = Field(sa_column=Column(JSON), default=None)
    verifier_result: dict[str, Any] | None = Field(sa_column=Column(JSON), default=None)
    verification_attempt: int = Field(default=0)

    # Timeout
    timeout_seconds: int
    redact_payload: bool = Field(default=False)

    # Timestamps
    created_at: datetime = Field(default_factory=_utc_now)
    updated_at: datetime = Field(default_factory=_utc_now)
    completed_at: datetime | None = Field(default=None)
    timed_out_at: datetime | None = Field(default=None)

    # Webhook callback
    callback_url: str | None = Field(default=None)

    # Metadata
    completed_by_email: str | None = Field(default=None)
    completed_via_channel: str | None = Field(default=None)


class AuditEntry(SQLModel, table=True):
    """Audit trail — one row per state transition."""

    __tablename__ = "audit_entries"

    id: str = Field(default_factory=_new_id, primary_key=True)
    task_id: str = Field(index=True)

    # What happened
    from_status: str | None = Field(default=None)
    to_status: str
    action: str = Field(description="E.g., 'created', 'notified', 'completed', 'timed_out'")

    # Who did it
    actor_type: str = Field(description="'system', 'human', or 'agent'")
    actor_email: str | None = Field(default=None)

    # Context
    channel: str | None = Field(default=None, description="E.g., 'slack', 'email', 'dashboard'")
    metadata: dict[str, Any] | None = Field(sa_column=Column(JSON), default=None)

    # When
    created_at: datetime = Field(default_factory=_utc_now)
