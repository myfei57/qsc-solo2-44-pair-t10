"""Pressure latch decision with hysteresis."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class PressureDecision:
    """What the vessel pressure implies for the over pressure latch."""

    kpa: float
    limit: float
    ok: bool
    code: str
    should_latch: bool
    should_clear: bool

    def describe(self) -> dict[str, Any]:
        return {
            "kpa": self.kpa,
            "limit": self.limit,
            "ok": self.ok,
            "code": self.code,
            "should_latch": self.should_latch,
            "should_clear": self.should_clear,
        }


def evaluate_pressure(
    kpa: float,
    *,
    limit: float,
    hysteresis: float,
    latched: bool,
) -> PressureDecision:
    """Decide whether the latch must be set or may be released."""

    if kpa < 0:
        raise ValidationError("vessel pressure must not be negative", kpa=kpa)
    if hysteresis < 0:
        raise ValidationError("hysteresis must not be negative", hysteresis=hysteresis)
    above = kpa > limit
    below_release = kpa <= limit - hysteresis
    return PressureDecision(
        kpa=kpa,
        limit=limit,
        ok=not above,
        code="above_max" if above else "ok",
        should_latch=above,
        should_clear=latched and below_release,
    )
