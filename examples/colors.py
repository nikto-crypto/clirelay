"""Colored output with style/secho.

Run:
    python examples/colors.py --name Ada
"""
from __future__ import annotations

import clirelay


@clirelay.command()
@clirelay.option("--name", default="world", help="Who to greet.")
def cli(name):
    """Print a greeting in color."""
    clirelay.secho("Success!", fg="green", bold=True)
    clirelay.secho("Warning: this is just a demo.", fg="yellow")
    clirelay.secho("Error-looking text (not a real error).", fg="red")
    greeting = clirelay.style("Hello, ", fg="cyan") + clirelay.style(
        name, fg="magenta", underline=True
    )
    clirelay.echo(greeting)


if __name__ == "__main__":
    cli()
