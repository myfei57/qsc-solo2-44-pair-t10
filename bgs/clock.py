"""Tick source for control decisions.

Nothing in the runtime reads the wall clock.  A tick only moves when a caller
asks for it, so the same command sequence always produces the same decisions
and the same persisted records.
"""

from __future__ import annotations

from typing import Protocol


class Clock(Protocol):
    """Minimal tick source used by every service."""

    def now(self) -> int:
        """Return the current tick."""

    def advance(self, ticks: int = 1) -> int:
        """Move the tick forward and return the new value."""


class ManualClock:
    """A clock that moves only when it is told to."""

    __slots__ = ("_tick",)

    def __init__(self, start: int = 0) -> None:
        if start < 0:
            raise ValueError("start tick must not be negative")
        self._tick = start

    def now(self) -> int:
        return self._tick

    def advance(self, ticks: int = 1) -> int:
        if ticks < 0:
            raise ValueError("cannot move the tick backwards")
        self._tick += ticks
        return self._tick
