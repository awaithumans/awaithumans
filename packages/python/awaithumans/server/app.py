"""FastAPI application factory.

All configuration, middleware, and error handling live in server/core/.
This file only wires them together.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles

from awaithumans.server.core.config import settings
from awaithumans.server.core.exceptions import exception_handlers
from awaithumans.server.core.logging_config import setup_logging
from awaithumans.server.core.middleware import RequestIDMiddleware
from awaithumans.server.db.connection import close_db, init_db
from awaithumans.server.routes import email, health, slack, tasks
from awaithumans.server.services.timeout_scheduler import run_timeout_scheduler

logger = logging.getLogger("awaithumans.server")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Startup and shutdown lifecycle."""
    await init_db()
    logger.info("Database initialized")

    scheduler_task = asyncio.create_task(run_timeout_scheduler())

    yield

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
    # ── Logging ──────────────────────────────────────────────────────
    setup_logging(settings.LOG_LEVEL)

    # ── Production safety checks ─────────────────────────────────────
    # HTTPS is required in production because the server handles Slack OAuth
    # tokens and bearer credentials that must not transit in cleartext.
    if settings.is_production and not settings.PUBLIC_URL.startswith("https://"):
        logger.error(
            "SECURITY: ENVIRONMENT=production but PUBLIC_URL is not HTTPS "
            "(value=%s). Tokens and OAuth state will transit in cleartext. "
            "Set PUBLIC_URL to an https:// URL.",
            settings.PUBLIC_URL,
        )

    # OAuth stores bot tokens in the DB. Those tokens are encrypted at rest
    # via server/core/encryption.py, which needs PAYLOAD_KEY. Without the
    # key we'd either silently fall back to plaintext (unsafe) or crash on
    # first install (surprising). Fail fast at boot instead.
    if settings.SLACK_CLIENT_ID and not settings.PAYLOAD_KEY:
        raise RuntimeError(
            "Slack OAuth is enabled (SLACK_CLIENT_ID is set) but PAYLOAD_KEY "
            "is not. Tokens cannot be encrypted at rest without it. Generate "
            "one with: python -c 'import secrets; print(secrets.token_urlsafe(32))' "
            "and set AWAITHUMANS_PAYLOAD_KEY."
        )

    # ── App ──────────────────────────────────────────────────────────
    app = FastAPI(
        title="awaithumans",
        description="The human layer for AI agents.",
        version="0.1.0",
        lifespan=lifespan,
    )

    # ── Exception handlers ───────────────────────────────────────────
    for exc_class, handler in exception_handlers.items():
        app.add_exception_handler(exc_class, handler)

    # ── Middleware (order matters — last added = first executed) ──────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True if settings.CORS_ORIGINS != "*" else False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestIDMiddleware)

    # ── Routes ───────────────────────────────────────────────────────
    app.include_router(tasks.router, prefix="/api")
    app.include_router(health.router, prefix="/api")
    app.include_router(slack.router, prefix="/api")
    app.include_router(email.router, prefix="/api")

    # ── Dashboard static files ───────────────────────────────────────
    if serve_dashboard:
        dashboard_dist = Path(__file__).parent.parent.parent / "dashboard_dist"
        if dashboard_dist.exists():
            app.mount(
                "/",
                StaticFiles(directory=str(dashboard_dist), html=True),
                name="dashboard",
            )

    logger.info(
        "App created (environment=%s, cors=%s, dashboard=%s)",
        settings.ENVIRONMENT,
        settings.CORS_ORIGINS,
        serve_dashboard,
    )

    return app
