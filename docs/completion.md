# Shell completion

clirelay generates completion scripts for bash, zsh, fish, and PowerShell.

## Enabling completion

Each shell evaluates a small script produced by your program. The completion
variable is `_<PROG>_COMPLETE`, upper-cased with dashes turned into underscores.

Bash:

```console
$ eval "$(_MYTOOL_COMPLETE=bash_source mytool)"
```

Zsh:

```console
$ eval "$(_MYTOOL_COMPLETE=zsh_source mytool)"
```

Fish:

```console
$ _MYTOOL_COMPLETE=fish_source mytool | source
```

PowerShell:

```powershell
_MYTOOL_COMPLETE=powershell_source mytool | Out-String | Invoke-Expression
```

Usually you add the appropriate line to your shell's startup file.

## What completes

Out of the box, clirelay completes subcommand names, option names, and the values
of `Choice` parameters.

## Custom completion

Give a parameter a `shell_complete` callback that returns
{class}`~clirelay.shell_completion.CompletionItem` objects (or plain strings):

```python
from clirelay.shell_completion import CompletionItem

def complete_env(ctx, param, incomplete):
    return [CompletionItem(e) for e in ("dev", "prod") if e.startswith(incomplete)]

@clirelay.option("--env", shell_complete=complete_env)
def cli(env):
    ...
```

A custom parameter type can also implement `shell_complete`.
