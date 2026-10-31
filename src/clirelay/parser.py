"""Public ``parser`` module.

The real parsing engine is private (``_parsing``).  This module exists for the
public import path and for the deprecated attributes that still resolve here.
"""
from __future__ import annotations

import typing as t
import warnings

from ._sentinel import FLAG_NEEDS_VALUE, UNSET
from .exceptions import BadArgumentUsage, BadOptionUsage, NoSuchOption, UsageError

V = t.TypeVar("V")

__all__ = [
    "BadArgumentUsage",
    "BadOptionUsage",
    "NoSuchOption",
    "UsageError",
    "FLAG_NEEDS_VALUE",
    "UNSET",
    "split_arg_string",
]

_OPTPARSE = (
    " is deprecated and will be removed in Click 9.0. The old parser is "
    "available in 'optparse'."
)


def __getattr__(name: str) -> t.Any:
    if name == "split_arg_string":
        warnings.warn(
            "Importing 'parser.split_arg_string' is deprecated, it will only be "
            "available in 'shell_completion' in Click 9.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        from .shell_completion import split_arg_string

        return split_arg_string

    mapping = {
        "Argument": ("_Argument", "parser.Argument"),
        "Option": ("_Option", "parser.Option"),
        "OptionParser": ("_Parser", "parser.OptionParser"),
        "ParsingState": ("_State", "parser.ParsingState"),
        "normalize_opt": ("normalize_opt", "parser.normalize_opt"),
        "split_opt": ("split_opt", "parser.split_opt"),
    }
    if name in mapping:
        attr, label = mapping[name]
        warnings.warn(f"'{label}'{_OPTPARSE}", DeprecationWarning, stacklevel=2)
        from . import _parsing

        return getattr(_parsing, attr)

    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
