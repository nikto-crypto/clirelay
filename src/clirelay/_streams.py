"""Stream acquisition and the color-stripping decision.

This is the compatibility seam between clirelay and the actual file objects it
writes to.  It stays deliberately small: get the current stdout/stderr, decide
whether ANSI should be removed, and open files for the File parameter type.
"""
from __future__ import annotations

import io
import os
import sys
import typing as t

WIN = sys.platform.startswith("win")


def get_text_stdout() -> t.IO[t.Any]:
    return sys.stdout


def get_text_stderr() -> t.IO[t.Any]:
    return sys.stderr


def get_binary_stream(name: str) -> t.BinaryIO:
    stream = getattr(sys, name)
    buffer = getattr(stream, "buffer", None)
    if buffer is not None:
        return buffer
    return stream


def get_text_stream(name: str) -> t.IO[t.Any]:
    return getattr(sys, name)


def isatty(stream: t.IO[t.Any] | None) -> bool:
    if stream is None:
        return False
    try:
        return bool(stream.isatty())
    except Exception:
        return False


def should_strip_ansi(
    stream: t.IO[t.Any] | None = None, color: bool | None = None
) -> bool:
    if color is None:
        if stream is None:
            stream = sys.stdin
        return not isatty(stream)
    return not color


def _find_binary_writer(stream: t.IO[t.Any]) -> t.BinaryIO | None:
    # already a binary stream?
    if isinstance(stream, (io.RawIOBase, io.BufferedIOBase)):
        return t.cast("t.BinaryIO", stream)
    buffer = getattr(stream, "buffer", None)
    if buffer is not None and hasattr(buffer, "write"):
        return buffer
    return None


def open_stream(
    filename: str | os.PathLike[str],
    mode: str = "r",
    encoding: str | None = None,
    errors: str | None = "strict",
    atomic: bool = False,
) -> tuple[t.IO[t.Any], bool]:
    """Open *filename*, returning ``(file, should_close)``.

    The dash ``-`` maps to the matching standard stream, which must not be closed
    by the caller.  (Atomic writes are accepted but, for now, performed as an
    ordinary open; the public behaviour — the returned object — is unchanged.)
    """
    binary = "b" in mode
    filename = os.fspath(filename)

    if filename == "-":
        if any(m in mode for m in ("w", "a", "x")):
            stream: t.IO[t.Any] = (
                get_binary_stream("stdout") if binary else get_text_stream("stdout")
            )
        else:
            stream = (
                get_binary_stream("stdin") if binary else get_text_stream("stdin")
            )
        return stream, False

    if binary:
        return open(filename, mode), True
    return open(filename, mode, encoding=encoding, errors=errors, newline=None), True
