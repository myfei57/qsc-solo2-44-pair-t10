"""Temperature zones inside the vessel."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..decision.thresholds import ThresholdSet
from ..errors import ValidationError

ZONES: tuple[str, ...] = ("upper", "middle", "lower")


@dataclass(frozen=True, slots=True)
class ZoneReading:
    """One zone temperature with its bound verdict."""

    zone: str
    temperature_c: float
    tick: int
    ok: bool
    code: str

    def describe(self) -> dict[str, Any]:
        return {
            "zone": self.zone,
            "temperature_c": self.temperature_c,
            "tick": self.tick,
            "ok": self.ok,
            "code": self.code,
        }


def validate_zone(zone: str) -> str:
    if zone not in ZONES:
        raise ValidationError("unknown temperature zone", zone=zone, known=list(ZONES))
    return zone


def zone_reading(thresholds: ThresholdSet, zone: str, temperature_c: float, tick: int) -> ZoneReading:
    """Compare a zone temperature with the wall bound."""

    verdict = thresholds.evaluate("wall_temp", temperature_c)
    return ZoneReading(
        zone=validate_zone(zone),
        temperature_c=temperature_c,
        tick=tick,
        ok=verdict.ok,
        code=verdict.code,
    )
