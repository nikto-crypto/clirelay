"""The exception hierarchy.

Everything a command can raise to signal a problem lives here.  The two most
important behaviours are :meth:`ClickException.format_message` (the human text of
the problem) and :meth:`ClickException.show` (writing that text, with a usage
banner for usage errors, to a stream).
"""
from __future__ import annotations

import typing as t

from .utils import echo, format_filename

if t.TYPE_CHECKING:
    from .core import Context, Parameter


def _join_hints(parts: t.Sequence[str]) -> str:
    return " / ".join(f"'{p}'" for p in parts)


class ClickException(Exception):
    """A problem that should be reported to the user rather than tracebacked."""

    #: the process exit status that accompanies this error
    exit_code = 1

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message

    def format_message(self) -> str:
        return self.message

    def __str__(self) -> str:
        return self.message

    def show(self, file: t.IO[t.Any] | None = None) -> None:
        if file is None:
            file = _stderr()
        echo(f"Error: {self.format_message()}", file=file)


class UsageError(ClickException):
    """The command line was used incorrectly."""

    exit_code = 2

    def __init__(self, message: str, ctx: Context | None = None) -> None:
        super().__init__(message)
        self.ctx = ctx
        self.cmd = self.ctx.command if self.ctx else None

    def show(self, file: t.IO[t.Any] | None = None) -> None:
        if file is None:
            file = _stderr()
        color = None
        hint = ""
        if self.ctx is not None:
            color = self.ctx.color
            if self.cmd is not None and self.cmd.get_help_option(self.ctx) is not None:
                option = _help_hint_name(self.ctx.help_option_names)
                hint = (
                    f"Try '{self.ctx.command_path} {option}' for help.\n"
                )
            echo(f"{self.ctx.get_usage()}\n{hint}", file=file, color=color)
        echo(f"Error: {self.format_message()}", file=file, color=color)


class BadParameter(UsageError):
    """A value for a parameter could not be accepted."""

    def __init__(
        self,
        message: str,
        ctx: Context | None = None,
        param: Parameter | None = None,
        param_hint: t.Sequence[str] | str | None = None,
    ) -> None:
        super().__init__(message, ctx)
        self.param = param
        self.param_hint = param_hint

    def format_message(self) -> str:
        if self.param_hint is not None:
            hint = self.param_hint
        elif self.param is not None:
            hint = self.param.get_error_hint(self.ctx)
        else:
            return f"Invalid value: {self.message}"

        if isinstance(hint, str):
            hint_text = hint
        else:
            hint_text = _join_hints(hint)
        return f"Invalid value for {hint_text}: {self.message}"


class MissingParameter(BadParameter):
    """A required parameter was not supplied."""

    def __init__(
        self,
        message: str | None = None,
        ctx: Context | None = None,
        param: Parameter | None = None,
        param_hint: t.Sequence[str] | str | None = None,
        param_type: str | None = None,
    ) -> None:
        super().__init__(message or "", ctx, param, param_hint)
        self.param_type = param_type

    def format_message(self) -> str:
        if self.param_hint is not None:
            hint: t.Any = self.param_hint
        elif self.param is not None:
            hint = self.param.get_error_hint(self.ctx)
        else:
            hint = None

        if hint is None:
            hint_text = ""
        elif isinstance(hint, str):
            hint_text = f" {hint}"
        else:
            hint_text = f" {_join_hints(hint)}"

        param_type = self.param_type
        if param_type is None and self.param is not None:
            param_type = self.param.param_type_name

        extra = ""
        if self.message:
            extra = self.message
        elif self.param is not None:
            missing = self.param.type.get_missing_message(self.param, self.ctx)
            if missing:
                extra = missing

        msg = f"Missing {param_type}{hint_text}."
        if extra:
            msg = f"{msg} {extra}"
        return msg


class NoSuchOption(UsageError):
    """An unknown option name was seen on the command line."""

    def __init__(
        self,
        option_name: str,
        message: str | None = None,
        possibilities: t.Iterable[str] | None = None,
        ctx: Context | None = None,
    ) -> None:
        if message is None:
            message = f"No such option '{option_name}'."
        super().__init__(message, ctx)
        self.option_name = option_name
        self.possibilities = possibilities

    def format_message(self) -> str:
        return _with_suggestions(self.message, self.possibilities)


class BadOptionUsage(UsageError):
    """An option was supplied in a way it does not allow."""

    def __init__(
        self, option_name: str, message: str, ctx: Context | None = None
    ) -> None:
        super().__init__(message, ctx)
        self.option_name = option_name


class BadArgumentUsage(UsageError):
    """A positional argument was supplied in a way it does not allow."""


class NoSuchCommand(UsageError):
    """A subcommand name did not resolve."""

    def __init__(
        self,
        command_name: str,
        message: str | None = None,
        possibilities: t.Iterable[str] | None = None,
        ctx: Context | None = None,
    ) -> None:
        if message is None:
            message = f"No such command '{command_name}'."
        super().__init__(message, ctx)
        self.command_name = command_name
        self.possibilities = possibilities

    def format_message(self) -> str:
        return _with_suggestions(self.message, self.possibilities)


class NoArgsIsHelpError(UsageError):
    """A group was called with no arguments and is configured to show help."""

    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx
        super().__init__(ctx.get_help(), ctx=ctx)

    def show(self, file: t.IO[t.Any] | None = None) -> None:
        if file is None:
            file = _stderr()
        echo(self.format_message(), file=file, color=self.ctx.color)


class FileError(ClickException):
    """A file named on the command line could not be opened."""

    def __init__(self, filename: str, hint: str | None = None) -> None:
        if hint is None:
            hint = "unknown error"
        super().__init__(hint)
        self.ui_filename = format_filename(filename)
        self.filename = filename

    def format_message(self) -> str:
        return f"Could not open file '{self.ui_filename}': {self.message}"


class Abort(RuntimeError):
    """Raised to abort a command, printing ``Aborted!``."""


class Exit(RuntimeError):
    """Raised to exit the program with a specific status code."""

    __slots__ = ("exit_code",)

    def __init__(self, code: int = 0) -> None:
        self.exit_code = code


def _with_suggestions(message: str, possibilities: t.Iterable[str] | None) -> str:
    if not possibilities:
        return message
    options = sorted(possibilities)
    if len(options) == 1:
        suggest = f"Did you mean {options[0]!r}?"
    else:
        joined = ", ".join(repr(o) for o in options)
        suggest = f"(Did you mean one of: {joined}?)"
    return f"{message} {suggest}"


def _help_hint_name(names: t.Sequence[str]) -> str:
    if "--help" in names:
        return "--help"
    for name in names:
        if name.startswith("--"):
            return name
    return names[0] if names else "--help"


def _stderr() -> t.IO[t.Any]:
    from ._streams import get_text_stderr

    return get_text_stderr()


def get_text_stderr() -> t.IO[t.Any]:
    from ._streams import get_text_stderr as _impl

    return _impl()


def resolve_color_default(color: bool | None = None) -> bool | None:
    from .globals import resolve_color_default as _impl

    return _impl(color)
