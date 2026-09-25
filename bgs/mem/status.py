"""Read model for the membrane stage."""

from __future__ import annotations

from typing import Any, Mapping


def compose_status(state: Mapping[str, Any], *, machine_phase: str, analyzer: Mapping[str, Any] | None) -> dict[str, Any]:
    """Summarise the valve, the ramp and the newest analysis."""

    mem = state.get("mem") if isinstance(state, Mapping) else None
    valve = mem.get("valve") if isinstance(mem, Mapping) else None
    ramp = mem.get("ramp") if isinstance(mem, Mapping) else None
    quality = mem.get("quality") if isinstance(mem, Mapping) else None
    return {
        "phase": machine_phase,
        "valve_open": bool(valve.get("open", False)) if isinstance(valve, Mapping) else False,
        "pressure_kpa": ramp.get("pressure_kpa") if isinstance(ramp, Mapping) else None,
        "ramping": bool(ramp.get("active", False)) if isinstance(ramp, Mapping) else False,
        "methane": quality.get("methane") if isinstance(quality, Mapping) else None,
        "quality_ok": bool(quality.get("ok", False)) if isinstance(quality, Mapping) else False,
        "analyzer": dict(analyzer) if analyzer else None,
    }
