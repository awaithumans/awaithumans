"""CLI entrypoint — `awaithumans dev`, `awaithumans add-user`, etc."""

from __future__ import annotations

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


@app.command()
def dev(
    host: str = typer.Option("0.0.0.0", help="Host to bind to."),
    port: int = typer.Option(3001, help="Port for the API server."),
    db: str = typer.Option(".awaithumans/dev.db", help="SQLite database path."),
) -> None:
    """Start the awaithumans server + dashboard for local development."""
    import uvicorn

    from awaithumans.server.app import create_app

    typer.echo(f"Starting awaithumans server on http://{host}:{port}")
    typer.echo(f"Dashboard at http://{host}:{port}")
    typer.echo(f"SQLite database at {db}")
    typer.echo("Ready — waiting for tasks...\n")

    # TODO: pass db path to the app via environment or config
    application = create_app(serve_dashboard=True)
    uvicorn.run(application, host=host, port=port, log_level="info")


@app.command()
def add_user(
    email: str = typer.Argument(help="User's email address."),
    role: str = typer.Option(None, help="Role to assign (e.g., kyc-reviewer)."),
    access_level: str = typer.Option(None, help="Access level (e.g., senior)."),
    pool: str = typer.Option(None, help="Pool to add the user to."),
) -> None:
    """Add a user to the awaithumans user directory."""
    # TODO: implement — write to the user directory (JSON file or DB)
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
