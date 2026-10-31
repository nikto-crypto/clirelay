"""The ambient context stack.

While a command runs, the active :class:`~clirelay.core.Context` is reachable
from anywhere through :func:`get_current_context`.  The stack is thread-local so
concurrent runners do not see each other's contexts.
"""
from __future__ import annotations

import typing as t
from threading import local

if t.TYPE_CHECKING:
    from .core import Context

_stack = local()


def _get_stack() -> list[Context]:
    try:
        return _stack.items
    except AttributeError:
        _stack.items = []
        return _stack.items


def get_current_context(silent: bool = False) -> Context | None:
    """Return the context for the command currently running.

    Outside of any command this raises ``RuntimeError`` unless *silent* is set,
    in which case ``None`` is returned.
    """
    stack = _get_stack()
    if stack:
        return stack[-1]
    if silent:
        return None
    raise RuntimeError("There is no active click context.")


def push_context(ctx: Context) -> None:
    """Make *ctx* the current context."""
    _get_stack().append(ctx)


def pop_context() -> None:
    """Remove the most recently pushed context."""
    _get_stack().pop()


def resolve_color_default(color: bool | None = None) -> bool | None:
    """Return *color* if given, otherwise the current context's preference."""
    if color is not None:
        return color
    ctx = get_current_context(silent=True)
    if ctx is not None:
        return ctx.color
    return None
