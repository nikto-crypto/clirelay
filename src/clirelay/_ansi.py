"""ANSI styling primitives: building SGR escape sequences and removing them."""
from __future__ import annotations

import re
import typing as t

# Offsets from the base foreground code (30).  Background codes add ten.
_COLOR_OFFSETS = {
    "black": 0,
    "red": 1,
    "green": 2,
    "yellow": 3,
    "blue": 4,
    "magenta": 5,
    "cyan": 6,
    "white": 7,
    "reset": 9,
    "bright_black": 60,
    "bright_red": 61,
    "bright_green": 62,
    "bright_yellow": 63,
    "bright_magenta": 65,
    "bright_cyan": 66,
    "bright_white": 67,
    "bright_blue": 64,
}

_RESET_ALL = "\x1b[0m"

# ``(on, off)`` SGR parameters for each toggle-able attribute, in the order they
# are emitted.
_ATTRS: tuple[tuple[str, int, int], ...] = (
    ("bold", 1, 22),
    ("dim", 2, 22),
    ("underline", 4, 24),
    ("overline", 53, 55),
    ("italic", 3, 23),
    ("blink", 5, 25),
    ("reverse", 7, 27),
    ("strikethrough", 9, 29),
)

_CSI_RE = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _color_params(value: t.Any, base: int) -> str:
    """Return the SGR parameter string for a color *value*.

    *base* is 30 for foreground or 40 for background.  Raises ``ValueError`` for
    anything that is not a known name, a 0-255 integer, or an RGB triple.
    """
    if isinstance(value, str):
        try:
            return str(base + _COLOR_OFFSETS[value])
        except KeyError:
            raise ValueError(f"Unknown color {value!r}") from None
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= 255:
        return f"{base + 8};5;{value}"
    if (
        isinstance(value, (tuple, list))
        and len(value) == 3
        and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in value)
    ):
        r, g, b = value
        return f"{base + 8};2;{r};{g};{b}"
    raise ValueError(f"Unknown color {value!r}")


def style(
    text: t.Any,
    fg: t.Any = None,
    bg: t.Any = None,
    bold: bool | None = None,
    dim: bool | None = None,
    underline: bool | None = None,
    overline: bool | None = None,
    italic: bool | None = None,
    blink: bool | None = None,
    reverse: bool | None = None,
    strikethrough: bool | None = None,
    reset: bool = True,
) -> str:
    parts: list[str] = []
    if fg is not None:
        parts.append(f"\x1b[{_color_params(fg, 30)}m")
    if bg is not None:
        parts.append(f"\x1b[{_color_params(bg, 40)}m")
    flags = {
        "bold": bold,
        "dim": dim,
        "underline": underline,
        "overline": overline,
        "italic": italic,
        "blink": blink,
        "reverse": reverse,
        "strikethrough": strikethrough,
    }
    for name, on, off in _ATTRS:
        flag = flags[name]
        if flag is not None:
            parts.append(f"\x1b[{on if flag else off}m")
    parts.append(str(text))
    if reset:
        parts.append(_RESET_ALL)
    return "".join(parts)


def strip_ansi(value: str) -> str:
    return _CSI_RE.sub("", value)


def unstyle(text: str) -> str:
    return strip_ansi(text)
