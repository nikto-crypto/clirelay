# Terminal utilities

Beyond prompts, clirelay offers helpers for richer terminal output.

## Echo and styling

```python
clirelay.echo("plain text")
clirelay.echo("to stderr", err=True)
clirelay.secho("done", fg="green", bold=True)
styled = clirelay.style("warn", fg="yellow", underline=True)
clirelay.echo(clirelay.unstyle(styled))   # strips the codes
```

`echo` removes ANSI codes automatically when the destination is not a terminal.

## Progress bars

```python
with clirelay.progressbar(range(100), label="Working") as items:
    for item in items:
        do_work(item)
```

## Pager and editor

```python
clirelay.echo_via_pager(long_text)
edited = clirelay.edit("initial content")    # opens $EDITOR
```

## Single key input and pausing

```python
char = clirelay.getchar()
clirelay.pause()          # "Press any key to continue..."
clirelay.clear()          # clear the screen
```

## Opening things

```python
clirelay.launch("https://example.com")       # open in the default app
clirelay.launch("/path/to/file", locate=True)
```

## Application directories and files

```python
cfg_dir = clirelay.get_app_dir("My App")
with clirelay.open_file("-", "r") as f:       # "-" is stdin
    data = f.read()
```
