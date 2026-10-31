"""Command aliases via a custom Group.

Run:
    python examples/aliases.py st
    python examples/aliases.py status
"""
from __future__ import annotations

import clirelay


class AliasedGroup(clirelay.Group):
    """A group that resolves unambiguous command prefixes and explicit aliases."""

    aliases = {"st": "status", "co": "checkout"}

    def get_command(self, ctx, cmd_name):
        cmd_name = self.aliases.get(cmd_name, cmd_name)
        rv = super().get_command(ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [n for n in self.list_commands(ctx) if n.startswith(cmd_name)]
        if len(matches) == 1:
            return super().get_command(ctx, matches[0])
        return None


@clirelay.group(cls=AliasedGroup)
def cli():
    """A tiny version-control-style tool with aliases."""


@cli.command()
def status():
    """Show the working tree status."""
    clirelay.echo("On branch main, nothing to commit.")


@cli.command()
@clirelay.argument("branch")
def checkout(branch):
    """Switch branches."""
    clirelay.echo(f"Switched to branch {branch!r}.")


if __name__ == "__main__":
    cli()
