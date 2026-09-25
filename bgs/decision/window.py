"""Rolling sample windows used by quality and recovery decisions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ValidationError


@dataclass(frozen=True, slots=True)
class Sample:
    tick: int
    value: float

    def describe(self) -> dict[str, Any]:
        return {"tick": self.tick, "value": self.value}


class SampleWindow:
    """Keeps the newest samples that are still inside the tick span."""

    __slots__ = ("_span", "_capacity", "_samples")

    def __init__(self, span_ticks: int, capacity: int) -> None:
        if span_ticks < 1:
            raise ValidationError("window span must be positive", span_ticks=span_ticks)
        if capacity < 1:
            raise ValidationError("window capacity must be positive", capacity=capacity)
        self._span = span_ticks
        self._capacity = capacity
        self._samples: list[Sample] = []

    @property
    def span_ticks(self) -> int:
        return self._span

    @property
    def capacity(self) -> int:
        return self._capacity

    def add(self, tick: int, value: float) -> Sample:
        """Add a sample, keeping ticks monotonic and the capacity bounded."""

        if tick < 0:
            raise ValidationError("sample tick must not be negative", tick=tick)
        if self._samples and tick < self._samples[-1].tick:
            raise ValidationError(
                "samples must arrive in tick order",
                tick=tick,
                last_tick=self._samples[-1].tick,
            )
        sample = Sample(tick=tick, value=value)
        self._samples.append(sample)
        self.prune(tick)
        return sample

    def prune(self, now: int) -> int:
        """Drop samples older than the span and return how many were dropped."""

        keep_from = now - self._span
        before = len(self._samples)
        self._samples = [sample for sample in self._samples if sample.tick >= keep_from]
        if len(self._samples) > self._capacity:
            self._samples = self._samples[-self._capacity :]
        return before - len(self._samples)

    def samples(self) -> tuple[Sample, ...]:
        return tuple(self._samples)

    def values(self) -> tuple[float, ...]:
        return tuple(sample.value for sample in self._samples)

    def size(self) -> int:
        return len(self._samples)

    def is_full(self) -> bool:
        return len(self._samples) >= self._capacity

    def minimum(self) -> float | None:
        return min((sample.value for sample in self._samples), default=None)

    def maximum(self) -> float | None:
        return max((sample.value for sample in self._samples), default=None)

    def mean(self) -> float | None:
        if not self._samples:
            return None
        return sum(sample.value for sample in self._samples) / len(self._samples)

    def all_at_least(self, threshold: float) -> bool:
        """True when every retained sample is at or above ``threshold``."""

        return bool(self._samples) and all(sample.value >= threshold for sample in self._samples)

    def all_at_most(self, threshold: float) -> bool:
        """True when every retained sample is at or below ``threshold``."""

        return bool(self._samples) and all(sample.value <= threshold for sample in self._samples)

    def clear(self) -> None:
        self._samples.clear()

    def describe(self) -> dict[str, Any]:
        return {
            "span_ticks": self._span,
            "capacity": self._capacity,
            "size": self.size(),
            "minimum": self.minimum(),
            "maximum": self.maximum(),
            "mean": self.mean(),
        }
