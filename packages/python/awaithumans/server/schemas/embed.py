"""Request/response models for the embed mint endpoint."""

from __future__ import annotations

from pydantic import BaseModel, Field


class EmbedTokenRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=64)
    sub: str | None = Field(default=None, max_length=256)
    parent_origin: str = Field(min_length=1, max_length=256)
    ttl_seconds: int | None = Field(default=None, ge=0)


class EmbedTokenResponse(BaseModel):
    embed_token: str
    embed_url: str
    expires_at: str  # ISO8601 UTC
