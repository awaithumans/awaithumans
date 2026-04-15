"""Audit trail API response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditEntryResponse(BaseModel):
    id: str
    task_id: str
    from_status: str | None = None
    to_status: str
    action: str
    actor_type: str
    actor_email: str | None = None
    channel: str | None = None
    metadata: dict[str, Any] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}
