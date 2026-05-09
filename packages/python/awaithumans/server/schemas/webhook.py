"""Outbound webhook delivery — admin response shapes."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from awaithumans.server.db.models import WebhookDeliveryStatus


class WebhookDeliveryResponse(BaseModel):
    """A row from the `webhook_deliveries` queue, exposed for the
    admin dashboard. The signed `body` is intentionally omitted —
    receivers verify it locally and operators don't need to read it."""

    id: str
    task_id: str
    url: str
    status: WebhookDeliveryStatus
    attempt_count: int
    next_attempt_at: datetime
    first_attempted_at: datetime | None
    last_attempt_at: datetime | None
    last_error: str | None
    last_status_code: int | None
    created_at: datetime
    updated_at: datetime
