"""Read side of the stream: current state, historical state and the gap."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..facts import derive_facts
from ..store.records import Record
from ..store.replay import reduce_state, state_at_tick
from ..store.repository import RecordRepository


@dataclass(frozen=True, slots=True)
class StateDelta:
    """What changed between two points in time."""

    from_tick: int
    to_tick: int
    added: tuple[str, ...]
    changed: tuple[str, ...]
    removed: tuple[str, ...]

    @property
    def touched(self) -> tuple[str, ...]:
        return tuple(sorted({*self.added, *self.changed, *self.removed}))

    def describe(self) -> dict[str, Any]:
        return {
            "from_tick": self.from_tick,
            "to_tick": self.to_tick,
            "added": list(self.added),
            "changed": list(self.changed),
            "removed": list(self.removed),
        }


def _flatten(state: Mapping[str, Any]) -> dict[str, Any]:
    flat: dict[str, Any] = {}
    for group, leaves in state.items():
        if isinstance(leaves, Mapping):
            for leaf, payload in leaves.items():
                flat[f"{group}.{leaf}"] = payload
        else:
            flat[group] = leaves
    return flat


class StateView:
    """Answers "what is true now" and "what was true then"."""

    __slots__ = ("_repository",)

    def __init__(self, repository: RecordRepository) -> None:
        self._repository = repository

    def current(self) -> dict[str, Any]:
        """Return the state built from committed records."""

        return self._repository.state()

    def as_of(self, tick: int) -> dict[str, Any]:
        """Return the state as it stood at ``tick``."""

        return state_at_tick(self._repository.committed_records(), tick)

    def delta(self, tick: int) -> StateDelta:
        """Compare the state at ``tick`` with the state right now."""

        before = _flatten(self.as_of(tick))
        after = _flatten(self.current())
        added = tuple(sorted(key for key in after if key not in before))
        removed = tuple(sorted(key for key in before if key not in after))
        changed = tuple(sorted(key for key in after if key in before and after[key] != before[key]))
        return StateDelta(
            from_tick=tick,
            to_tick=self._repository.watermark().tick,
            added=added,
            changed=changed,
            removed=removed,
        )

    def history(self, kind: str) -> tuple[Record, ...]:
        """Return every committed record of ``kind`` in sequence order."""

        return tuple(rec for rec in self._repository.visible() if rec.kind == kind)

    def latest(self, kind: str) -> Record | None:
        records = self.history(kind)
        return records[-1] if records else None

    def facts(self) -> dict[str, bool]:
        """Return the interlock facts implied by the current state."""

        return derive_facts(self.current())

    def fold(self, records: tuple[Record, ...]) -> dict[str, Any]:
        """Expose the same fold the stream uses, for callers holding records."""

        return reduce_state(records)
