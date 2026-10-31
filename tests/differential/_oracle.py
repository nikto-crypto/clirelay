"""Load the Click 8.5.0 oracle as a black box and guard the environment.

The oracle is used only through its public API.  This module never inspects it.
It enforces that the running interpreter matches the one recorded with the oracle
and that the only importable ``click`` is the oracle itself.
"""
from __future__ import annotations

import importlib.util
import os
import sys
import typing as t

import pytest

ORACLE_DIR = os.environ.get(
    "CLIRELAY_ORACLE_DIR", os.path.expanduser("~/clirelay-oracle")
)
REQUIRE = os.environ.get("CLIRELAY_REQUIRE_ORACLE") == "1"


def _read_oracle_python() -> tuple[int, int, str] | None:
    path = os.path.join(ORACLE_DIR, "ORACLE_PYTHON.txt")
    try:
        with open(path) as fh:
            first = fh.readline().split()
    except OSError:
        return None
    if len(first) < 3:
        return None
    return int(first[0]), int(first[1]), first[2]


def _current_magic_hex() -> str:
    import binascii

    return binascii.hexlify(importlib.util.MAGIC_NUMBER).decode()


def _skip_or_fail(reason: str) -> t.NoReturn:
    if REQUIRE:
        pytest.fail(f"oracle required but unavailable: {reason}")
    pytest.skip(reason)


_oracle_cache: t.Any = None


def oracle_available() -> tuple[bool, str]:
    info = _read_oracle_python()
    if info is None:
        return False, f"oracle metadata not found under {ORACLE_DIR}"
    major, minor, magic = info
    if sys.version_info[:2] != (major, minor):
        return (
            False,
            f"interpreter {sys.version_info[0]}.{sys.version_info[1]} != oracle "
            f"{major}.{minor}",
        )
    if _current_magic_hex() != magic:
        return False, f"bytecode magic {_current_magic_hex()} != oracle {magic}"
    if not os.path.isdir(os.path.join(ORACLE_DIR, "click")):
        return False, f"oracle click package not found under {ORACLE_DIR}"
    return True, ""


def load_oracle() -> t.Any:
    """Import and return the oracle's ``click`` module, or skip/fail."""
    global _oracle_cache
    if _oracle_cache is not None:
        return _oracle_cache

    ok, reason = oracle_available()
    if not ok:
        _skip_or_fail(reason)

    if ORACLE_DIR not in sys.path:
        sys.path.insert(0, ORACLE_DIR)
    import click  # type: ignore

    # The only importable click must be the oracle.
    resolved = os.path.realpath(click.__file__)
    if os.path.realpath(ORACLE_DIR) not in resolved:
        _skip_or_fail(f"click.__file__ ({resolved}) is not under the oracle folder")

    _oracle_cache = click
    return click


def oracle_call(fn: t.Callable[[], t.Any]) -> tuple[t.Any, tuple[str, str] | None]:
    """Run *fn* against the oracle, recording errors only as (class, message).

    Never lets an oracle traceback escape.
    """
    try:
        return fn(), None
    except BaseException as exc:  # noqa: BLE001
        return None, (type(exc).__name__, str(exc))
