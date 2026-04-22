"""Shared helper: open a local SQLite session for CLI commands.

CLI commands run locally against the same database the server writes
to. Auth is "you already have shell access to the box" — no extra gate.

Runs `alembic upgrade head` first so fresh dev machines don't have to
remember to migrate before adding their first user.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy.ext.asyncio import AsyncSession

from awaithumans.server.db.connection import (
    close_db,
    get_async_session_factory,
    init_db,
)


@asynccontextmanager
async def with_session() -> AsyncIterator[AsyncSession]:
    """Yield a DB session, applying migrations on entry and disposing
    the engine on exit so the CLI process doesn't leave a stray
    connection pool alive."""
    await init_db()
    factory = get_async_session_factory()
    try:
        async with factory() as session:
            yield session
    finally:
        await close_db()
