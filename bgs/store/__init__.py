"""Append only record stream with a commit watermark and snapshots."""

from __future__ import annotations

from .codec import JournalEntry, decode_entry, encode_entry
from .journal import FileBackend, MemoryBackend
from .records import Record
from .replay import merge_state, reduce_state, state_at_tick
from .repository import RecordRepository, RestoreReport
from .snapshot import Snapshot, SnapshotStore
from .tombstone import effective_records, hidden_sequences, rollback_targets
from .watermark import Watermark

__all__ = [
    "FileBackend",
    "JournalEntry",
    "MemoryBackend",
    "Record",
    "RecordRepository",
    "RestoreReport",
    "Snapshot",
    "SnapshotStore",
    "Watermark",
    "decode_entry",
    "effective_records",
    "encode_entry",
    "hidden_sequences",
    "merge_state",
    "reduce_state",
    "rollback_targets",
    "state_at_tick",
]
