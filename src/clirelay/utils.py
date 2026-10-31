"""General-purpose helpers: printing, file names, the per-app config directory."""
from __future__ import annotations

import os
import sys
import typing as t

from ._ansi import strip_ansi
from ._streams import (
    WIN,
    _find_binary_writer,
    get_text_stderr,
    get_text_stdout,
    open_stream,
    should_strip_ansi,
)
from .globals import resolve_color_default

R = t.TypeVar("R")

_FS_ENCODING = sys.getfilesystemencoding() or "utf-8"


def make_str(value: t.Any) -> str:
    """Coerce *value* to text, decoding bytes with the filesystem encoding."""
    if isinstance(value, (bytes, bytearray)):
        try:
            return value.decode(_FS_ENCODING)
        except UnicodeError:
            return value.decode("utf-8", "replace")
    return str(value)


def echo(
    message: object = None,
    file: t.IO[t.Any] | None = None,
    nl: bool = True,
    err: bool = False,
    color: bool | None = None,
) -> None:
    """Print *message*, removing ANSI codes when the target is not a terminal."""
    if file is None:
        file = get_text_stderr() if err else get_text_stdout()

    if message is not None and not isinstance(message, (str, bytes, bytearray)):
        message = str(message)

    text: t.Any = message
    if nl:
        if text is None:
            text = ""
        if isinstance(text, (bytes, bytearray)):
            text = bytes(text) + b"\n"
        else:
            text = text + "\n"

    if not text:
        file.flush()
        return

    if isinstance(text, (bytes, bytearray)):
        binary_writer = _find_binary_writer(file)
        if binary_writer is not None:
            file.flush()
            binary_writer.write(bytes(text))
            binary_writer.flush()
            return
        text = bytes(text).decode(getattr(file, "encoding", None) or "utf-8", "replace")

    if text and should_strip_ansi(file, color):
        text = strip_ansi(text)

    file.write(text)
    file.flush()


def _posixify(name: str) -> str:
    return "-".join(name.split()).lower()


def get_app_dir(
    app_name: str, roaming: bool = True, force_posix: bool = False
) -> str:
    """Return a directory suitable for per-user application data."""
    if WIN:
        key = "APPDATA" if roaming else "LOCALAPPDATA"
        folder = os.environ.get(key)
        if folder is None:
            folder = os.path.expanduser("~")
        return os.path.join(folder, app_name)
    if force_posix:
        return os.path.join(os.path.expanduser(f"~/.{_posixify(app_name)}"))
    if sys.platform == "darwin":
        return os.path.join(
            os.path.expanduser("~/Library/Application Support"), app_name
        )
    return os.path.join(
        os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config")),
        _posixify(app_name),
    )


def format_filename(
    filename: str | bytes | os.PathLike[str] | os.PathLike[bytes],
    shorten: bool = False,
) -> str:
    """Format a file name for display, tolerating undecodable bytes."""
    if shorten:
        filename = os.path.basename(filename)

    if isinstance(filename, bytes):
        return filename.decode(_FS_ENCODING, "replace")

    text = os.fspath(filename)
    if isinstance(text, bytes):
        return text.decode(_FS_ENCODING, "replace")
    # Normalize any surrogate-escaped bytes to replacement characters.
    return text.encode(_FS_ENCODING, "replace").decode(_FS_ENCODING, "replace")


def open_file(
    filename: str | os.PathLike[str],
    mode: str = "r",
    encoding: str | None = None,
    errors: str | None = "strict",
    lazy: bool = False,
    atomic: bool = False,
) -> t.IO[t.Any]:
    """Open a file, understanding ``-`` as the matching standard stream."""
    from ._files import LazyFile, KeepOpenFile

    if lazy:
        return t.cast("t.IO[t.Any]", LazyFile(filename, mode, encoding, errors, atomic=atomic))

    f, should_close = open_stream(filename, mode, encoding, errors, atomic=atomic)
    if not should_close:
        f = t.cast("t.IO[t.Any]", KeepOpenFile(f))
    return f


__all__ = [
    "echo",
    "format_filename",
    "get_app_dir",
    "make_str",
    "open_file",
    "open_stream",
    "resolve_color_default",
    "should_strip_ansi",
    "strip_ansi",
    "WIN",
]
