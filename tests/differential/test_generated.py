"""Large deterministic fuzz: thousands of generated programs × argv variants.

Satisfies the build contract's requirement of at least 20,000 command
invocations compared against the oracle.  The generator is seeded, so failures
reproduce exactly.  Set ``CLIRELAY_FUZZ_SPECS`` to change how many specs are
generated (default 1800; each spec yields ~12 argv variants, exceeding 20k).
"""
from __future__ import annotations

import os
import random

import pytest

from . import generator
from ._oracle import oracle_available
from .harness import run_both

N_SPECS = int(os.environ.get("CLIRELAY_FUZZ_SPECS", "2600"))
SEED = int(os.environ.get("CLIRELAY_FUZZ_SEED", "20260101"))


def _build_plan() -> list[tuple[int, dict, list[str]]]:
    rng = random.Random(SEED)
    plan: list[tuple[int, dict, list[str]]] = []
    for i in range(N_SPECS):
        spec = generator.gen_spec(rng, i)
        for argv in generator.argvs_for(rng, spec):
            plan.append((i, spec, argv))
    return plan


_PLAN = _build_plan()


def test_case_count():
    assert len(_PLAN) >= 20000, f"only {len(_PLAN)} generated cases (<20000)"


@pytest.mark.skipif(not oracle_available()[0], reason=oracle_available()[1])
def test_generated_fuzz():
    failures: list[str] = []
    checked = 0
    for idx, spec, argv in _PLAN:
        spec_i = spec  # closure capture
        mismatches = run_both(lambda m, s=spec_i: generator.build_command(m, s), argv)
        checked += 1
        if mismatches:
            failures.append(
                f"spec#{idx} argv={argv}\n  spec={spec_i}\n  "
                + "\n  ".join(
                    f"[{m.channel}] oracle={m.oracle!r} mine={m.mine!r}"
                    for m in mismatches
                )
            )
            if len(failures) >= 25:
                break
    assert not failures, (
        f"{len(failures)} mismatches out of {checked} checked:\n"
        + "\n".join(failures[:25])
    )
