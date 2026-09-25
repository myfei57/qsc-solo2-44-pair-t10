"""Calibration baselines such as vessel pressure, mix ratio and recovery rate."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ArtifactExpiredError, NotFoundError, StaleGenerationError, ValidationError
from .expiry import Validity


@dataclass(frozen=True, slots=True)
class Baseline:
    """One calibrated value with its generation and validity window."""

    name: str
    value: float
    unit: str
    generation: int
    validity: Validity

    @property
    def issued_tick(self) -> int:
        return self.validity.issued_tick

    def is_expired(self, now: int) -> bool:
        return self.validity.is_expired(now)

    def describe(self, now: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "generation": self.generation,
            "issued_tick": self.issued_tick,
            "valid_until": self.validity.valid_until(),
        }
        if now is not None:
            payload["expired"] = self.is_expired(now)
        return payload


class BaselineRegistry:
    """Latest calibration plus its history, per name."""

    __slots__ = ("_current", "_history")

    def __init__(self) -> None:
        self._current: dict[str, Baseline] = {}
        self._history: dict[str, list[Baseline]] = {}

    def publish(self, baseline: Baseline) -> None:
        if baseline.generation < 1:
            raise StaleGenerationError(
                "baseline must name a generation that was already issued",
                name=baseline.name,
                generation=baseline.generation,
            )
        current = self._current.get(baseline.name)
        if current is not None and baseline.generation < current.generation:
            raise StaleGenerationError(
                "baseline generation went backwards",
                name=baseline.name,
                published=baseline.generation,
                current=current.generation,
            )
        self._current[baseline.name] = baseline
        self._history.setdefault(baseline.name, []).append(baseline)

    def current(self, name: str) -> Baseline | None:
        return self._current.get(name)

    def history(self, name: str) -> tuple[Baseline, ...]:
        return tuple(self._history.get(name, ()))

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._current))

    def require(self, name: str, *, generation: int, now: int) -> Baseline:
        """Return the current baseline, or explain why it cannot be trusted."""

        baseline = self._current.get(name)
        if baseline is None:
            raise NotFoundError("no baseline was published", name=name)
        if baseline.is_expired(now):
            raise ArtifactExpiredError(
                "baseline expired",
                name=name,
                valid_until=baseline.validity.valid_until(),
                now=now,
            )
        if baseline.generation != generation:
            raise StaleGenerationError(
                "baseline does not match the calibration in force",
                name=name,
                baseline_generation=baseline.generation,
                required_generation=generation,
            )
        return baseline

    def deviation(self, name: str, measured: float) -> float:
        """Return how far ``measured`` sits from the current baseline."""

        baseline = self._current.get(name)
        if baseline is None:
            raise ValidationError("cannot compare against a missing baseline", name=name)
        return measured - baseline.value
