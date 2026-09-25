"""Read model for the compressor."""

from __future__ import annotations

from typing import Any, Mapping


def compose_status(state: Mapping[str, Any], *, machine_phase: str) -> dict[str, Any]:
    """Summarise the compressor from derived state."""

    compress = state.get("compress") if isinstance(state, Mapping) else None
    running = compress.get("running") if isinstance(compress, Mapping) else None
    gate = compress.get("gate") if isinstance(compress, Mapping) else None
    return {
        "running": bool(running.get("active", False)) if isinstance(running, Mapping) else False,
        "phase": machine_phase,
        "last_gate": gate.get("action") if isinstance(gate, Mapping) else None,
    }
