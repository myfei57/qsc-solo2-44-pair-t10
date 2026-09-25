"""Product gas valve state."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ValveState:
    """Open or closed, with the tick it moved."""

    open: bool
    tick: int
    reason: str

    def describe(self) -> dict[str, Any]:
        return {"open": self.open, "tick": self.tick, "reason": self.reason}


def valve_payload(state: ValveState, *, generation: int = 0) -> dict[str, Any]:
    """Build the record body for one valve move."""

    return {
        "active": state.open,
        "open": state.open,
        "moved_tick": state.tick,
        "reason": state.reason,
        "generation": generation,
    }
