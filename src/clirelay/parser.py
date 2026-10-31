"""Public ``parser`` module.

The real parsing engine is private (``_parsing``).  This module exists for the
public import path and for the deprecated attributes that still resolve here.
"""
from __future__ import annotations

import typing as t
import warnings

from ._parsing import _Argument, _Option, _Parser, _State, normalize_opt, split_opt
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


def split_arg_string(string: str) -> list[str]:
    from .shell_completion import split_arg_string as _impl

    return _impl(string)


_DEPRECATED = {
    "Argument": (_Argument, "'parser.Argument' is deprecated and will be removed in Click 9.0. The old parser is available in 'optparse'."),
    "Option": (_Option, "'parser.Option' is deprecated and will be removed in Click 9.0. The old parser is available in 'optparse'."),
    "OptionParser": (_Parser, "'parser.OptionParser' is deprecated and will be removed in Click 9.0. The old parser is available in 'optparse'."),
    "ParsingState": (_State, "'parser.ParsingState' is deprecated and will be removed in Click 9.0. The old parser is available in 'optparse'."),
    "normalize_opt": (normalize_opt, "'parser.normalize_opt' is deprecated and will be removed in Click 9.0. The old parser is available in 'optparse'."),
    "split_opt": (split_opt, "'parser.split_opt' is deprecated and will be removed in Click 9.0. The old parser is available in 'optparse'."),
}


def __getattr__(name: str) -> t.Any:
    if name == "split_arg_string":
        warnings.warn(
            "Importing 'parser.split_arg_string' is deprecated, it will only be "
            "available in 'shell_completion' in Click 9.0.",
            DeprecationWarning,
            stacklevel=2,
        )
        return split_arg_string
    if name in _DEPRECATED:
        obj, message = _DEPRECATED[name]
        warnings.warn(message, DeprecationWarning, stacklevel=2)
        return obj
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
