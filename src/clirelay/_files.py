"""Lazy and keep-open file wrappers used by the File parameter type."""
from __future__ import annotations

import os
import typing as t

from ._streams import open_stream
from .exceptions import FileError


class LazyFile:
    """A file that is not opened until it is first used."""

    def __init__(
        self,
        filename: str | os.PathLike[str],
        mode: str = "r",
        encoding: str | None = None,
        errors: str | None = "strict",
        atomic: bool = False,
    ) -> None:
        self.name: str = os.fspath(filename)
        self.mode = mode
        self.encoding = encoding
        self.errors = errors
        self.atomic = atomic
        self._f: t.IO[t.Any] | None
        self.should_close: bool

        if self.name == "-":
            self._f, self.should_close = open_stream(filename, mode, encoding, errors)
        else:
            if "r" in mode and "+" not in mode:
                # fail early if unreadable
                open(filename, mode).close()
            self._f = None
            self.should_close = True

    def __getattr__(self, name: str) -> t.Any:
        return getattr(self.open(), name)

    def __repr__(self) -> str:
        if self._f is not None:
            return repr(self._f)
        return f"<unopened file '{self.name}' {self.mode}>"

    def open(self) -> t.IO[t.Any]:
        if self._f is not None:
            return self._f
        try:
            rv, self.should_close = open_stream(
                self.name, self.mode, self.encoding, self.errors, atomic=self.atomic
            )
        except OSError as e:
            raise FileError(self.name, hint=e.strerror) from e
        self._f = rv
        return rv

    def close(self) -> None:
        if self._f is not None:
            self._f.close()

    def close_intelligently(self) -> None:
        if self.should_close:
            self.close()

    def __enter__(self) -> LazyFile:
        return self

    def __exit__(self, *args: t.Any) -> None:
        self.close_intelligently()

    def __iter__(self) -> t.Iterator[t.Any]:
        self.open()
        return iter(self._f)  # type: ignore[arg-type]


class KeepOpenFile:
    """Wrap a stream so leaving a ``with`` block does not close it."""

    def __init__(self, file: t.IO[t.Any]) -> None:
        self._file = file

    def __getattr__(self, name: str) -> t.Any:
        return getattr(self._file, name)

    def __enter__(self) -> KeepOpenFile:
        return self

    def __exit__(self, *args: t.Any) -> None:
        pass

    def __repr__(self) -> str:
        return repr(self._file)

    def __iter__(self) -> t.Iterator[t.Any]:
        return iter(self._file)
