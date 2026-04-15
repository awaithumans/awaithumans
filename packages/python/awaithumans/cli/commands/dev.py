"""Start the awaithumans server + dashboard for local development."""

from __future__ import annotations

import atexit
import logging
import os
import socket

import typer

from awaithumans.utils.discovery import delete_discovery, write_discovery

logger = logging.getLogger("awaithumans.cli")


def _is_port_available(host: str, port: int) -> bool:
    """Check if a port is available for binding."""
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return True
    except OSError:
        return False


def _find_available_port(host: str, preferred: int, max_attempts: int = 10) -> int:
    """Find an available port, starting from the preferred one.

    Tries the preferred port first, then increments until an available one is found.
    """
    for offset in range(max_attempts):
        candidate = preferred + offset
        if _is_port_available(host, candidate):
            return candidate

    raise typer.Exit(
        code=1,
    )


def dev(
    host: str = typer.Option("0.0.0.0", help="Host to bind to."),
    port: int = typer.Option(3001, help="Port for the API server."),
    db_path: str = typer.Option(".awaithumans/dev.db", help="SQLite database path."),
    log_level: str = typer.Option("INFO", help="Log level (DEBUG, INFO, WARNING, ERROR)."),
) -> None:
    """Start the awaithumans server + dashboard for local development."""
    import uvicorn

    from awaithumans.server.core.logging_config import setup_logging

    setup_logging(log_level)

    # Find an available port
    actual_port = _find_available_port(host, port)
    if actual_port != port:
        logger.info(
            "Port %d is in use — using port %d instead",
            port,
            actual_port,
        )

    # Set config via env vars so Settings picks them up
    os.environ.setdefault("AWAITHUMANS_DB_PATH", db_path)
    os.environ.setdefault("AWAITHUMANS_LOG_LEVEL", log_level)
    os.environ.setdefault("AWAITHUMANS_HOST", host)
    os.environ.setdefault("AWAITHUMANS_PORT", str(actual_port))

    # Write discovery file so SDKs and the dashboard can auto-find us
    write_discovery(host=host, port=actual_port)
    atexit.register(delete_discovery)

    logger.info("Starting awaithumans server on http://%s:%d", host, actual_port)
    logger.info("Dashboard at http://%s:%d", host, actual_port)
    logger.info("SQLite database at %s", db_path)
    logger.info("Ready — waiting for tasks...")

    from awaithumans.server.app import create_app

    application = create_app(serve_dashboard=True)
    try:
        uvicorn.run(application, host=host, port=actual_port, log_level=log_level.lower())
    finally:
        delete_discovery()
