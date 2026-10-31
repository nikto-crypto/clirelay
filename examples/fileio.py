"""File input and output with the File parameter type.

Run:
    echo hello | python examples/fileio.py - -
    python examples/fileio.py input.txt output.txt
"""
from __future__ import annotations

import clirelay


@clirelay.command()
@clirelay.argument("src", type=clirelay.File("r"))
@clirelay.argument("dst", type=clirelay.File("w"))
@clirelay.option("--upper", is_flag=True, help="Upper-case the text.")
def cli(src, dst, upper):
    """Copy SRC to DST, optionally upper-casing it. Use - for stdin/stdout."""
    text = src.read()
    if upper:
        text = text.upper()
    dst.write(text)


if __name__ == "__main__":
    cli()
