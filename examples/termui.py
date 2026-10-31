"""Terminal UI helpers: progress bars, pager, and pause.

Run:
    python examples/termui.py count --total 20
    python examples/termui.py page
"""
from __future__ import annotations

import time

import clirelay


@clirelay.group()
def cli():
    """Demonstrate terminal UI helpers."""


@cli.command()
@clirelay.option("--total", default=10, help="How many items.")
def count(total):
    """Show a progress bar while counting."""
    with clirelay.progressbar(range(total), label="Counting") as items:
        for _ in items:
            time.sleep(0.01)
    clirelay.echo("Done.")


@cli.command()
def page():
    """Show a lot of text through the pager."""
    text = "\n".join(f"Line {i}" for i in range(200))
    clirelay.echo_via_pager(text)


@cli.command()
def wait():
    """Pause until a key is pressed."""
    clirelay.pause()
    clirelay.echo("Continuing.")


if __name__ == "__main__":
    cli()
