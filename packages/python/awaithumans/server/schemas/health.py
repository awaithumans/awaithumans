"""Health check API response schema."""

from __future__ import annotations

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
