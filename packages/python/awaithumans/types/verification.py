"""Verification types — verifier config, context, and result."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


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

    provider: str = Field(description='E.g., "claude", "openai", "gemini", or "custom"')
    model: str | None = Field(default=None, description='E.g., "claude-sonnet-4-20250514"')
    instructions: str = Field(description="Prompt template for the verifier.")
    max_attempts: int = Field(default=3, ge=1, le=10)
    api_key_env: str | None = Field(
        default=None,
        description="Env var name for the API key. Server reads this at runtime.",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Provider-specific config (e.g., Azure endpoint_env, api_version).",
    )
