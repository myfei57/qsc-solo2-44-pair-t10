"""Filtering of the record stream for the audit surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ..errors import ValidationError
from ..store.records import Record
from ..store.tombstone import hidden_sequences


@dataclass(frozen=True, slots=True)
class RecordQuery:
    """The audit endpoint's view of the record stream."""

    include_tombstones: bool = False
    kinds: tuple[str, ...] = ()
    origins: tuple[str, ...] = ()
    seq_from: int | None = None
    seq_to: int | None = None
    tick_from: int | None = None
    tick_to: int | None = None
    limit: int | None = None

    def __post_init__(self) -> None:
        if self.seq_from is not None and self.seq_to is not None and self.seq_from > self.seq_to:
            raise ValidationError(
                "seq range is inverted", seq_from=self.seq_from, seq_to=self.seq_to
            )
        if self.tick_from is not None and self.tick_to is not None and self.tick_from > self.tick_to:
            raise ValidationError(
                "tick range is inverted", tick_from=self.tick_from, tick_to=self.tick_to
            )
        if self.limit is not None and self.limit < 1:
            raise ValidationError("limit must be a positive integer", limit=self.limit)

    def matches(self, record: Record) -> bool:
        """Decide whether one record belongs in the listing."""

        if record.is_tombstone and not self.include_tombstones:
            return False
        if self.kinds and record.kind not in self.kinds:
            return False
        if self.origins and record.origin not in self.origins:
            return False
        if self.seq_from is not None and record.seq < self.seq_from:
            return False
        if self.seq_to is not None and record.seq > self.seq_to:
            return False
        if self.tick_from is not None and record.tick < self.tick_from:
            return False
        if self.tick_to is not None and record.tick > self.tick_to:
            return False
        return True

    def apply(self, records: Iterable[Record]) -> tuple[Record, ...]:
        """Return the matching records, honouring the limit."""

        matched = [record for record in records if self.matches(record)]
        if self.limit is not None:
            matched = matched[-self.limit :]
        return tuple(matched)

    def describe(self) -> dict[str, Any]:
        return {
            "include_tombstones": self.include_tombstones,
            "kinds": list(self.kinds),
            "origins": list(self.origins),
            "seq_from": self.seq_from,
            "seq_to": self.seq_to,
            "tick_from": self.tick_from,
            "tick_to": self.tick_to,
            "limit": self.limit,
        }


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Matching records plus a small summary."""

    query: RecordQuery
    records: tuple[Record, ...] = field(default_factory=tuple)
    voided: frozenset[int] = field(default_factory=frozenset)

    @property
    def total(self) -> int:
        return len(self.records)

    def by_kind(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.records:
            counts[record.kind] = counts.get(record.kind, 0) + 1
        return counts

    def by_origin(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.records:
            counts[record.origin] = counts.get(record.origin, 0) + 1
        return counts

    def is_voided(self, record: Record) -> bool:
        """Return whether a tombstone neutralised ``record``."""

        return record.seq in self.voided

    def describe(self) -> dict[str, Any]:
        return {
            "query": self.query.describe(),
            "total": self.total,
            "voided": sum(1 for record in self.records if self.is_voided(record)),
            "by_kind": self.by_kind(),
            "by_origin": self.by_origin(),
            "records": [
                {
                    "seq": record.seq,
                    "kind": record.kind,
                    "origin": record.origin,
                    "generation": record.generation,
                    "tick": record.tick,
                    "tombstone_of": record.tombstone_of,
                    "voided": self.is_voided(record),
                    "payload": dict(record.payload),
                }
                for record in self.records
            ],
        }


def run_query(records: Iterable[Record], query: RecordQuery) -> QueryResult:
    """Apply ``query`` and wrap the outcome."""

    materialised = tuple(records)
    return QueryResult(
        query=query,
        records=query.apply(materialised),
        voided=hidden_sequences(materialised),
    )
