"""Storage readings."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..decision.thresholds import ThresholdSet
from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class StorageReading:
    """One stored volume together with its pressure verdict."""

    volume_m3: float
    pressure_kpa: float
    tick: int
    ok: bool
    code: str
    limit: float | None

    def describe(self) -> dict[str, Any]:
        return {
            "volume_m3": self.volume_m3,
            "pressure_kpa": self.pressure_kpa,
            "tick": self.tick,
            "ok": self.ok,
            "code": self.code,
            "limit": self.limit,
        }


def storage_reading(
    thresholds: ThresholdSet,
    volume_m3: float,
    pressure_kpa: float,
    tick: int,
) -> StorageReading:
    """Check that a stored volume is positive and inside the pressure bound."""

    if volume_m3 <= 0:
        raise ValidationError("stored volume must be positive", volume_m3=volume_m3)
    verdict = thresholds.evaluate("storage_pressure", pressure_kpa)
    return StorageReading(
        volume_m3=volume_m3,
        pressure_kpa=pressure_kpa,
        tick=tick,
        ok=verdict.ok,
        code=verdict.code,
        limit=verdict.limit,
    )
