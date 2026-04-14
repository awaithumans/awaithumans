"""CLI entrypoint — `awaithumans dev`, `awaithumans add-user`, etc."""

from __future__ import annotations

import logging

try:
    import typer
except ImportError:
    raise SystemExit(
        "The awaithumans CLI requires the [server] extra.\n"
        'Install with: pip install "awaithumans[server]"'
    )

app = typer.Typer(
    name="awaithumans",
    help="The human layer for AI agents.",
    no_args_is_help=True,
)

logger = logging.getLogger("awaithumans.cli")


@app.command()
def dev(
    host: str = typer.Option("0.0.0.0", help="Host to bind to."),
    port: int = typer.Option(3001, help="Port for the API server."),
    db_path: str = typer.Option(".awaithumans/dev.db", help="SQLite database path."),
    log_level: str = typer.Option("INFO", help="Log level (DEBUG, INFO, WARNING, ERROR)."),
) -> None:
    """Start the awaithumans server + dashboard for local development."""
    import os
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


@app.command()
def add_user(
    email: str = typer.Argument(help="User's email address."),
    role: str = typer.Option(None, help="Role to assign (e.g., kyc-reviewer)."),
    access_level: str = typer.Option(None, help="Access level (e.g., senior)."),
    pool: str = typer.Option(None, help="Pool to add the user to."),
) -> None:
    """Add a user to the awaithumans user directory."""
    # TODO: implement — write to the user directory (JSON file or DB)
    logger.info("Adding user: %s (role=%s, access_level=%s, pool=%s)", email, role, access_level, pool)
    typer.echo(f"Added user: {email}")
    if role:
        typer.echo(f"  Role: {role}")
    if access_level:
        typer.echo(f"  Access level: {access_level}")
    if pool:
        typer.echo(f"  Pool: {pool}")


@app.command()
def version() -> None:
    """Show the awaithumans version."""
    from awaithumans import __version__

    typer.echo(f"awaithumans {__version__}")


if __name__ == "__main__":
    app()
