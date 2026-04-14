"""Show the awaithumans version."""

from __future__ import annotations

import typer


def version() -> None:
    """Show the awaithumans version."""
    from awaithumans import __version__

    typer.echo(f"awaithumans {__version__}")
