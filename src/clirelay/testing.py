"""Testing helpers: run a command in isolation and inspect what it produced."""
from __future__ import annotations

import contextlib
import io
import os
import sys
import typing as t

from . import globals as _globals
from .core import Command
from .utils import make_str

if t.TYPE_CHECKING:
    from .core import Context


class EchoingStdin:
    """Wrap an input stream so reads are echoed to an output stream."""

    def __init__(self, input: t.BinaryIO, output: t.BinaryIO) -> None:
        self._input = input
        self._output = output
        self._paused = False

    def __getattr__(self, x: str) -> t.Any:
        return getattr(self._input, x)

    def _echo(self, rv: bytes) -> bytes:
        if not self._paused:
            self._output.write(rv)
        return rv

    def read(self, n: int = -1) -> bytes:
        return self._echo(self._input.read(n))

    def read1(self, n: int = -1) -> bytes:
        return self._echo(self._input.read1(n))  # type: ignore[attr-defined]

    def readline(self, n: int = -1) -> bytes:
        return self._echo(self._input.readline(n))

    def readlines(self) -> list[bytes]:
        return [self._echo(line) for line in self._input.readlines()]

    def __iter__(self) -> t.Iterator[bytes]:
        return iter(self._echo(line) for line in self._input)

    def __repr__(self) -> str:
        return repr(self._input)


@contextlib.contextmanager
def _pause_echo(stream: EchoingStdin | None) -> t.Iterator[None]:
    if stream is None:
        yield
    else:
        stream._paused = True
        yield
        stream._paused = False


class BytesIOCopy(io.BytesIO):
    """A BytesIO that also forwards every write to another buffer."""

    def __init__(self, copy_to: io.BytesIO) -> None:
        super().__init__()
        self.copy_to = copy_to

    def flush(self) -> None:
        super().flush()
        self.copy_to.flush()

    def write(self, b: t.Any) -> int:
        self.copy_to.write(b)
        return super().write(b)


class StreamMixer:
    """Keeps separate stdout/stderr buffers plus an interleaved copy."""

    def __init__(self) -> None:
        self.output = io.BytesIO()
        self.stdout = BytesIOCopy(copy_to=self.output)
        self.stderr = BytesIOCopy(copy_to=self.output)


class _NamedTextIO(io.TextIOWrapper):
    _isatty = False
    _name: str | None = None

    def isatty(self) -> bool:
        return self._isatty

    @property
    def name(self) -> t.Any:  # type: ignore[override]
        return self._name


def make_input_stream(
    input: str | bytes | t.IO[t.Any] | None, charset: str
) -> t.BinaryIO:
    if hasattr(input, "read"):
        rv = _find_binary_reader(t.cast("t.IO[t.Any]", input))
        if rv is not None:
            return rv
        raise TypeError("Could not find binary reader for input stream.")
    if input is None:
        input = b""
    elif isinstance(input, str):
        input = input.encode(charset)
    return io.BytesIO(t.cast(bytes, input))


def _find_binary_reader(stream: t.IO[t.Any]) -> t.BinaryIO | None:
    if isinstance(stream, (io.RawIOBase, io.BufferedIOBase)):
        return t.cast("t.BinaryIO", stream)
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        return buffer
    return None


class Result:
    """Everything a run produced, for assertions in tests."""

    def __init__(
        self,
        runner: CliRunner,
        stdout_bytes: bytes,
        stderr_bytes: bytes,
        output_bytes: bytes,
        return_value: t.Any,
        exit_code: int,
        exception: BaseException | None,
        exc_info: t.Any = None,
    ) -> None:
        self.runner = runner
        self.stdout_bytes = stdout_bytes
        self.stderr_bytes = stderr_bytes
        self.output_bytes = output_bytes
        self.return_value = return_value
        self.exit_code = exit_code
        self.exception = exception
        self.exc_info = exc_info

    @property
    def output(self) -> str:
        return self.output_bytes.decode(self.runner.charset, "replace").replace(
            "\r\n", "\n"
        )

    @property
    def stdout(self) -> str:
        return self.stdout_bytes.decode(self.runner.charset, "replace").replace(
            "\r\n", "\n"
        )

    @property
    def stderr(self) -> str:
        return self.stderr_bytes.decode(self.runner.charset, "replace").replace(
            "\r\n", "\n"
        )

    def __repr__(self) -> str:
        exc = repr(self.exception) if self.exception else "okay"
        return f"<{type(self).__name__} {exc}>"


class CliRunner:
    """Runs a command with isolated streams and environment."""

    def __init__(
        self,
        charset: str = "utf-8",
        env: t.Mapping[str, str | None] | None = None,
        echo_stdin: bool = False,
        catch_exceptions: bool = True,
        capture: str = "sys",
    ) -> None:
        self.charset = charset
        self.env: t.Mapping[str, str | None] = env or {}
        self.echo_stdin = echo_stdin
        self.catch_exceptions = catch_exceptions
        self.capture = capture

    def get_default_prog_name(self, cli: Command) -> str:
        return cli.name or "root"

    def make_env(
        self, overrides: t.Mapping[str, str | None] | None = None
    ) -> t.Mapping[str, str | None]:
        rv = dict(self.env)
        if overrides:
            rv.update(overrides)
        return rv

    @contextlib.contextmanager
    def isolation(
        self,
        input: str | bytes | t.IO[t.Any] | None = None,
        env: t.Mapping[str, str | None] | None = None,
        color: bool = False,
    ) -> t.Iterator[tuple[io.BytesIO, io.BytesIO, io.BytesIO]]:
        bytes_input = make_input_stream(input, self.charset)
        env = self.make_env(env)

        old_stdin, old_stdout, old_stderr = sys.stdin, sys.stdout, sys.stderr
        old_env: dict[str, str | None] = {}
        mixer = StreamMixer()

        from . import formatting as _formatting

        old_forced_width = _formatting.FORCED_WIDTH
        _formatting.FORCED_WIDTH = 80

        echo_input: EchoingStdin | None = None
        if self.echo_stdin:
            bytes_input = echo_input = EchoingStdin(bytes_input, mixer.stdout)  # type: ignore[assignment]
        text_input = _NamedTextIO(bytes_input, encoding=self.charset)
        text_input._name = "<stdin>"

        sys.stdin = text_input
        text_stdout = _NamedTextIO(
            mixer.stdout, encoding=self.charset, line_buffering=True, write_through=False
        )
        text_stderr = _NamedTextIO(
            mixer.stderr, encoding=self.charset, line_buffering=False, write_through=True
        )
        text_stdout._isatty = color
        text_stderr._isatty = color
        text_stdout._name = "<stdout>"
        text_stderr._name = "<stderr>"
        sys.stdout = text_stdout
        sys.stderr = text_stderr

        from . import termui as _termui

        old_visible = _termui.visible_prompt_func
        old_hidden = _termui.hidden_prompt_func

        def _prompt_out() -> t.IO[str]:
            # Echo onto the same stream the prompt went to (stderr when err=True).
            return sys.stderr if _termui._prompt_target_err else sys.stdout

        @_pause_echo(echo_input)  # type: ignore[arg-type]
        def visible_input(prompt: str | None = None) -> str:
            out = _prompt_out()
            out.write(prompt or "")
            line = text_input.readline()
            if not line:
                raise EOFError()
            val = line.rstrip("\r\n")
            out.write(f"{val}\n")
            return val

        @_pause_echo(echo_input)  # type: ignore[arg-type]
        def hidden_input(prompt: str | None = None) -> str:
            _prompt_out().write(f"{prompt or ''}\n")
            line = text_input.readline()
            if not line:
                raise EOFError()
            return line.rstrip("\r\n")

        _termui.visible_prompt_func = visible_input
        _termui.hidden_prompt_func = hidden_input

        for key, value in env.items():
            old_env[key] = os.environ.get(key)
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

        try:
            yield (mixer.stdout, mixer.stderr, mixer.output)
        finally:
            try:
                text_stdout.flush()
                text_stderr.flush()
            except Exception:
                pass
            for key, value in old_env.items():
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value
            sys.stdin, sys.stdout, sys.stderr = old_stdin, old_stdout, old_stderr
            _termui.visible_prompt_func = old_visible
            _termui.hidden_prompt_func = old_hidden
            _formatting.FORCED_WIDTH = old_forced_width

    def invoke(
        self,
        cli: Command,
        args: str | t.Sequence[str] | None = None,
        input: str | bytes | t.IO[t.Any] | None = None,
        env: t.Mapping[str, str | None] | None = None,
        catch_exceptions: bool | None = None,
        color: bool = False,
        **extra: t.Any,
    ) -> Result:
        if catch_exceptions is None:
            catch_exceptions = self.catch_exceptions

        exc_info = None
        return_value = None
        exception: BaseException | None = None
        exit_code: t.Any = 0

        if isinstance(args, str):
            from .shell_completion import split_arg_string

            args = split_arg_string(args)

        with self.isolation(input=input, env=env, color=color) as outstreams:
            with _clear_context():
                if "prog_name" not in extra:
                    extra["prog_name"] = self.get_default_prog_name(cli)
                try:
                    return_value = cli.main(args=args or (), **extra)
                except SystemExit as e:
                    exc_info = sys.exc_info()
                    e_code = t.cast("int | t.Any | None", e.code)
                    if e_code is None:
                        e_code = 0
                    if e_code != 0:
                        exception = e
                    if not isinstance(e_code, int):
                        sys.stdout.write(str(e_code))
                        sys.stdout.write("\n")
                        e_code = 1
                    exit_code = e_code
                except Exception as e:
                    if not catch_exceptions:
                        raise
                    exit_code = 1
                    exception = e
                    exc_info = sys.exc_info()
                finally:
                    try:
                        sys.stdout.flush()
                        sys.stderr.flush()
                    except Exception:
                        pass
                    stdout = outstreams[0].getvalue()
                    stderr = outstreams[1].getvalue()
                    output = outstreams[2].getvalue()

        return Result(
            runner=self,
            stdout_bytes=stdout,
            stderr_bytes=stderr,
            output_bytes=output,
            return_value=return_value,
            exit_code=exit_code,
            exception=exception,
            exc_info=exc_info,
        )

    @contextlib.contextmanager
    def isolated_filesystem(
        self, temp_dir: str | os.PathLike[str] | None = None
    ) -> t.Iterator[str]:
        import tempfile
        import shutil
        import warnings

        warnings.warn(
            "'isolated_filesystem' is deprecated and will be removed in Click 9.0. "
            "Use 'tempfile.TemporaryDirectory' or pytest's 'tmp_path' fixture with "
            "absolute paths instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        cwd = os.getcwd()
        dt = tempfile.mkdtemp(dir=temp_dir)
        os.chdir(dt)
        try:
            yield dt
        finally:
            os.chdir(cwd)
            if temp_dir is None:
                with contextlib.suppress(OSError):
                    shutil.rmtree(dt)


@contextlib.contextmanager
def _clear_context() -> t.Iterator[None]:
    stack = _globals._get_stack()
    saved = list(stack)
    stack.clear()
    try:
        yield
    finally:
        stack.clear()
        stack.extend(saved)
