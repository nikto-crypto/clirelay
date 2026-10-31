# Commands and groups

## Commands

`@clirelay.command()` turns a function into a {class}`~clirelay.Command`. The
function's docstring becomes the help text, and its name becomes the command name
(underscores become dashes, and a trailing `_cmd`, `_command`, `_grp`, or
`_group` is stripped).

```python
@clirelay.command()
def sync_cmd():
    """Synchronize."""
```

This registers a command named `sync`. Pass an explicit name if you prefer:

```python
@clirelay.command("do-sync")
def sync():
    ...
```

## Groups

A {class}`~clirelay.Group` dispatches to subcommands. Attach commands with the
group's `command` and `group` decorators:

```python
@clirelay.group()
def cli():
    """Top-level tool."""

@cli.command()
def build():
    """Build the project."""

@cli.group()
def db():
    """Database commands."""

@db.command()
def migrate():
    """Run migrations."""
```

Invoking a group with no subcommand shows its help and exits with status 2,
unless you set `invoke_without_command=True`.

## Chaining

With `chain=True`, several subcommands run in sequence in a single invocation:

```python
@clirelay.group(chain=True)
def pipeline():
    ...
```

```console
$ python app.py load resize save
```

A {meth}`~clirelay.Group.result_callback` receives the list of subcommand return
values once the chain finishes.

## Custom classes

Subclass {class}`~clirelay.Group` to customize command resolution — for example,
to support aliases — and pass it with `cls=`:

```python
@clirelay.group(cls=AliasedGroup)
def cli():
    ...
```
