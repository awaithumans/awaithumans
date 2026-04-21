"""Audit trail API response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, field_serializer

from awaithumans.server.schemas._datetime import utc_iso


class AuditEntryResponse(BaseModel):
    id: str
    task_id: str
    from_status: str | None = None
    to_status: str
    action: str
    actor_type: str
    actor_email: str | None = None
    channel: str | None = None
    extra_data: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}

    @field_serializer("created_at")
    def _ser_dt(self, dt: datetime | None) -> str | None:
        return utc_iso(dt)
