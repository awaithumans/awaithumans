"""FastAPI application factory."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

# TODO: import routes when built
# from awaithumans.server.routes import tasks, webhooks, auth, health


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown events."""
    # TODO: initialize database connection pool
    # TODO: start background task timeout scheduler
    yield
    # TODO: cleanup database connections


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

    # ── API routes ───────────────────────────────────────────────────
    # TODO: app.include_router(tasks.router, prefix="/api")
    # TODO: app.include_router(webhooks.router, prefix="/api")
    # TODO: app.include_router(auth.router, prefix="/api")
    # TODO: app.include_router(health.router, prefix="/api")

    # ── Dashboard static files ───────────────────────────────────────
    if serve_dashboard:
        dashboard_dist = Path(__file__).parent.parent.parent / "dashboard_dist"
        if dashboard_dist.exists():
            app.mount("/", StaticFiles(directory=str(dashboard_dist), html=True), name="dashboard")

    return app
