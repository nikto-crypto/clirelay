# Quickstart

Install clirelay and write your first command.

## Install

```console
$ pip install clirelay
```

clirelay needs Python 3.10+ and has no runtime dependencies.

## A single command

A command is an ordinary function with decorators:

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

Running it:

```console
$ python hello.py --count 2 World
Hello, World!
Hello, World!
$ python hello.py --help
Usage: hello.py [OPTIONS] NAME

  Greet NAME COUNT times.

Options:
  --count INTEGER  Number of greetings.
  --help           Show this message and exit.
```

## A group of commands

Group related commands under a parent:

```python
@clirelay.group()
def cli():
    """A small tool."""

@cli.command()
def init():
    """Initialize things."""
    clirelay.echo("initialized")

@cli.command()
@clirelay.argument("name")
def add(name):
    """Add NAME."""
    clirelay.echo(f"added {name}")
```

```console
$ python tool.py add thing
added thing
```

Next, read about [commands and groups](commands.md), [options](options.md), and
[arguments](arguments.md).
