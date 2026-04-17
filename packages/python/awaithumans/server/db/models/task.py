"""Task model — one row per awaitHuman() call."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Index, text
from sqlmodel import JSON, Column, Field, SQLModel

from awaithumans.server.db.models.base import new_id, utc_now
from awaithumans.types import TaskStatus

# Partial unique index — only ACTIVE tasks have unique idempotency keys.
# After a task reaches a terminal state, another task with the same key can
# be created. This lets developers retry failed/timed-out tasks with the
# same content without hitting a duplicate-key error.
_TERMINAL_STATUS_VALUES = "('completed', 'timed_out', 'cancelled', 'verification_exhausted')"
_ACTIVE_IDEMPOTENCY_WHERE = f"status NOT IN {_TERMINAL_STATUS_VALUES}"


class Task(SQLModel, table=True):
    """Core task record — one row per awaitHuman() call."""

    __tablename__ = "tasks"

    id: str = Field(default_factory=new_id, primary_key=True)
    idempotency_key: str = Field(index=True)

    # Task description
    task: str = Field(description="Human-readable task description.")
    payload: dict[str, Any] = Field(sa_column=Column(JSON), default_factory=dict)
    payload_schema: dict[str, Any] = Field(sa_column=Column(JSON), default_factory=dict)
    response_schema: dict[str, Any] = Field(sa_column=Column(JSON), default_factory=dict)
    form_definition: dict[str, Any] | None = Field(
        sa_column=Column(JSON),
        default=None,
        description="Form primitive tree extracted from response_schema. Rendered per channel.",
    )

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
    created_at: datetime = Field(default_factory=utc_now)
    updated_at: datetime = Field(default_factory=utc_now)
    completed_at: datetime | None = Field(default=None)
    timed_out_at: datetime | None = Field(default=None)
    timeout_at: datetime | None = Field(
        default=None,
        index=True,
        description="Pre-computed: created_at + timeout_seconds. Used by timeout scheduler.",
    )

    # Webhook callback
    callback_url: str | None = Field(default=None)

    # Metadata
    completed_by_email: str | None = Field(default=None)
    completed_via_channel: str | None = Field(default=None)

    __table_args__ = (
        Index(
            "ix_tasks_active_idempotency_key",
            "idempotency_key",
            unique=True,
            sqlite_where=text(_ACTIVE_IDEMPOTENCY_WHERE),
            postgresql_where=text(_ACTIVE_IDEMPOTENCY_WHERE),
        ),
    )
