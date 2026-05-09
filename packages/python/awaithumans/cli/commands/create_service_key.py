"""`awaithumans create-service-key --name <name>`

Mints a new service API key. The raw `ah_sk_*` value is shown ONCE on
stdout — store it immediately. Subsequent listings only show the prefix.
"""

from __future__ import annotations

import asyncio

import typer

from awaithumans.cli.commands._session import with_session
from awaithumans.server.services.service_key_service import (
    create_service_key as _create,
)


def create_service_key(
    name: str = typer.Option(..., "--name", help="Display name for this key."),
) -> None:
    """Create a new service API key. The raw key is shown only once."""

    async def _run() -> None:
        async with with_session() as session:
            try:
                raw, row = await _create(session, name=name)
            except ValueError as e:
                typer.echo(typer.style(f"✗ {e}", fg=typer.colors.RED), err=True)
                raise typer.Exit(code=1) from e

        typer.echo("")
        typer.echo(typer.style("✓ service key created", fg=typer.colors.GREEN))
        typer.echo(f"  id:     {row.id}")
        typer.echo(f"  name:   {row.name}")
        typer.echo("")
        typer.echo(
            typer.style(
                "  Save this key now — it will not be shown again:",
                fg=typer.colors.YELLOW,
            )
        )
        typer.echo(f"  {raw}")
        typer.echo("")

    asyncio.run(_run())
