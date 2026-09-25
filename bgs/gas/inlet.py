"""Inlet gating for the storage vessel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..facts import DIGESTER_LATCHED, MEM_PRESSURISED, VENT_LATCHED


@dataclass(frozen=True, slots=True)
class InletPlan:
    """What the inlet needs before it may open."""

    requires: tuple[str, ...]
    blocked_by: tuple[str, ...]

    def describe(self) -> dict[str, Any]:
        return {"requires": list(self.requires), "blocked_by": list(self.blocked_by)}


def inlet_blockers(facts: Mapping[str, bool]) -> tuple[str, ...]:
    """Return every fact that currently keeps the inlet shut."""

    blockers: list[str] = []
    if not facts.get(MEM_PRESSURISED, False):
        blockers.append(MEM_PRESSURISED)
    for latch in (VENT_LATCHED, DIGESTER_LATCHED):
        if facts.get(latch, False):
            blockers.append(latch)
    return tuple(blockers)


def plan_inlet(facts: Mapping[str, bool]) -> InletPlan:
    """Describe the inlet decision."""

    return InletPlan(requires=(MEM_PRESSURISED,), blocked_by=inlet_blockers(facts))
