"""Read model for the mixer."""

from __future__ import annotations

from typing import Any, Mapping

from ..decision.thresholds import ThresholdSet


def compose_status(state: Mapping[str, Any], *, now: int, thresholds: ThresholdSet) -> dict[str, Any]:
    """Summarise the mixer from derived state."""

    stir = state.get("stir") if isinstance(state, Mapping) else None
    mixer = stir.get("mixer") if isinstance(stir, Mapping) else None
    mixed = stir.get("mix") if isinstance(stir, Mapping) else None
    persisted = stir.get("persisted") if isinstance(stir, Mapping) else None
    level = float(mixed.get("level", 0.0)) if isinstance(mixed, Mapping) else None
    return {
        "running": bool(mixer.get("active", False)) if isinstance(mixer, Mapping) else False,
        "target": mixer.get("target") if isinstance(mixer, Mapping) else None,
        "level": level,
        "level_verdict": None if level is None else thresholds.evaluate("mix_level", level).describe(),
        "persisted": bool(persisted.get("active", False)) if isinstance(persisted, Mapping) else False,
        "generation": int(persisted.get("generation", 0)) if isinstance(persisted, Mapping) else 0,
        "persisted_tick": persisted.get("persisted_tick") if isinstance(persisted, Mapping) else None,
        "now": now,
    }
