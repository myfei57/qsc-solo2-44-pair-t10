"""Feed timeline built from the stream."""

from __future__ import annotations

from typing import Any, Iterable

from ..store.records import Record

BATCH_KIND = "feed.batch"
OPEN_KIND = "feed.open"


def batch_timeline(records: Iterable[Record]) -> list[dict[str, Any]]:
    """Turn the feed records into a timeline the console can list."""

    timeline: list[dict[str, Any]] = []
    for record in records:
        if record.kind not in (BATCH_KIND, OPEN_KIND):
            continue
        entry: dict[str, Any] = {
            "seq": record.seq,
            "kind": record.kind,
            "tick": record.tick,
            "generation": record.generation,
        }
        entry.update({key: value for key, value in record.payload.items() if key != "origin"})
        timeline.append(entry)
    return timeline
