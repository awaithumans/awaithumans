"""List users in the directory."""

from __future__ import annotations

import asyncio

import typer

from awaithumans.cli.commands._session import with_session
from awaithumans.server.services.user_service import list_users


def list_users_cmd(
    role: str | None = typer.Option(None, help="Only users with this role."),
    access_level: str | None = typer.Option(None, help="Only users with this access level."),
    pool: str | None = typer.Option(None, help="Only users in this pool."),
    active: bool | None = typer.Option(None, help="Only active (true) or inactive (false) users."),
) -> None:
    """List users in the directory."""

    async def _run() -> None:
        async with with_session() as session:
            users = await list_users(
                session,
                role=role,
                access_level=access_level,
                pool=pool,
                active=active,
            )

        if not users:
            typer.echo("No users found.")
            return

        header = f"{'ID':<12} {'EMAIL':<30} {'SLACK':<22} {'ROLE':<18} {'LEVEL':<10} {'POOL':<10} {'OP':<3}"
        typer.echo(header)
        typer.echo("-" * len(header))
        for u in users:
            slack_addr = f"{u.slack_team_id}/{u.slack_user_id}" if u.slack_team_id else ""
            typer.echo(
                f"{u.id[:10]:<12} "
                f"{(u.email or ''):<30} "
                f"{slack_addr:<22} "
                f"{(u.role or ''):<18} "
                f"{(u.access_level or ''):<10} "
                f"{(u.pool or ''):<10} "
                f"{('yes' if u.is_operator else ''):<3}"
            )
        typer.echo(f"\nTotal: {len(users)}")

    asyncio.run(_run())
