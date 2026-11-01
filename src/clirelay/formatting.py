"""Help-text rendering: the :class:`HelpFormatter` and its building blocks."""
from __future__ import annotations

import typing as t
from contextlib import contextmanager

from ._wrap import term_len, wrap_dl_text, wrap_text

#: When set, overrides the detected terminal width everywhere.
FORCED_WIDTH: int | None = None


def _detect_columns() -> int:
    """Terminal width for help rendering.

    Uses :func:`shutil.get_terminal_size`, which honors the ``COLUMNS``
    environment variable first and otherwise queries the real terminal, falling
    back to 80 when neither is available (piped output, no terminal).  This
    matches the oracle, where ``COLUMNS`` drives the width in a real process.
    """
    import shutil

    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return 80


def measure_table(rows: t.Iterable[tuple[str, ...]]) -> tuple[int, ...]:
    widths: dict[int, int] = {}
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths.get(i, 0), term_len(cell))
    return tuple(y for x, y in sorted(widths.items()))


def iter_rows(
    rows: t.Iterable[tuple[str, ...]], col_count: int
) -> t.Iterator[tuple[str, ...]]:
    for row in rows:
        yield row + ("",) * (col_count - len(row))


def join_options(options: t.Sequence[str]) -> tuple[str, bool]:
    """Join option names for a help record.

    Returns the joined string and whether any option used a short (single-dash)
    prefix, which affects alignment.
    """
    rv = []
    any_prefix_is_slash = False
    for opt in options:
        prefix = _split_opt(opt)[0]
        if prefix == "/":
            any_prefix_is_slash = True
        rv.append((len(prefix), opt))
    rv.sort(key=lambda x: x[0])
    return ", ".join(x[1] for x in rv), any_prefix_is_slash


def _split_opt(opt: str) -> tuple[str, str]:
    first = opt[:1]
    if first.isalnum():
        return "", opt
    if opt[1:2] == first:
        return opt[:2], opt[2:]
    return first, opt[1:]


class HelpFormatter:
    """Builds help output: usage lines, definition lists, and wrapped text."""

    def __init__(
        self,
        indent_increment: int = 2,
        width: int | None = None,
        max_width: int | None = None,
    ) -> None:
        self.indent_increment = indent_increment
        if max_width is None:
            max_width = 80
        if width is None:
            width = FORCED_WIDTH
        if width is None:
            width = max(min(_detect_columns(), max_width) - 2, 50)
        self.width = width
        self.current_indent = 0
        self.buffer: list[str] = []

    def write(self, string: str) -> None:
        self.buffer.append(string)

    def indent(self) -> None:
        self.current_indent += self.indent_increment

    def dedent(self) -> None:
        self.current_indent -= self.indent_increment

    def write_usage(
        self, prog: str, args: str = "", prefix: str | None = None
    ) -> None:
        if prefix is None:
            prefix = "Usage: "
        usage_prefix = f"{' ' * self.current_indent}{prefix}{prog} "
        indent = " " * term_len(usage_prefix)
        text = wrap_text(
            args,
            self.width,
            initial_indent=usage_prefix,
            subsequent_indent=indent,
        )
        self.write(f"{text}\n")

    def write_heading(self, heading: str) -> None:
        self.write(f"{'':>{self.current_indent}}{heading}:\n")

    def write_paragraph(self) -> None:
        if self.buffer:
            self.write("\n")

    def write_text(self, text: str) -> None:
        indent = " " * self.current_indent
        self.write(
            wrap_text(
                text,
                self.width,
                initial_indent=indent,
                subsequent_indent=indent,
                preserve_paragraphs=True,
            )
        )
        self.write("\n")

    def write_dl(
        self,
        rows: t.Iterable[tuple[str, str]],
        col_max: int = 30,
        col_spacing: int = 2,
    ) -> None:
        rows = list(rows)
        widths = measure_table(rows)
        if len(widths) != 2:
            raise TypeError("Expected two columns for definition list")

        first_col = min(widths[0], col_max) + col_spacing

        for first, second in iter_rows(rows, len(widths)):
            self.write(f"{'':>{self.current_indent}}{first}")
            if not second:
                self.write("\n")
                continue
            if term_len(first) <= first_col - col_spacing:
                self.write(" " * (first_col - term_len(first)))
            else:
                self.write("\n")
                self.write(" " * (first_col + self.current_indent))

            text_width = max(self.width - first_col - 2, 10)
            wrapped = wrap_dl_text(second, text_width)
            lines = wrapped.splitlines()
            if lines:
                self.write(f"{lines[0]}\n")
                for line in lines[1:]:
                    self.write(f"{'':>{first_col + self.current_indent}}{line}\n")
            else:
                self.write("\n")

    @contextmanager
    def section(self, name: str) -> t.Iterator[None]:
        self.write_paragraph()
        self.write_heading(name)
        self.indent()
        try:
            yield
        finally:
            self.dedent()

    @contextmanager
    def indentation(self) -> t.Iterator[None]:
        self.indent()
        try:
            yield
        finally:
            self.dedent()

    def getvalue(self) -> str:
        return "".join(self.buffer)
