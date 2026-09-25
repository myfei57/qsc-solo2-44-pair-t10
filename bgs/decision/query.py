"""Filtering of the record stream for the audit surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ..errors import ValidationError
from ..store.records import Record


@dataclass(frozen=True, slots=True)
class RecordQuery:
    """The audit endpoint's view of the record stream."""

    include_tombstones: bool = False
    limit: int | None = None

    def matches(self, record: Record) -> bool:
        """Decide whether one record belongs in the listing."""

        if record.is_tombstone and not self.include_tombstones:
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
            "limit": self.limit,
        }


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Matching records plus a small summary."""

    query: RecordQuery
    records: tuple[Record, ...] = field(default_factory=tuple)

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

    def describe(self) -> dict[str, Any]:
        return {
            "query": self.query.describe(),
            "total": self.total,
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
                    "payload": dict(record.payload),
                }
                for record in self.records
            ],
        }


def run_query(records: Iterable[Record], query: RecordQuery) -> QueryResult:
    """Apply ``query`` and wrap the outcome."""

    return QueryResult(query=query, records=query.apply(records))
