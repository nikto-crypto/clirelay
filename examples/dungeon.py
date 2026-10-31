"""A small game-style app with nested commands and prompts.

Run:
    python examples/dungeon.py new --name Hero
    python examples/dungeon.py room enter --door north
"""
from __future__ import annotations

import clirelay


@clirelay.group()
def cli():
    """A tiny text-adventure controller."""


@cli.command()
@clirelay.option("--name", prompt="Hero name", help="Your character's name.")
@clirelay.option(
    "--class", "hero_class",
    type=clirelay.Choice(["warrior", "mage", "rogue"]),
    prompt="Choose a class",
)
def new(name, hero_class):
    """Start a new game."""
    clirelay.echo(f"Welcome, {name} the {hero_class}!")


@cli.group()
def room():
    """Interact with the current room."""


@room.command()
@clirelay.option(
    "--door",
    type=clirelay.Choice(["north", "south", "east", "west"]),
    default="north",
    show_default=True,
)
def enter(door):
    """Walk through a door."""
    clirelay.echo(f"You go {door} and find a treasure chest.")


@room.command()
def fight():
    """Fight whatever is in the room."""
    if clirelay.confirm("A goblin appears. Attack?"):
        clirelay.echo("You win!")
    else:
        clirelay.echo("You flee.")


if __name__ == "__main__":
    cli()
