"""Flare planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class FlarePlan:
    """Why the flare is being opened and for how long it may stay open."""

    reason: str
    max_ticks: int

    def describe(self) -> dict[str, Any]:
        return {"reason": self.reason, "max_ticks": self.max_ticks}


def plan_flare(reason: str, *, max_ticks: int = 24) -> FlarePlan:
    """Validate a flare request."""

    if not reason:
        raise ValidationError("flare needs a reason")
    if max_ticks < 1:
        raise ValidationError("flare duration must be positive", max_ticks=max_ticks)
    return FlarePlan(reason=reason, max_ticks=max_ticks)


def flare_payload(plan: FlarePlan, *, tick: int, open_state: bool) -> dict[str, Any]:
    """Build the record body for one flare move."""

    return {
        "active": open_state,
        "reason": plan.reason,
        "max_ticks": plan.max_ticks,
        "moved_tick": tick,
    }
