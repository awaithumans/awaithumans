"""Single-use enforcement for magic-link tokens.

The route layer calls `try_consume_token(session, jti)` immediately
after HMAC-verifying a magic-link token. The function attempts to
INSERT a new row keyed on `jti`; the primary-key constraint makes the
operation atomic across concurrent submissions. Returns True on
first-use, False on replay.

We do NOT depend on the wider transaction state — `try_consume_token`
commits its own row before returning so a downstream failure in the
caller (`complete_task` raising for unrelated reasons) doesn't roll
back the consumption marker. Once consumed, the token stays consumed
even if the task completion didn't ultimately apply; the human can
re-engage via the dashboard. The alternative — leaving the token
re-usable on completion failure — opens a window where a flaky DB
moment lets an attacker retry.
"""

from __future__ import annotations

import logging

from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.server.db.models import ConsumedEmailToken

logger = logging.getLogger("awaithumans.server.services.email_token_service")


async def try_consume_token(session: AsyncSession, jti: str) -> bool:
    """Mark `jti` as consumed. Returns True if this is first-use,
    False if it was already consumed (replay attempt).

    Race-safe: two concurrent POSTs with the same token will both
    attempt the INSERT; the loser sees IntegrityError and gets
    False. Only one caller proceeds to complete the task."""
    from sqlalchemy import select

    # Cheap pre-check before INSERT — covers in-memory SQLite test
    # databases that don't share PK constraints across distinct
    # connections in some pool configurations. The IntegrityError
    # path below is still the authoritative race-safe gate against
    # concurrent submissions on the same token.
    existing = await session.execute(
        select(ConsumedEmailToken).where(ConsumedEmailToken.jti == jti)
    )
    if existing.scalar_one_or_none() is not None:
        logger.info("Magic-link replay rejected: jti=%s already consumed", jti)
        return False

    session.add(ConsumedEmailToken(jti=jti))
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        logger.info("Magic-link replay rejected: jti=%s already consumed", jti)
        return False
    return True
