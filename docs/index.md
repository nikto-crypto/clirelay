# clirelay

clirelay is a composable command-line interface toolkit for Python. You write a
function, decorate it to describe its options and arguments, and clirelay handles
the rest: parsing, type conversion, help, errors, prompts, and shell completion.

```python
import clirelay

@clirelay.command()
@clirelay.option("--count", default=1, help="Number of greetings.")
@clirelay.argument("name")
def hello(count, name):
    """Greet NAME COUNT times."""
    for _ in range(count):
        clirelay.echo(f"Hello, {name}!")
```

```{toctree}
:maxdepth: 2
:caption: Guide

quickstart
commands
options
arguments
types
prompts
help
context
exceptions
completion
testing
termui
```

```{toctree}
:maxdepth: 2
:caption: Reference

api
```

## Indices

- {ref}`genindex`
- {ref}`modindex`
