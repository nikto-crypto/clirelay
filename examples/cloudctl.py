"""A complex multi-command application with nested groups and a shared context.

Run:
    python examples/cloudctl.py --profile prod vm list
    python examples/cloudctl.py vm create web-1 --size large
"""
from __future__ import annotations

import clirelay


class Config:
    def __init__(self):
        self.profile = "default"
        self.verbose = False


pass_config = clirelay.make_pass_decorator(Config, ensure=True)


@clirelay.group(help="Manage a pretend cloud.")
@clirelay.option("--profile", default="default", help="Credentials profile.")
@clirelay.option("-v", "--verbose", count=True, help="Increase verbosity.")
@pass_config
def cli(config, profile, verbose):
    config.profile = profile
    config.verbose = verbose


@cli.group()
def vm():
    """Manage virtual machines."""


@vm.command("list")
@pass_config
def vm_list(config):
    """List virtual machines."""
    clirelay.echo(f"[{config.profile}] vm-1, vm-2")


@vm.command()
@clirelay.argument("name")
@clirelay.option("--size", type=clirelay.Choice(["small", "large"]), default="small")
@pass_config
def create(config, name, size):
    """Create a virtual machine."""
    clirelay.echo(f"[{config.profile}] created {name} ({size})")


@cli.group()
def db():
    """Manage databases."""


@db.command("list")
@pass_config
def db_list(config):
    """List databases."""
    clirelay.echo(f"[{config.profile}] main, analytics")


if __name__ == "__main__":
    cli()
