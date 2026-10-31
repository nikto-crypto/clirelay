# Help and documentation formatting

clirelay renders `--help` automatically from your docstrings, option help, and
parameter types.

## Help text

A command's docstring becomes its help. Within it:

- blank lines separate paragraphs, which are re-wrapped to the terminal width;
- a paragraph beginning with a `\b` escape keeps its exact line breaks;
- a `\f` escape truncates the help at that point.

```python
@clirelay.command()
def cli():
    """Short summary.

    \b
    A table:
      a   1
      b   2

    More prose that will be wrapped normally.
    """
```

## Short help in listings

In a group's command list, the short help is the first sentence of the
docstring (or the explicit `short_help`), truncated with `...` if it is long.

## Widths

Help is wrapped to the terminal width, capped at `max_content_width` (80 by
default). Set `terminal_width` or `max_content_width` through `context_settings`
to control it.

## The HelpFormatter

For custom help output, use {class}`~clirelay.HelpFormatter` directly:

```python
formatter = clirelay.HelpFormatter(width=80)
formatter.write_usage("prog", "[OPTIONS]")
with formatter.section("Options"):
    formatter.write_dl([("--foo", "Do the foo thing.")])
print(formatter.getvalue())
```

The standalone {func}`~clirelay.wrap_text` function wraps a single string.
