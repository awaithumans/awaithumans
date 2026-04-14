"""Start the awaithumans server + dashboard for local development."""

from __future__ import annotations

import logging
import os

import typer

logger = logging.getLogger("awaithumans.cli")


def dev(
    host: str = typer.Option("0.0.0.0", help="Host to bind to."),
    port: int = typer.Option(3001, help="Port for the API server."),
    db_path: str = typer.Option(".awaithumans/dev.db", help="SQLite database path."),
    log_level: str = typer.Option("INFO", help="Log level (DEBUG, INFO, WARNING, ERROR)."),
) -> None:
    """Start the awaithumans server + dashboard for local development."""
    import uvicorn

    from awaithumans.server.core.logging_config import setup_logging

    # Set config via env vars so Settings picks them up
    os.environ.setdefault("AWAITHUMANS_DB_PATH", db_path)
    os.environ.setdefault("AWAITHUMANS_LOG_LEVEL", log_level)
    os.environ.setdefault("AWAITHUMANS_HOST", host)
    os.environ.setdefault("AWAITHUMANS_PORT", str(port))

    setup_logging(log_level)

    logger.info("Starting awaithumans server on http://%s:%d", host, port)
    logger.info("Dashboard at http://%s:%d", host, port)
    logger.info("SQLite database at %s", db_path)
    logger.info("Ready — waiting for tasks...")

    from awaithumans.server.app import create_app

    application = create_app(serve_dashboard=True)
    uvicorn.run(application, host=host, port=port, log_level=log_level.lower())
