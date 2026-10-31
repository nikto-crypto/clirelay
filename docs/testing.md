# Testing with CliRunner

{class}`~clirelay.testing.CliRunner` runs a command in isolation and captures
everything it produced, without spawning a subprocess.

```python
from clirelay.testing import CliRunner
from mytool import cli

def test_hello():
    runner = CliRunner()
    result = runner.invoke(cli, ["--count", "2", "World"])
    assert result.exit_code == 0
    assert result.output == "Hello, World!\nHello, World!\n"
```

## The Result

{class}`~clirelay.testing.Result` exposes:

- `exit_code`
- `output` — stdout and stderr interleaved in write order
- `stdout`, `stderr` — each stream on its own
- `output_bytes`, `stdout_bytes`, `stderr_bytes`
- `return_value` — the callback's return value (with `standalone_mode=False`)
- `exception`, `exc_info` — any exception that escaped

## Supplying input and environment

```python
result = runner.invoke(cli, [], input="Alice\n")
result = runner.invoke(cli, [], env={"APP_TOKEN": "secret"})
```

Scripted input drives prompts; the typed text is echoed into the captured output
just as a terminal would show it.

## Isolating the filesystem

Use a temporary directory for tests that read or write files:

```python
import tempfile, os

with tempfile.TemporaryDirectory() as d:
    os.chdir(d)
    ...
```

(The older `runner.isolated_filesystem()` still works but is deprecated.)
