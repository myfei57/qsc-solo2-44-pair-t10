"""Methane analysis and its rolling window."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from ..decision.thresholds import ThresholdSet
from ..decision.window import SampleWindow
from ..store.records import Record

QUALITY_KIND = "mem.quality"
SAMPLE_KEY = "methane"


@dataclass(frozen=True, slots=True)
class AnalyzerSnapshot:
    """One methane reading plus the window it joined."""

    methane: float
    tick: int
    ok: bool
    code: str
    window_size: int
    window_full: bool
    window_mean: float | None

    def describe(self) -> dict[str, Any]:
        return {
            "methane": self.methane,
            "tick": self.tick,
            "ok": self.ok,
            "code": self.code,
            "window_size": self.window_size,
            "window_full": self.window_full,
            "window_mean": self.window_mean,
        }


def evaluate_methane(
    thresholds: ThresholdSet,
    window: SampleWindow,
    methane: float,
    tick: int,
) -> AnalyzerSnapshot:
    """Compare one reading and report the state of the window it joined."""

    window.add(tick, methane)
    verdict = thresholds.evaluate(SAMPLE_KEY, methane)
    return AnalyzerSnapshot(
        methane=methane,
        tick=tick,
        ok=verdict.ok,
        code=verdict.code,
        window_size=window.size(),
        window_full=window.is_full(),
        window_mean=window.mean(),
    )


def rebuild_window(
    records: Iterable[Record],
    *,
    span_ticks: int,
    capacity: int,
    kind: str = QUALITY_KIND,
    sample_key: str = SAMPLE_KEY,
) -> SampleWindow:
    """Rebuild the analysis window from the committed history."""

    window = SampleWindow(span_ticks, capacity)
    for record in records:
        if record.kind != kind:
            continue
        value = record.payload.get(sample_key)
        if value is None:
            continue
        window.add(record.tick, float(value))
    return window
