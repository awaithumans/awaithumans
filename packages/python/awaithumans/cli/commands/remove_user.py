"""Remove a user from the directory by ID or email."""

from __future__ import annotations

import asyncio

import typer

from awaithumans.cli.commands._session import with_session
from awaithumans.server.services.user_service import (
    delete_user,
    get_user,
    get_user_by_email,
)


def remove_user(
    identifier: str = typer.Argument(help="User ID or email address."),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt."),
) -> None:
    """Remove a user from the directory.

    Hard delete — the row is gone. Use `update-user --active false`
    to deactivate without deleting.
    """

    async def _run() -> None:
        async with with_session() as session:
            # Try ID first, fall back to email lookup
            user = await get_user(session, identifier)
            if user is None and "@" in identifier:
                user = await get_user_by_email(session, identifier)

            if user is None:
                typer.echo(f"Error: user not found: {identifier}", err=True)
                raise typer.Exit(code=1)

            label = user.display_name or user.email or user.id
            if not yes:
                typer.confirm(
                    f"Remove user {label} ({user.id})?",
                    abort=True,
                )

            await delete_user(session, user.id)
            typer.echo(f"Removed: {user.id}")

    asyncio.run(_run())
