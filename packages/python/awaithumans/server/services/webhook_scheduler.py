"""Background webhook delivery scheduler.

Owns the polling loop that drains the `webhook_deliveries` queue.
Modeled on `timeout_scheduler.py` — same shape, same cancel-aware
shutdown story. Every WEBHOOK_SCHEDULER_INTERVAL_SECONDS it asks the
dispatcher for a batch of due rows; if there's nothing to do the
query is a single indexed scan and costs nothing.

Why this lives in its own file: the timeout scheduler and webhook
scheduler have unrelated failure modes (a flapping receiver shouldn't
delay timeouts; a long DB lock during timeout sweep shouldn't pause
deliveries). Keeping them as independent asyncio tasks means each
gets its own cadence and its own crash-and-recover.
"""

from __future__ import annotations

import asyncio
import logging

from awaithumans.server.db.connection import get_async_session_factory
from awaithumans.server.services.webhook_dispatch import process_due_deliveries
from awaithumans.utils.constants import WEBHOOK_SCHEDULER_INTERVAL_SECONDS

logger = logging.getLogger("awaithumans.webhook_scheduler")


async def run_webhook_scheduler() -> None:
    """Run the webhook delivery loop.

    Sleeps WEBHOOK_SCHEDULER_INTERVAL_SECONDS between ticks. Each
    tick uses a fresh DB session so a long-running attempt can't
    starve the connection pool — every iteration is short, claim a
    batch, do the I/O, commit, sleep.
    """
    logger.info(
        "Webhook scheduler started (interval: %ds)",
        WEBHOOK_SCHEDULER_INTERVAL_SECONDS,
    )

    factory = get_async_session_factory()
    while True:
        try:
            async with factory() as session:
                attempted = await process_due_deliveries(session)
            if attempted:
                logger.debug("Processed %d webhook deliveries", attempted)
        except Exception:
            # Any uncaught exception (DB blip, network freak-out)
            # should never tear down the loop — the next tick has a
            # fresh session and a fresh shot. We log and continue.
            logger.exception("Error in webhook scheduler tick")

        await asyncio.sleep(WEBHOOK_SCHEDULER_INTERVAL_SECONDS)
