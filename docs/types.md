# Parameter types

A parameter type converts a raw command-line string into a Python value and
reports a clear error when the value is unacceptable. Pass one with `type=`.

## Built-in types

| Type | Accepts |
|------|---------|
| `clirelay.STRING` | any text (the default) |
| `clirelay.INT` | an integer |
| `clirelay.FLOAT` | a floating-point number |
| `clirelay.BOOL` | `1/0`, `true/false`, `yes/no`, `on/off`, `t/f`, `y/n` |
| `clirelay.UUID` | a UUID |
| `clirelay.UNPROCESSED` | the raw string, unconverted |

You can also pass a plain Python type (`int`, `float`, `bool`, `str`) and
clirelay picks the matching parameter type.

## Choices

```python
clirelay.Choice(["red", "green", "blue"])
clirelay.Choice(["Red", "Green"], case_sensitive=False)
```

`Choice` also accepts an `Enum`; it then matches member *names* and shows them in
help.

## Numeric ranges

```python
clirelay.IntRange(0, 10)              # 0 <= x <= 10
clirelay.IntRange(0, None, min_open=True)  # x > 0
clirelay.FloatRange(0, 1, clamp=True)      # out-of-range values are clamped
```

## Dates, tuples, files, and paths

```python
clirelay.DateTime(["%Y-%m-%d"])
clirelay.Tuple([int, str])
clirelay.File("r")                 # open for reading; "-" means stdin
clirelay.Path(exists=True, dir_okay=False)
```

## Custom types

Subclass {class}`~clirelay.ParamType`, set `name`, and implement `convert`:

```python
class URL(clirelay.ParamType):
    name = "url"

    def convert(self, value, param, ctx):
        if not value.startswith(("http://", "https://")):
            self.fail(f"{value!r} is not a valid URL.", param, ctx)
        return value
```

`ParamType` is generic, so `clirelay.ParamType[str]` is also valid as a base.
