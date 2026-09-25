"""Bound comparisons used by the control decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..errors import BelowLimitError, OverLimitError, ValidationError


@dataclass(frozen=True, slots=True)
class ThresholdVerdict:
    """Result of comparing one value with one bound set."""

    name: str
    value: float
    ok: bool
    code: str
    limit: float | None

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "ok": self.ok,
            "code": self.code,
            "limit": self.limit,
        }


@dataclass(frozen=True, slots=True)
class Threshold:
    """A named lower and upper bound."""

    name: str
    unit: str
    minimum: float | None = None
    maximum: float | None = None

    def __post_init__(self) -> None:
        if self.minimum is None and self.maximum is None:
            raise ValidationError("threshold needs at least one bound", name=self.name)
        if self.minimum is not None and self.maximum is not None and self.minimum > self.maximum:
            raise ValidationError("threshold minimum exceeds maximum", name=self.name)

    def evaluate(self, value: float) -> ThresholdVerdict:
        """Compare ``value`` against the bounds."""

        if self.maximum is not None and value > self.maximum:
            return ThresholdVerdict(self.name, value, False, "above_max", self.maximum)
        if self.minimum is not None and value < self.minimum:
            return ThresholdVerdict(self.name, value, False, "below_min", self.minimum)
        return ThresholdVerdict(self.name, value, True, "ok", None)

    def describe(self) -> dict[str, Any]:
        return {"name": self.name, "unit": self.unit, "minimum": self.minimum, "maximum": self.maximum}


class ThresholdSet:
    """A lookup of thresholds by name."""

    __slots__ = ("_thresholds",)

    def __init__(self, thresholds: Mapping[str, Threshold] | None = None) -> None:
        self._thresholds: dict[str, Threshold] = dict(thresholds or {})

    @classmethod
    def from_limits(cls, limits: Any) -> "ThresholdSet":
        """Build the bound set the line runs with."""

        return cls(
            {
                "methane": Threshold("methane", "%", minimum=limits.methane_min_percent),
                "sulfur": Threshold("sulfur", "ppm", maximum=limits.sulfur_max_ppm),
                "vessel_pressure": Threshold("vessel_pressure", "kPa", maximum=limits.vessel_pressure_max_kpa),
                "membrane_pressure": Threshold(
                    "membrane_pressure", "kPa", maximum=limits.membrane_pressure_max_kpa
                ),
                "storage_pressure": Threshold("storage_pressure", "kPa", maximum=limits.storage_pressure_max_kpa),
                "wall_temp": Threshold("wall_temp", "C", maximum=limits.wall_temp_max_c),
                "mix_level": Threshold("mix_level", "ratio", minimum=limits.mix_level_min),
            }
        )

    def add(self, threshold: Threshold) -> None:
        self._thresholds[threshold.name] = threshold

    def get(self, name: str) -> Threshold:
        threshold = self._thresholds.get(name)
        if threshold is None:
            raise ValidationError("unknown threshold", name=name)
        return threshold

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._thresholds))

    def evaluate(self, name: str, value: float) -> ThresholdVerdict:
        return self.get(name).evaluate(value)

    def require(self, name: str, value: float) -> ThresholdVerdict:
        """Raise when ``value`` is outside the named bounds."""

        verdict = self.evaluate(name, value)
        if verdict.ok:
            return verdict
        if verdict.code == "above_max":
            raise OverLimitError(
                f"{name} is above its upper bound",
                name=name,
                value=value,
                limit=verdict.limit,
            )
        raise BelowLimitError(
            f"{name} is below its lower bound",
            name=name,
            value=value,
            limit=verdict.limit,
        )

    def describe(self) -> dict[str, Any]:
        return {name: self._thresholds[name].describe() for name in self.names()}
