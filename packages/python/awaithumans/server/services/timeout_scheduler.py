"""Background timeout scheduler — marks expired tasks as timed_out."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.server.db.connection import get_async_session_factory
from awaithumans.server.db.models import Task, TaskStatus, TERMINAL_STATUSES
from awaithumans.server.services.task_service import timeout_task

logger = logging.getLogger("awaithumans.timeout_scheduler")

# How often to check for expired tasks (seconds)
CHECK_INTERVAL = 5


async def run_timeout_scheduler() -> None:
    """Run the timeout scheduler loop.

    Checks every CHECK_INTERVAL seconds for tasks that have exceeded their
    timeout_seconds and are still in a non-terminal state. Marks them as
    timed_out using first-writer-wins semantics.
    """
    logger.info("Timeout scheduler started (check interval: %ds)", CHECK_INTERVAL)

    while True:
        try:
            await _check_and_timeout_expired_tasks()
        except Exception:
            logger.exception("Error in timeout scheduler")

        await asyncio.sleep(CHECK_INTERVAL)


async def _check_and_timeout_expired_tasks() -> None:
    """Find and timeout all expired tasks."""
    factory = get_async_session_factory()
    async with factory() as session:
        now = datetime.now(timezone.utc)

        # Find tasks that are:
        # 1. Not in a terminal state
        # 2. Created more than timeout_seconds ago
        result = await session.execute(
            select(Task)
            .where(Task.status.notin_([s.value for s in TERMINAL_STATUSES]))
        )
        tasks = result.scalars().all()

        for task in tasks:
            elapsed = (now - task.created_at).total_seconds()
            if elapsed >= task.timeout_seconds:
                logger.info(
                    "Timing out task '%s' (%s) — elapsed %.0fs, timeout %ds",
                    task.id,
                    task.task,
                    elapsed,
                    task.timeout_seconds,
                )
                await timeout_task(session, task.id)
