"""Outlet quality measurement."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..decision.thresholds import ThresholdSet


@dataclass(frozen=True, slots=True)
class OutletReading:
    """One sulphur reading with its bound verdict."""

    sulfur_ppm: float
    tick: int
    ok: bool
    code: str
    limit: float | None

    def describe(self) -> dict[str, Any]:
        return {
            "sulfur_ppm": self.sulfur_ppm,
            "tick": self.tick,
            "ok": self.ok,
            "code": self.code,
            "limit": self.limit,
        }


def evaluate_outlet(thresholds: ThresholdSet, sulfur_ppm: float, tick: int) -> OutletReading:
    """Compare the outlet sulphur content with its ceiling."""

    verdict = thresholds.evaluate("sulfur", sulfur_ppm)
    return OutletReading(
        sulfur_ppm=sulfur_ppm,
        tick=tick,
        ok=verdict.ok,
        code=verdict.code,
        limit=verdict.limit,
    )
