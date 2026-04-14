"""Core types for awaithumans."""

from __future__ import annotations

import enum
from datetime import datetime
from typing import Any, Callable, Literal, Union

from pydantic import BaseModel, Field


# ─── Core Primitive Options ──────────────────────────────────────────────


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

    class Config:
        arbitrary_types_allowed = True


# ─── Routing ─────────────────────────────────────────────────────────────


class PoolAssignment(BaseModel):
    pool: str


class RoleAssignment(BaseModel):
    role: str
    access_level: str | None = None


class UserAssignment(BaseModel):
    user_id: str


class MarketplaceAssignment(BaseModel):
    marketplace: Literal[True] = True


AssignTo = Union[
    str,                    # email — direct assignment
    list[str],              # multiple emails — first to claim
    PoolAssignment,         # named pool
    RoleAssignment,         # role-based (optionally with access level)
    UserAssignment,         # internal user ID
    MarketplaceAssignment,  # reserved for Phase 3
]


# ─── Human Identity ─────────────────────────────────────────────────────


class HumanIdentity(BaseModel):
    id: str
    email: str
    display_name: str | None = None
    roles: list[str] | None = None
    access_level: str | None = None


# ─── Verifier ────────────────────────────────────────────────────────────


class VerificationContext(BaseModel):
    """Context passed to the verifier for quality checking + NL parsing."""

    task: str
    payload: Any
    payload_schema: dict  # JSON Schema
    response: Any | None = None  # structured response (None if NL input)
    response_schema: dict  # JSON Schema
    raw_input: str | None = None  # natural language text
    attempt: int
    previous_rejections: list[str] = Field(default_factory=list)


class VerifierResult(BaseModel):
    """Result from the verifier."""

    passed: bool
    reason: str = Field(description="Human-readable — shown to the human if rejected.")
    parsed_response: Any | None = Field(
        default=None,
        description="Extracted from NL input, conforming to response_schema.",
    )


class VerifierConfig(BaseModel):
    """Configuration for a verifier (passed to the server, executed server-side)."""

    provider: str = Field(description='E.g., "claude", "openai", or "custom"')
    model: str | None = Field(default=None, description='E.g., "claude-sonnet-4-20250514"')
    instructions: str = Field(description="Prompt template for the verifier.")
    max_attempts: int = Field(default=3, ge=1, le=10)
    api_key_env: str | None = Field(
        default=None,
        description="Env var name for the API key. Server reads this at runtime.",
    )


# ─── Task State Machine ─────────────────────────────────────────────────


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


# ─── Task Record ─────────────────────────────────────────────────────────


class TaskRecord(BaseModel):
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
