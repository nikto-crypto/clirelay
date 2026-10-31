# clirelay examples

Small, self-contained applications showing clirelay's feature areas. Run any of
them with the project's Python, e.g.:

```console
$ python examples/colors.py --name Ada
```

| File | Shows |
|------|-------|
| `aliases.py` | Command aliases and prefix matching via a custom `Group` |
| `colors.py` | Colored output with `style` / `secho` |
| `completion.py` | Shell completion with a custom completer |
| `cloudctl.py` | A complex multi-command app with nested groups and a shared object |
| `imagepipe.py` | An image-style processing pipeline with a chained group |
| `fileio.py` | File input/output with the `File` type and `-` for stdin/stdout |
| `dungeon.py` | A game-style nested app with prompts and confirmations |
| `repo.py` | A repository-style tool passing an object down the command tree |
| `termui.py` | Terminal UI helpers: progress bars, pager, pause |
| `validation.py` | Custom validation with callbacks and a custom `ParamType` |
