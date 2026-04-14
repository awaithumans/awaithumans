"""Database connection management."""

from __future__ import annotations

import os
from pathlib import Path

from sqlmodel import SQLModel, create_engine, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker


def get_database_url() -> str:
    """Resolve the database URL from environment or default to SQLite."""
    url = os.environ.get("DATABASE_URL")
    if url:
        # Convert postgres:// to postgresql+asyncpg:// for async
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
        return url

    # Default: SQLite for development
    db_path = os.environ.get("AWAITHUMANS_DB_PATH", ".awaithumans/dev.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite+aiosqlite:///{db_path}"


def get_sync_database_url() -> str:
    """Resolve the sync database URL (for migrations and CLI commands)."""
    url = os.environ.get("DATABASE_URL")
    if url:
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        return url

    db_path = os.environ.get("AWAITHUMANS_DB_PATH", ".awaithumans/dev.db")
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


# Async engine for the FastAPI server
_async_engine = None


def get_async_engine():
    """Get or create the async database engine."""
    global _async_engine
    if _async_engine is None:
        url = get_database_url()
        connect_args = {}
        if "sqlite" in url:
            connect_args["check_same_thread"] = False
        _async_engine = create_async_engine(url, connect_args=connect_args, echo=False)
    return _async_engine


# Async session factory
_async_session_factory = None


def get_async_session_factory():
    """Get or create the async session factory."""
    global _async_session_factory
    if _async_session_factory is None:
        engine = get_async_engine()
        _async_session_factory = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    return _async_session_factory


async def get_session() -> AsyncSession:
    """FastAPI dependency — yields an async database session."""
    factory = get_async_session_factory()
    async with factory() as session:
        yield session


async def init_db() -> None:
    """Create all tables. Called on server startup."""
    engine = get_async_engine()
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)


async def close_db() -> None:
    """Close the database engine. Called on server shutdown."""
    global _async_engine, _async_session_factory
    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None
