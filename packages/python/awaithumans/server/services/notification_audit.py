"""Record notification-delivery failures into the audit log.

Notification sends (Slack message, email, etc.) are best-effort
background work. A failure must not roll back the task the agent just
created — that defeats the point of async delivery. But the operator
who opens the task in the dashboard needs *some* signal that the
human never got pinged. Previously these failures only hit the server
log, which an operator running a managed deployment may never see.

This module persists a single `AuditEntry` per failure with
`action="notification_failed"`, the channel that failed, and the
machine-readable reason + human-readable message in `extra_data`.
The task's audit panel (and a banner at the top of the task page)
surface it.

`to_status` is required on AuditEntry, but a failed notification
doesn't transition the task — pass the current status so the row
shows the task remained where it was.
"""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.server.db.models import AuditEntry

logger = logging.getLogger("awaithumans.server.services.notification_audit")


async def record_notification_failure(
    session: AsyncSession,
    *,
    task_id: str,
    task_status: str,
    channel: str,
    recipient: str,
    reason: str,
    message: str,
) -> None:
    """Persist a `notification_failed` audit entry and commit.

    Always commits the entry on its own — notify is a background task
    that runs after the parent transaction is already closed, so there
    is no outer commit to piggy-back on. A failure to persist the audit
    row should not itself silently drop; log loudly and swallow so the
    rest of the notification loop continues for other recipients.
    """
    extra: dict[str, Any] = {
        "recipient": recipient,
        "reason": reason,
        "message": message,
    }
    entry = AuditEntry(
        task_id=task_id,
        from_status=None,
        to_status=task_status,
        action="notification_failed",
        actor_type="system",
        channel=channel,
        extra_data=extra,
    )
    session.add(entry)
    try:
        await session.commit()
    except Exception:  # noqa: BLE001
        logger.exception(
            "Failed to record notification_failed audit entry for task=%s "
            "channel=%s recipient=%s reason=%s",
            task_id,
            channel,
            recipient,
            reason,
        )
        await session.rollback()
