"""Set or clear a user's dashboard login password."""

from __future__ import annotations

import asyncio

import typer

from awaithumans.cli.commands._session import with_session
from awaithumans.server.services.exceptions import UserNotFoundError
from awaithumans.server.services.user_service import (
    get_user,
    get_user_by_email,
    set_password,
)


def set_password_cmd(
    identifier: str = typer.Argument(help="User ID or email address."),
    password: str | None = typer.Option(
        None,
        "--password",
        "-p",
        help="New password (min 8 chars). Omit to prompt interactively.",
    ),
    clear: bool = typer.Option(
        False, "--clear", help="Clear the password (user can no longer log in)."
    ),
) -> None:
    """Set or clear a user's dashboard login password.

    Pass `--clear` to disable login for a user without deleting them —
    they can still receive tasks via their configured channels.
    """
    if clear and password:
        raise typer.BadParameter("Pass either --password or --clear, not both.")

    new_password: str | None
    if clear:
        new_password = None
    elif password is not None:
        new_password = password
    else:
        new_password = typer.prompt("New password", hide_input=True, confirmation_prompt=True)

    if new_password is not None and len(new_password) < 8:
        raise typer.BadParameter("Password must be at least 8 characters.")

    async def _run() -> None:
        async with with_session() as session:
            user = await get_user(session, identifier)
            if user is None and "@" in identifier:
                user = await get_user_by_email(session, identifier)
            if user is None:
                raise UserNotFoundError(identifier)

            await set_password(session, user.id, new_password)

        if clear:
            typer.echo(f"Password cleared for {user.id}")
        else:
            typer.echo(f"Password updated for {user.id}")

    try:
        asyncio.run(_run())
    except UserNotFoundError as exc:
        typer.echo(f"Error: {exc.message}", err=True)
        raise typer.Exit(code=1) from exc
