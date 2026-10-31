# Exceptions and exit codes

clirelay reports problems through an exception hierarchy rooted at
{class}`~clirelay.ClickException`. In standalone mode these are caught, printed,
and turned into an exit code instead of a traceback.

## The hierarchy

- {class}`~clirelay.ClickException` — a reportable error (exit code 1).
  - {class}`~clirelay.UsageError` — the command line was used wrongly (exit 2).
    - {class}`~clirelay.BadParameter` — a bad value for a parameter.
      - {class}`~clirelay.MissingParameter` — a required parameter is missing.
    - {class}`~clirelay.NoSuchOption`, {class}`~clirelay.BadOptionUsage`,
      {class}`~clirelay.BadArgumentUsage`, {class}`~clirelay.NoSuchCommand`.
  - {class}`~clirelay.FileError` — a file could not be opened.
- {class}`~clirelay.Abort` — abort with `Aborted!` (exit 1).

## Exit codes

| Situation | Exit code |
|-----------|-----------|
| Success | 0 |
| `ClickException` | 1 |
| Usage error | 2 |
| Abort / Ctrl-C | 1 |
| `ctx.exit(n)` | n |

## Raising your own

```python
@clirelay.command()
def cli():
    raise clirelay.ClickException("something went wrong")
```

prints `Error: something went wrong` to stderr and exits 1. Inside a command,
`ctx.fail("...")` raises a {class}`~clirelay.UsageError` with the usage banner.

## Turning off standalone mode

Call the command with `standalone_mode=False` to get the return value and let
exceptions propagate instead of exiting:

```python
result = cli(["--count", "3"], standalone_mode=False)
```
