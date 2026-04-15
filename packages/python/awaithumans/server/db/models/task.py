"""Task model — one row per awaitHuman() call."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlmodel import JSON, Column, Field, SQLModel

from awaithumans.types import TaskStatus
from awaithumans.server.db.models.base import new_id, utc_now


class Task(SQLModel, table=True):
    """Core task record — one row per awaitHuman() call."""

    __tablename__ = "tasks"

    id: str = Field(default_factory=new_id, primary_key=True)
    idempotency_key: str = Field(index=True, unique=True)

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
