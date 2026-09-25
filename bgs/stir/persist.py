"""The durable hand off from mixing to feeding."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class PersistOutcome:
    """What was written when the mixer state was made durable."""

    generation: int
    mix_level: float
    tick: int
    seq: int = 0

    def describe(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "mix_level": self.mix_level,
            "tick": self.tick,
            "seq": self.seq,
        }


def build_payload(mix_level: float, generation: int, tick: int) -> dict[str, Any]:
    """Build the record body that feeding reads back."""

    return {
        "active": True,
        "mix_level": mix_level,
        "generation": generation,
        "persisted_tick": tick,
        "durable": True,
    }
