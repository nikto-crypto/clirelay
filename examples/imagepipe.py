"""An image-style processing pipeline using a chained group.

Run:
    python examples/imagepipe.py load -i cat.png resize -w 100 save -o out.png
"""
from __future__ import annotations

import clirelay


@clirelay.group(chain=True, invoke_without_command=True)
@clirelay.pass_context
def cli(ctx):
    """Process images through a chain of steps."""


@cli.result_callback()
def run_pipeline(steps):
    clirelay.echo("Pipeline finished with steps: " + ", ".join(steps))


@cli.command()
@clirelay.option("-i", "--input", "src", required=True, help="Input file.")
def load(src):
    """Load an image."""
    clirelay.echo(f"load {src}")
    return f"load({src})"


@cli.command()
@clirelay.option("-w", "--width", type=int, required=True, help="New width.")
def resize(width):
    """Resize the image."""
    clirelay.echo(f"resize to {width}px")
    return f"resize({width})"


@cli.command()
@clirelay.option("-o", "--output", "dst", required=True, help="Output file.")
def save(dst):
    """Save the image."""
    clirelay.echo(f"save {dst}")
    return f"save({dst})"


if __name__ == "__main__":
    cli()
