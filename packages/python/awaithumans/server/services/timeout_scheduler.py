"""Background timeout scheduler — marks expired tasks as timed_out."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select

from awaithumans.server.channels.slack.post_completion import (
    update_slack_messages_for_task,
)
from awaithumans.server.db.connection import get_async_session_factory
from awaithumans.server.db.models import Task
from awaithumans.server.services.task_service import timeout_task
from awaithumans.server.services.webhook_dispatch import fire_completion_webhook
from awaithumans.utils.constants import TERMINAL_STATUSES_SET, TIMEOUT_CHECK_INTERVAL_SECONDS

logger = logging.getLogger("awaithumans.timeout_scheduler")


async def run_timeout_scheduler() -> None:
    """Run the timeout scheduler loop.

    Checks every TIMEOUT_CHECK_INTERVAL_SECONDS seconds for tasks whose timeout_at has passed
    and are still in a non-terminal state. Marks them as timed_out using
    first-writer-wins semantics.
    """
    logger.info("Timeout scheduler started (check interval: %ds)", TIMEOUT_CHECK_INTERVAL_SECONDS)

    while True:
        try:
            await _check_and_timeout_expired_tasks()
        except Exception:
            logger.exception("Error in timeout scheduler")

        await asyncio.sleep(TIMEOUT_CHECK_INTERVAL_SECONDS)


async def _check_and_timeout_expired_tasks() -> None:
    """Find and timeout all expired tasks using the indexed timeout_at column."""
    factory = get_async_session_factory()
    async with factory() as session:
        now = datetime.now(timezone.utc)

        # Efficient query: uses the timeout_at index, only fetches IDs
        result = await session.execute(
            select(Task.id)
            .where(Task.status.notin_(list(TERMINAL_STATUSES_SET)))
            .where(Task.timeout_at <= now)
        )
        expired_ids = [row[0] for row in result.all()]

        for task_id in expired_ids:
            logger.info("Timing out task '%s'", task_id)
            task = await timeout_task(session, task_id)
            # Fire webhook for callback-equipped tasks. Without this,
            # a Temporal workflow waiting on a signal would sit
            # forever on tasks the server timed out — the workflow's
            # own timer would eventually fire, but operators reading
            # the dashboard would see a `timed_out` task with no
            # signal ever sent. asyncio.create_task makes it
            # fire-and-forget so a slow callback doesn't block the
            # next iteration of the scheduler loop.
            if task.callback_url:
                asyncio.create_task(fire_completion_webhook(task))

            # Replace the original Slack notification ("Approve / Reject"
            # buttons) with a "Timed out" surface so the recipient
            # doesn't try to fill the form on a dead task.
            asyncio.create_task(update_slack_messages_for_task(task.id))
