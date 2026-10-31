# The context and passing objects

Every running command has a {class}`~clirelay.Context`. It holds the parsed
parameters, the parent context, a user object (`obj`), and lifecycle hooks.

## Reaching the context

```python
@clirelay.command()
@clirelay.pass_context
def cli(ctx):
    clirelay.echo(ctx.info_name)
```

Or from anywhere during a command:

```python
ctx = clirelay.get_current_context()
```

Outside of a command this raises `RuntimeError: There is no active click context.`

## Sharing an object

Set `ctx.obj` in a group and read it in subcommands:

```python
@clirelay.group()
@clirelay.pass_context
def cli(ctx):
    ctx.obj = {"verbose": False}

@cli.command()
@clirelay.pass_obj
def run(obj):
    ...
```

For typed objects, {func}`~clirelay.make_pass_decorator` finds (or creates) an
instance of a given class:

```python
pass_repo = clirelay.make_pass_decorator(Repo, ensure=True)
```

If no such object exists and `ensure` is false, it raises `RuntimeError: Managed
to invoke callback without a context object of type 'Repo' existing.`

## Lifecycle

- `ctx.call_on_close(fn)` registers cleanup run when the context closes.
- `ctx.with_resource(cm)` enters a context manager tied to the context.
- `ctx.exit(code)` exits, `ctx.fail(msg)` raises a usage error, `ctx.abort()`
  aborts.

## Parameter sources

`ctx.get_parameter_source(name)` reports where a value came from — the command
line, an environment variable, a default map, a prompt, or the default.
