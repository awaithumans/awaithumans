"""FastAPI application factory."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from awaithumans.server.db.connection import close_db, init_db
from awaithumans.server.routes import health, tasks
from awaithumans.server.services.timeout_scheduler import run_timeout_scheduler

logger = logging.getLogger("awaithumans.server")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown events."""
    # Initialize database (create tables if they don't exist)
    await init_db()
    logger.info("Database initialized")

    # Start the background timeout scheduler
    scheduler_task = asyncio.create_task(run_timeout_scheduler())

    yield

    # Shutdown
    scheduler_task.cancel()
    try:
        await scheduler_task
    except asyncio.CancelledError:
        pass
    await close_db()
    logger.info("Server shut down")


def create_app(*, serve_dashboard: bool = True) -> FastAPI:
    """Create the FastAPI application.

    Args:
        serve_dashboard: If True, serve the pre-built dashboard static files
            at the root path. Set to False when running the dashboard separately
            in development mode.
    """
    app = FastAPI(
        title="awaithumans",
        description="The human layer for AI agents.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── CORS (allow dashboard + SDKs from any origin in dev) ─────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # TODO: restrict in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── API routes ───────────────────────────────────────────────────
    app.include_router(tasks.router, prefix="/api")
    app.include_router(health.router, prefix="/api")

    # ── Dashboard static files ───────────────────────────────────────
    if serve_dashboard:
        dashboard_dist = Path(__file__).parent.parent.parent / "dashboard_dist"
        if dashboard_dist.exists():
            app.mount(
                "/",
                StaticFiles(directory=str(dashboard_dist), html=True),
                name="dashboard",
            )

    return app
