"""Ramp planning for the heater."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..config import Limits
from ..errors import OverLimitError, ValidationError


@dataclass(frozen=True, slots=True)
class RampPlan:
    """A target wall temperature plus the tolerance band."""

    target_c: float
    band_c: float

    def describe(self) -> dict[str, Any]:
        return {"target_c": self.target_c, "band_c": self.band_c}


def plan_ramp(target_c: float, limits: Limits, *, band_c: float = 1.5) -> RampPlan:
    """Validate a ramp target against the wall temperature bound."""

    if target_c <= 0:
        raise ValidationError("ramp target must be positive", target_c=target_c)
    if band_c <= 0:
        raise ValidationError("ramp band must be positive", band_c=band_c)
    if target_c > limits.wall_temp_max_c:
        raise OverLimitError(
            "ramp target is above the wall temperature bound",
            target_c=target_c,
            limit=limits.wall_temp_max_c,
        )
    return RampPlan(target_c=target_c, band_c=band_c)


def wall_temperature(target_c: float, *, efficiency: float = 0.92) -> float:
    """Model the wall temperature the ramp settles on."""

    if not 0.0 < efficiency <= 1.0:
        raise ValidationError("efficiency must sit between zero and one", efficiency=efficiency)
    return round(target_c * efficiency, 2)
