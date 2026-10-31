# Options

Options are optional, named parameters. Declare them with
`@clirelay.option(...)`.

## Names and values

```python
@clirelay.option("--count", "-c", default=1)
```

The long name determines the Python parameter name (`count`). An option takes a
value unless it is a flag or a counter.

## Flags

```python
@clirelay.option("--shout/--no-shout", default=False)   # on/off pair
@clirelay.option("--debug", is_flag=True)               # simple flag
@clirelay.option("-v", "--verbose", count=True)         # repeatable counter
```

A `--x/--no-x` pair sets its destination to `True` or `False`. A counter counts
how many times the flag appears.

## Multiple values

```python
@clirelay.option("--tag", multiple=True)     # --tag a --tag b -> ('a', 'b')
@clirelay.option("--pos", nargs=2, type=int) # --pos 1 2 -> (1, 2)
```

## Required, defaults, and environment variables

```python
@clirelay.option("--name", required=True)
@clirelay.option("--token", envvar="APP_TOKEN")
@clirelay.option("--host", default="127.0.0.1", show_default=True)
```

Set `auto_envvar_prefix` on the context to derive environment variable names
automatically.

## Showing defaults and extras

The help line can show a default, a required marker, a range, and an environment
variable:

```python
@clirelay.option("--level", type=clirelay.IntRange(0, 10),
                 show_default=True, show_envvar=True, envvar="LEVEL")
```

renders as:

```text
--level INTEGER RANGE  [env var: LEVEL; default: 0; 0<=x<=10]
```

## Deprecating an option

```python
@clirelay.option("--old", deprecated=True)
@clirelay.option("--older", deprecated="use --new")
```

Using one prints a `DeprecationWarning: The option 'old' is deprecated.` line to
stderr, and the help line is labeled `(DEPRECATED)`.
