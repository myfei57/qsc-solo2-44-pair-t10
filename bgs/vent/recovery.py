"""Recovery condition for the quality latch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..decision.window import SampleWindow


@dataclass(frozen=True, slots=True)
class RecoveryCheck:
    """Whether the quality window allows the latch to be released."""

    ready: bool
    reason: str
    window_size: int
    window_full: bool
    minimum: float | None
    floor: float

    def describe(self) -> dict[str, Any]:
        return {
            "ready": self.ready,
            "reason": self.reason,
            "window_size": self.window_size,
            "window_full": self.window_full,
            "minimum": self.minimum,
            "floor": self.floor,
        }


def recovery_ready(window: SampleWindow, *, floor: float) -> RecoveryCheck:
    """A latch may only be released once a full window sits above the floor."""

    minimum = window.minimum()
    full = window.is_full()
    if not full:
        return RecoveryCheck(False, "quality window is not full yet", window.size(), full, minimum, floor)
    if not window.all_at_least(floor):
        return RecoveryCheck(False, "quality window still holds a low reading", window.size(), full, minimum, floor)
    return RecoveryCheck(True, "quality window is above the floor", window.size(), full, minimum, floor)
