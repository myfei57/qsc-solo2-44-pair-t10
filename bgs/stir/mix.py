"""Homogenisation readings for the mixer."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..decision.thresholds import ThresholdSet
from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class MixReading:
    """One homogenisation level together with its bound verdict."""

    level: float
    tick: int
    ok: bool
    code: str

    def describe(self) -> dict[str, Any]:
        return {"level": self.level, "tick": self.tick, "ok": self.ok, "code": self.code}


def normalize_level(level: float) -> float:
    """Check that ``level`` is a usable fraction and round it deterministically."""

    if level != level:  # NaN never equals itself
        raise ValidationError("mix level must be a number", level=str(level))
    if level < 0.0 or level > 1.0:
        raise ValidationError("mix level must sit between zero and one", level=level)
    return round(level, 4)


def level_reading(thresholds: ThresholdSet, level: float, tick: int) -> MixReading:
    """Compare a homogenisation level with the configured floor."""

    verdict = thresholds.evaluate("mix_level", level)
    return MixReading(level=level, tick=tick, ok=verdict.ok, code=verdict.code)
