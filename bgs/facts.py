"""Fact names and derivation used by gates and interlocks.

Services write facts into the record stream; the gate layer only ever reads
them from the derived state.  Keeping the translation in one place means a
restart rebuilds exactly the same facts as a live process.
"""

from __future__ import annotations

from typing import Any, Mapping

STIR_RUNNING = "stir.running"
STIR_PERSISTED = "stir.persisted"
HEAT_RUNNING = "heat.running"
FEED_OPEN = "feed.open"
DESUL_VERIFIED = "desul.verified"
COMPRESS_RUNNING = "compress.running"
MEM_VALVE_OPEN = "mem.valve_open"
MEM_PRESSURISED = "mem.pressurised"
GAS_INLET_OPEN = "gas.inlet_open"
VENT_LATCHED = "vent.latched"
VENT_FLARING = "vent.flaring"
DIGESTER_LATCHED = "digester.latched"
FEED_BATCH_DECLARED = "feed.batch_declared"

def _flag(state: Mapping[str, Any], path: str, key: str = "active") -> bool:
    group, _, leaf = path.partition(".")
    node = state.get(group)
    if not isinstance(node, Mapping):
        return False
    entry = node.get(leaf)
    if not isinstance(entry, Mapping):
        return False
    return bool(entry.get(key, False))


def derive_facts(state: Mapping[str, Any]) -> dict[str, bool]:
    """Translate derived state into the boolean facts gates evaluate."""

    return {
        STIR_RUNNING: _flag(state, "stir.mixer"),
        STIR_PERSISTED: _flag(state, "stir.persisted"),
        HEAT_RUNNING: _flag(state, "heat.ramp"),
        FEED_OPEN: _flag(state, "feed.open"),
        DESUL_VERIFIED: _flag(state, "desul.verified"),
        COMPRESS_RUNNING: _flag(state, "compress.running"),
        MEM_VALVE_OPEN: _flag(state, "mem.valve"),
        MEM_PRESSURISED: _flag(state, "mem.ramp"),
        GAS_INLET_OPEN: _flag(state, "gas.inlet"),
        VENT_LATCHED: latch_state(state, "vent"),
        VENT_FLARING: _flag(state, "vent.flare"),
        DIGESTER_LATCHED: latch_state(state, "digester"),
    }


def latch_state(state: Mapping[str, Any], group: str) -> bool:
    """Return whether ``group`` is currently latched.

    A latch is set when its set record is newer than its clear record, which
    keeps the answer correct after a restart without any side channel.
    """

    node = state.get(group)
    if not isinstance(node, Mapping):
        return False
    latch = node.get("latch")
    cleared = node.get("clear")
    latch_step = latch.get("step") if isinstance(latch, Mapping) else None
    clear_step = cleared.get("step") if isinstance(cleared, Mapping) else None
    if latch_step is None:
        return False
    if clear_step is None:
        return True
    return int(clear_step) < int(latch_step)
