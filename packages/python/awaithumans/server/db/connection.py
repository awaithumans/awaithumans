"""Database connection management.

Uses the centralized settings from server/core/config.py.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlmodel import SQLModel

from awaithumans.server.core.config import settings

logger = logging.getLogger("awaithumans.server.db")

# Async engine (lazily initialized)
_async_engine = None

# Async session factory (lazily initialized)
_async_session_factory = None


def get_async_engine():
    """Get or create the async database engine."""
    global _async_engine
    if _async_engine is None:
        url = settings.database_url_async
        connect_args = {}
        if "sqlite" in url:
            connect_args["check_same_thread"] = False
        _async_engine = create_async_engine(url, connect_args=connect_args, echo=False)
        logger.info("Database engine created (url=%s)", url.split("@")[-1] if "@" in url else url)
    return _async_engine


def get_async_session_factory():
    """Get or create the async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_async_engine()
        _async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return _async_session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency — yields an async database session."""
    factory = get_async_session_factory()
    async with factory() as session:
        yield session


async def init_db() -> None:
    """Create all tables. Called on server startup."""
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)
    logger.info("Database tables created")


async def close_db() -> None:
    """Close the database engine. Called on server shutdown."""
    global _async_engine, _async_session_factory
    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None
        logger.info("Database engine closed")
