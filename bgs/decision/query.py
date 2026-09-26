"""Filtering of the record stream for the audit surfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

from ..errors import ValidationError
from ..store.records import Record
from ..store.tombstone import hidden_sequences


@dataclass(frozen=True, slots=True)
class RecordQuery:
    """The audit endpoint's view of the record stream.

    ``include_tombstones`` only governs the tombstone marker records that
    record a rollback.  Records neutralised by those tombstones are never
    counted as effective: they remain visible as an audit trail but are
    carried separately from the effective ledger.
    """

    kinds: tuple[str, ...] = ()
    origins: tuple[str, ...] = ()
    seq_from: int | None = None
    seq_to: int | None = None
    tick_from: int | None = None
    tick_to: int | None = None
    include_tombstones: bool = False
    limit: int | None = None

    def __post_init__(self) -> None:
        if self.limit is not None and self.limit < 1:
            raise ValidationError("limit must be a positive integer", limit=self.limit)
        if self.seq_from is not None and self.seq_to is not None and self.seq_from > self.seq_to:
            raise ValidationError("seq range is inverted", seq_from=self.seq_from, seq_to=self.seq_to)
        if self.tick_from is not None and self.tick_to is not None and self.tick_from > self.tick_to:
            raise ValidationError("tick range is inverted", tick_from=self.tick_from, tick_to=self.tick_to)

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
        """Return the matching records, honouring the limit.

        The limit is applied from the end so callers always see the most
        recent entries.
        """

        matched = [record for record in records if self.matches(record)]
        if self.limit is not None:
            matched = matched[-self.limit :]
        return tuple(matched)

    def describe(self) -> dict[str, Any]:
        return {
            "kinds": list(self.kinds),
            "origins": list(self.origins),
            "seq_from": self.seq_from,
            "seq_to": self.seq_to,
            "tick_from": self.tick_from,
            "tick_to": self.tick_to,
            "include_tombstones": self.include_tombstones,
            "limit": self.limit,
        }


@dataclass(frozen=True, slots=True)
class QueryResult:
    """Matching records plus a small summary."""

    query: RecordQuery
    records: tuple[Record, ...] = field(default_factory=tuple)
    hidden: frozenset[int] = frozenset()
    tombstone_by: dict[int, Record] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return len(self.records)

    @property
    def tombstones(self) -> tuple[Record, ...]:
        return tuple(record for record in self.records if record.is_tombstone)

    @property
    def voided(self) -> tuple[Record, ...]:
        """Records shown for the audit trail but neutralised by a tombstone."""

        return tuple(record for record in self.records if record.seq in self.hidden)

    @property
    def effective(self) -> tuple[Record, ...]:
        """Records still in force: neither tombstones nor tombstoned."""

        return tuple(
            record for record in self.records if not record.is_tombstone and record.seq not in self.hidden
        )

    def by_kind(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.effective:
            counts[record.kind] = counts.get(record.kind, 0) + 1
        return counts

    def by_origin(self) -> dict[str, int]:
        counts: dict[str, int] = {}
        for record in self.effective:
            counts[record.origin] = counts.get(record.origin, 0) + 1
        return counts

    def _record_document(self, record: Record) -> dict[str, Any]:
        document = {
            "seq": record.seq,
            "kind": record.kind,
            "origin": record.origin,
            "generation": record.generation,
            "tick": record.tick,
            "tombstone_of": record.tombstone_of,
            "payload": dict(record.payload),
        }
        if record.is_tombstone:
            document["status"] = "tombstone"
        elif record.seq in self.hidden:
            document["status"] = "void"
            document["voided_by"] = self.tombstone_by[record.seq].seq
        else:
            document["status"] = "effective"
        return document

    def describe(self) -> dict[str, Any]:
        return {
            "query": self.query.describe(),
            "total": self.total,
            "effective_total": len(self.effective),
            "voided_total": len(self.voided),
            "tombstone_total": len(self.tombstones),
            "by_kind": self.by_kind(),
            "by_origin": self.by_origin(),
            "records": [self._record_document(record) for record in self.records],
        }


def run_query(records: Iterable[Record], query: RecordQuery) -> QueryResult:
    """Apply ``query`` and wrap the outcome.

    Tombstone reach is computed from the whole stream handed in, not only
    from the rows that survive the filters: otherwise filtering by kind
    could make a voided record look effective again by hiding the
    tombstone that neutralised it.
    """

    materialised = tuple(records)
    hidden = hidden_sequences(materialised)
    tombstone_by: dict[int, Record] = {}
    for record in materialised:
        if record.is_tombstone and record.tombstone_of is not None:
            tombstone_by.setdefault(record.tombstone_of, record)
    return QueryResult(
        query=query,
        records=query.apply(materialised),
        hidden=hidden,
        tombstone_by=tombstone_by,
    )
