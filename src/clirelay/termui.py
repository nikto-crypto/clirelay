"""Terminal interaction: styling, prompts, confirmation, and screen helpers."""
from __future__ import annotations

import typing as t

from ._ansi import strip_ansi, style, unstyle
from .exceptions import Abort, UsageError
from .globals import resolve_color_default
from .types import Choice, ParamType, convert_type
from .utils import echo

if t.TYPE_CHECKING:
    from .core import Context

_building_text = None


def secho(
    message: t.Any | None = None,
    file: t.IO[t.Any] | None = None,
    nl: bool = True,
    err: bool = False,
    color: bool | None = None,
    **styles: t.Any,
) -> None:
    if message is not None and not isinstance(message, (bytes, bytearray)):
        message = style(message, **styles)
    echo(message, file=file, nl=nl, err=err, color=color)


def isatty(stream: t.IO[t.Any]) -> bool:
    try:
        return bool(stream.isatty())
    except Exception:
        return False


def _build_prompt(
    text: str,
    suffix: str,
    show_default: bool = False,
    default: t.Any = None,
    show_choices: bool = True,
    type: ParamType | None = None,
) -> str:
    prompt = text
    if type is not None and show_choices and isinstance(type, Choice):
        prompt = f"{prompt} ({', '.join(map(str, type._display_choices()))})"
    if isinstance(show_default, str):
        prompt = f"{prompt} [({show_default})]"
    elif default is not None and show_default:
        prompt = f"{prompt} [{_format_default(default)}]"
    return f"{prompt}{suffix}"


def _format_default(default: t.Any) -> t.Any:
    if isinstance(default, (list, tuple)):
        return ", ".join(str(d) for d in default)
    return default


def prompt(
    text: str,
    default: t.Any = None,
    hide_input: bool = False,
    confirmation_prompt: bool | str = False,
    type: t.Any = None,
    value_proc: t.Callable[[str], t.Any] | None = None,
    prompt_suffix: str = ": ",
    show_default: bool = True,
    err: bool = False,
    show_choices: bool = True,
) -> t.Any:
    def prompt_func(text: str) -> str:
        try:
            echo(text, nl=False, err=err)
            _flush_if_interactive(err)
            return _read_input(hide_input, err)
        except (KeyboardInterrupt, EOFError):
            if hide_input:
                echo(None, err=err)
            raise Abort() from None

    if value_proc is None:
        param_type = convert_type(type, default)
        value_proc = lambda x: param_type(x, None, None)  # noqa: E731

    prompt_str = _build_prompt(
        text,
        prompt_suffix,
        show_default,
        default,
        show_choices,
        convert_type(type, default) if type is not None or default is not None else None,
    )

    if confirmation_prompt:
        if confirmation_prompt is True:
            confirmation_prompt = "Repeat for confirmation"
        confirm_str = _build_prompt(confirmation_prompt, prompt_suffix)

    while True:
        value = _prompt_once(prompt_str, prompt_func, default, value_proc, err, hide_input)
        if not confirmation_prompt:
            return value
        while True:
            value2 = _prompt_once(confirm_str, prompt_func, None, value_proc, err, hide_input)
            if value2 is not None:
                break
        if value == value2:
            return value
        echo("Error: The two entered values do not match.", err=err)


def _prompt_once(
    prompt_str: str,
    prompt_func: t.Callable[[str], str],
    default: t.Any,
    value_proc: t.Callable[[str], t.Any],
    err: bool,
    hide_input: bool = False,
) -> t.Any:
    def report(message: str, value: str) -> None:
        if hide_input:
            message = message.replace(repr(value), "'***'")
        echo(f"Error: {message}", err=err)

    while True:
        value = prompt_func(prompt_str)
        if value:
            try:
                return value_proc(value)
            except UsageError as e:
                report(e.message, value)
                continue
        elif default is not None:
            try:
                return value_proc(default) if isinstance(default, str) else default
            except UsageError as e:
                report(e.message, value)
                continue
        else:
            return default


def _flush_if_interactive(err: bool) -> None:
    import sys

    stream = sys.stderr if err else sys.stdout
    try:
        if stream.isatty():
            stream.flush()
    except Exception:
        pass


def _read_input(hide_input: bool, err: bool) -> str:
    import sys

    line = sys.stdin.readline()
    if not line:
        raise EOFError()
    value = line.rstrip("\n").rstrip("\r")
    if hide_input:
        # the value is not echoed; only the line break is shown
        echo("", err=err)
    else:
        echo(value, err=err)
    return value


def confirm(
    text: str,
    default: bool | None = False,
    abort: bool = False,
    prompt_suffix: str = ": ",
    show_default: bool = True,
    err: bool = False,
) -> bool:
    prompt_str = _build_confirm_prompt(text, default, prompt_suffix, show_default)
    while True:
        try:
            echo(prompt_str, nl=False, err=err)
            _flush_if_interactive(err)
            value = _read_input(False, err).lower().strip()
        except (KeyboardInterrupt, EOFError):
            raise Abort() from None
        if value in ("y", "yes"):
            rv = True
        elif value in ("n", "no"):
            rv = False
        elif default is not None and value == "":
            rv = default
        else:
            echo("Error: invalid input", err=err)
            continue
        break
    if abort and not rv:
        raise Abort()
    return rv


def _build_confirm_prompt(
    text: str, default: bool | None, suffix: str, show_default: bool
) -> str:
    if default is None:
        choices = "[y/n]"
    elif default:
        choices = "[Y/n]"
    else:
        choices = "[y/N]"
    if show_default:
        return f"{text} {choices}{suffix}"
    return f"{text}{suffix}"


def hidden_prompt_func(prompt: str) -> str:
    import getpass

    return getpass.getpass(prompt=prompt)


# -- terminal-only helpers (refined in a later phase) -----------------------

def echo_via_pager(
    text_or_generator: t.Any, color: bool | None = None
) -> None:
    from ._term import pager

    color = resolve_color_default(color)
    if callable(text_or_generator):
        gen: t.Iterable[str] = text_or_generator()
    elif isinstance(text_or_generator, str):
        gen = [text_or_generator]
    else:
        gen = text_or_generator
    pager((str(x) for x in gen), color)


def get_pager_file(color: bool | None = None) -> t.Any:
    from ._term import get_pager_file as _impl

    return _impl(color)


def progressbar(
    iterable: t.Iterable[t.Any] | None = None,
    length: int | None = None,
    label: str | None = None,
    hidden: bool = False,
    show_eta: bool = True,
    show_percent: bool | None = None,
    show_pos: bool = False,
    item_show_func: t.Callable[..., str | None] | None = None,
    fill_char: str = "#",
    empty_char: str = "-",
    bar_template: str = "%(label)s  [%(bar)s]  %(info)s",
    info_sep: str = "  ",
    width: int = 36,
    file: t.TextIO | None = None,
    color: bool | None = None,
    update_min_steps: int = 1,
) -> t.Any:
    from ._term import ProgressBar

    color = resolve_color_default(color)
    return ProgressBar(
        iterable=iterable,
        length=length,
        label=label,
        hidden=hidden,
        show_eta=show_eta,
        show_percent=show_percent,
        show_pos=show_pos,
        item_show_func=item_show_func,
        fill_char=fill_char,
        empty_char=empty_char,
        bar_template=bar_template,
        info_sep=info_sep,
        width=width,
        file=file,
        color=color,
        update_min_steps=update_min_steps,
    )


def getchar(echo: bool = False) -> str:
    from ._term import getchar as _impl

    return _impl(echo)


def raw_terminal() -> t.Any:
    from ._term import raw_terminal as _impl

    return _impl()


def pause(info: str | None = None, err: bool = False) -> None:
    from ._term import pause as _impl

    _impl(info, err)


def clear() -> None:
    import sys

    from ._streams import isatty as _isatty

    if not _isatty(sys.stdout):
        return
    echo("\x1b[2J\x1b[1;1H", nl=False)


def edit(
    text: str | bytes | bytearray | None = None,
    editor: str | None = None,
    env: t.Mapping[str, str] | None = None,
    require_save: bool = True,
    extension: str = ".txt",
    filename: t.Any = None,
) -> str | bytes | bytearray | None:
    from ._term import Editor

    ed = Editor(editor=editor, env=env, require_save=require_save, extension=extension)
    if filename is None:
        return ed.edit(text)
    ed.edit_files(filename if not isinstance(filename, (str, bytes)) else [filename])
    return None


def launch(url: str, wait: bool = False, locate: bool = False) -> int:
    from ._term import open_url

    return open_url(url, wait=wait, locate=locate)


__all__ = [
    "secho",
    "style",
    "unstyle",
    "strip_ansi",
    "echo",
    "prompt",
    "confirm",
    "echo_via_pager",
    "get_pager_file",
    "progressbar",
    "getchar",
    "raw_terminal",
    "pause",
    "clear",
    "edit",
    "launch",
    "convert_type",
    "Choice",
    "ParamType",
]
