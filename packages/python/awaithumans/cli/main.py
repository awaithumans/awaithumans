"""CLI entrypoint — registers commands, nothing else.

Each command lives in its own file under cli/commands/.
"""

from __future__ import annotations

try:
    import typer
except ImportError:
    raise SystemExit(
        "The awaithumans CLI requires the [server] extra.\n"
        'Install with: pip install "awaithumans[server]"'
    ) from None

from awaithumans.cli.commands.add_user import add_user
from awaithumans.cli.commands.dev import dev
from awaithumans.cli.commands.version import version

app = typer.Typer(
    name="awaithumans",
    help="The human layer for AI agents.",
    no_args_is_help=True,
)

app.command()(dev)
app.command()(add_user)
app.command()(version)

if __name__ == "__main__":
    app()
