"""Text wrapping used by help rendering.

A paragraph's whitespace is collapsed and reflowed to a width.  A paragraph that
begins with a backspace marker (``\\b``) is preformatted: its line breaks are
preserved and the marker is dropped.
"""
from __future__ import annotations

import textwrap

from ._ansi import strip_ansi


def term_len(text: str) -> int:
    """Length of *text* as it appears on a terminal (ANSI codes do not count)."""
    return len(strip_ansi(text))


def _wrapper(
    width: int,
    initial_indent: str,
    subsequent_indent: str,
    replace_whitespace: bool = True,
) -> textwrap.TextWrapper:
    return textwrap.TextWrapper(
        width=max(width, 1),
        initial_indent=initial_indent,
        subsequent_indent=subsequent_indent,
        expand_tabs=False,
        replace_whitespace=replace_whitespace,
        break_long_words=True,
        break_on_hyphens=False,
        drop_whitespace=True,
    )


def wrap_text(
    text: str,
    width: int = 78,
    initial_indent: str = "",
    subsequent_indent: str = "",
    preserve_paragraphs: bool = False,
) -> str:
    text = text.expandtabs()

    if not preserve_paragraphs:
        return _wrapper(
            width, initial_indent, subsequent_indent, replace_whitespace=False
        ).fill(text)

    paragraphs: list[tuple[bool, str]] = []
    buffer: list[str] = []

    def flush() -> None:
        if not buffer:
            return
        if buffer[0].strip() == "\b":
            paragraphs.append((True, "\n".join(buffer[1:])))
        else:
            paragraphs.append((False, " ".join(line.strip() for line in buffer)))
        buffer.clear()

    for line in text.splitlines():
        if not line.strip():
            flush()
        else:
            buffer.append(line)
    flush()

    rendered: list[str] = []
    for is_preformatted, content in paragraphs:
        if is_preformatted:
            lines = content.splitlines()
            if lines:
                block = [initial_indent + lines[0]]
                block.extend(subsequent_indent + ln for ln in lines[1:])
                rendered.append("\n".join(block))
            else:
                rendered.append(initial_indent)
        else:
            rendered.append(
                _wrapper(width, initial_indent, subsequent_indent).fill(content)
            )

    return "\n\n".join(rendered)
