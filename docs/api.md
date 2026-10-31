# API reference

## Decorators

```{eval-rst}
.. autofunction:: clirelay.command
.. autofunction:: clirelay.group
.. autofunction:: clirelay.option
.. autofunction:: clirelay.argument
.. autofunction:: clirelay.pass_context
.. autofunction:: clirelay.pass_obj
.. autofunction:: clirelay.make_pass_decorator
.. autofunction:: clirelay.version_option
.. autofunction:: clirelay.help_option
.. autofunction:: clirelay.password_option
.. autofunction:: clirelay.confirmation_option
```

## Commands and parameters

```{eval-rst}
.. autoclass:: clirelay.Context
   :members:
.. autoclass:: clirelay.Command
   :members:
.. autoclass:: clirelay.Group
   :members:
.. autoclass:: clirelay.CommandCollection
   :members:
.. autoclass:: clirelay.Parameter
   :members:
.. autoclass:: clirelay.Option
   :members:
.. autoclass:: clirelay.Argument
   :members:
```

## Parameter types

```{eval-rst}
.. autoclass:: clirelay.ParamType
   :members:
.. autoclass:: clirelay.Choice
.. autoclass:: clirelay.IntRange
.. autoclass:: clirelay.FloatRange
.. autoclass:: clirelay.DateTime
.. autoclass:: clirelay.Tuple
.. autoclass:: clirelay.File
.. autoclass:: clirelay.Path
```

## Terminal and utilities

```{eval-rst}
.. autofunction:: clirelay.echo
.. autofunction:: clirelay.secho
.. autofunction:: clirelay.style
.. autofunction:: clirelay.unstyle
.. autofunction:: clirelay.prompt
.. autofunction:: clirelay.confirm
.. autofunction:: clirelay.progressbar
.. autofunction:: clirelay.get_app_dir
.. autofunction:: clirelay.format_filename
.. autofunction:: clirelay.open_file
.. autofunction:: clirelay.wrap_text
.. autoclass:: clirelay.HelpFormatter
   :members:
```

## Exceptions

```{eval-rst}
.. autoexception:: clirelay.ClickException
.. autoexception:: clirelay.UsageError
.. autoexception:: clirelay.BadParameter
.. autoexception:: clirelay.MissingParameter
.. autoexception:: clirelay.NoSuchOption
.. autoexception:: clirelay.NoSuchCommand
.. autoexception:: clirelay.FileError
.. autoexception:: clirelay.Abort
```

## Testing

```{eval-rst}
.. autoclass:: clirelay.testing.CliRunner
   :members:
.. autoclass:: clirelay.testing.Result
   :members:
```
