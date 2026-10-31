"""Internal singleton markers.

These stand in for "no value was supplied" in places where ``None`` is itself a
legitimate value (a default of ``None``, a flag whose value is ``None``, and so
on).  They are an implementation detail and not part of the public contract.
"""
from __future__ import annotations

import enum


class Sentinel(enum.Enum):
    """Distinct marker singletons.

    ``UNSET`` means "the caller did not pass anything here".
    ``FLAG_NEEDS_VALUE`` marks an option flag that still expects a value to be
    collected (for example a prompt-on-demand option).
    """

    UNSET = "unset"
    FLAG_NEEDS_VALUE = "flag-needs-value"

    def __repr__(self) -> str:
        return f"Sentinel.{self.name}"

    def __bool__(self) -> bool:  # truthy, like any enum member
        return True


UNSET = Sentinel.UNSET
FLAG_NEEDS_VALUE = Sentinel.FLAG_NEEDS_VALUE
