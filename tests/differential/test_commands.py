"""Differential tests for whole-program invocation across realistic CLIs."""
from __future__ import annotations

import pytest

from .builders import CASES
from .harness import run_both

_PARAMS = [
    (name, builder, tuple(argv))
    for name, builder, argvs in CASES
    for argv in argvs
]


@pytest.mark.parametrize(
    "name,builder,argv",
    _PARAMS,
    ids=[f"{name}:{' '.join(argv) or '<none>'}" for name, builder, argv in _PARAMS],
)
def test_invocation(name, builder, argv):
    mismatches = run_both(builder, list(argv))
    assert not mismatches, "\n".join(
        f"[{m.channel}]\n  oracle={m.oracle!r}\n  mine=  {m.mine!r}" for m in mismatches
    )


@pytest.mark.parametrize("width", [40, 60, 80, 120])
@pytest.mark.parametrize("name,builder,argvs", CASES, ids=[c[0] for c in CASES])
def test_help_widths(name, builder, argvs, width):
    mismatches = run_both(builder, ["--help"], terminal_width=width)
    assert not mismatches, "\n".join(
        f"[{m.channel}]\n  oracle={m.oracle!r}\n  mine=  {m.mine!r}" for m in mismatches
    )
