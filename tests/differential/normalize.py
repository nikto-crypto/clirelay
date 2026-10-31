"""The one and only normalizer applied before comparing clirelay to the oracle.

Exactly three transformations are permitted by the build contract:

1. the dotted module prefix ``clirelay.`` is treated as ``click.``;
2. memory addresses (``0x`` + hex) are masked;
3. warning file names and line numbers are dropped.

No other text is altered.  Keeping this in one small, tested function makes the
contract auditable.
"""
from __future__ import annotations

import re

_ADDR = re.compile(r"0x[0-9a-fA-F]+")


def normalize(text: str) -> str:
    """Normalize *clirelay* output so it can be compared to the oracle's."""
    if not isinstance(text, str):
        return text
    # 1. module prefix: our package name maps onto the oracle's.
    text = text.replace("clirelay.", "click.")
    # 2. mask memory addresses.
    text = _ADDR.sub("0xMEM", text)
    return text


def normalize_warning(message: str) -> str:
    """Normalize a warning message (prefix + addresses; locations are dropped
    separately by capturing only the message text)."""
    return normalize(message)
