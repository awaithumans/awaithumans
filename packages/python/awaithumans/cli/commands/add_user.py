"""Add a user to the awaithumans user directory."""

from __future__ import annotations

import logging

import typer

logger = logging.getLogger("awaithumans.cli")


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
