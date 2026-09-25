"""Watermark value object for the record stream."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class Watermark:
    """How far the stream has been written and how far it is readable."""

    committed_seq: int = 0
    durable_seq: int = 0
    tick: int = 0
    snapshot_seq: int = 0

    def lag(self) -> int:
        """Return how many durable records are not committed yet."""

        return max(0, self.durable_seq - self.committed_seq)

    def describe(self) -> dict[str, Any]:
        return {
            "committed_seq": self.committed_seq,
            "durable_seq": self.durable_seq,
            "snapshot_seq": self.snapshot_seq,
            "tick": self.tick,
            "uncommitted_lag": self.lag(),
        }


def commit_allowed(target: int, durable_seq: int) -> bool:
    """A record can only be committed once it is durable."""

    return 0 <= target <= durable_seq


def advance_watermark(current: int, target: int) -> int:
    """Return the larger of the two values so watermarks never move back."""

    return target if target > current else current
