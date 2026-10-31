# Arguments

Arguments are positional parameters. Declare them with
`@clirelay.argument(...)`.

```python
@clirelay.argument("src")
@clirelay.argument("dst")
```

Arguments are required by default. Make one optional with `required=False` and a
`default`.

## Variadic arguments

`nargs=-1` collects any number of values into a tuple:

```python
@clirelay.argument("files", nargs=-1)
```

A command may have at most one variadic argument. `nargs=2` collects a fixed
number of values.

## Types

Arguments accept the same [parameter types](types.md) as options:

```python
@clirelay.argument("count", type=int)
@clirelay.argument("color", type=clirelay.Choice(["r", "g", "b"]))
```

A required `Choice` argument shows its options in braces in the usage line, e.g.
`{r|g|b}`.

## Help for arguments

Arguments can carry help text, which places them in a `Positional arguments:`
section before `Options:`:

```python
@clirelay.argument("name", help="The name to use.")
```

## Deprecating an argument

```python
@clirelay.argument("src", deprecated=True)
```

The argument appears as `[SRC!]` in the usage line, and using it prints a
`DeprecationWarning` to stderr.
