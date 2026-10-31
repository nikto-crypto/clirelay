# clirelay

clirelay is a composable command-line interface toolkit for Python. You write a
function, decorate it to describe its options and arguments, and clirelay takes
care of parsing the command line, converting and validating values, rendering
`--help`, reporting usage errors, prompting for input, and generating shell
completion scripts.

```python
import clirelay

@clirelay.command()
@clirelay.option("--count", default=1, help="Number of greetings.")
@clirelay.argument("name")
def hello(count, name):
    """Greet NAME COUNT times."""
    for _ in range(count):
        clirelay.echo(f"Hello, {name}!")

if __name__ == "__main__":
    hello()
```

```console
$ python hello.py --count 2 World
Hello, World!
Hello, World!
```

## Features

- Nested commands and groups, with chaining and lazy command loading.
- A rich set of parameter types: integers, floats, bounded ranges, choices
  (including `Enum`-backed), dates, UUIDs, tuples, files, and paths.
- Automatic, wrapped `--help` output that adapts to the terminal width.
- Interactive prompts, confirmations, hidden input, and progress bars.
- Shell completion for bash, zsh, fish, and PowerShell.
- A `CliRunner` for testing commands without spawning subprocesses.

## Install

clirelay has no runtime dependencies and supports Python 3.10 and newer.

```console
$ pip install clirelay
```

## Documentation

The documentation lives under `docs/` and is built with Sphinx + MyST:

```console
$ uv run --group docs sphinx-build -b html docs docs/_build/html
```

## Development and the differential test suite

clirelay is validated against a reference implementation (the *oracle*) with a
differential test suite. The oracle is a bytecode-only install kept out of this
repository; the suite imports it as a black box, builds the *same* program
against both libraries, and compares every observable channel.

### Building the oracle

The suite expects the oracle under `~/clirelay-oracle` (override with
`CLIRELAY_ORACLE_DIR`), laid out as:

```
~/clirelay-oracle/
  click/                 # the reference package (bytecode)
  API_SURFACE.json       # the public API surface (names, kinds, signatures)
  ORACLE_PYTHON.txt       # "<major> <minor> <bytecode-magic-hex>" + interpreter path
```

The suite only runs when the live interpreter's minor version and bytecode magic
number match `ORACLE_PYTHON.txt`; otherwise the differential tests skip. Set
`CLIRELAY_REQUIRE_ORACLE=1` to turn those skips into failures.

### Running the suite

```console
$ uv venv --python "$(sed -n 2p ~/clirelay-oracle/ORACLE_PYTHON.txt)"
$ uv pip install -e . pytest hypothesis
$ CLIRELAY_REQUIRE_ORACLE=1 .venv/bin/python -m pytest -rs -p no:warnings
```

Other Python versions run the unit tests only.

## License

MIT. See `LICENSE.txt`.
