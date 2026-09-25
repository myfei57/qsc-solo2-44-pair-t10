"""Materialised state files with an expiry window."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ..errors import ValidationError
from ..versioning.expiry import Validity


@dataclass(frozen=True, slots=True)
class Snapshot:
    """A state image taken at a watermark."""

    snapshot_id: str
    watermark_seq: int
    generation: int
    tick: int
    state: Mapping[str, Any]
    validity: Validity

    def is_expired(self, now: int) -> bool:
        return self.validity.is_expired(now)

    def describe(self, now: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "snapshot_id": self.snapshot_id,
            "watermark_seq": self.watermark_seq,
            "generation": self.generation,
            "tick": self.tick,
            "valid_until": self.validity.valid_until(),
        }
        if now is not None:
            payload["expired"] = self.is_expired(now)
        return payload

    def to_document(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "watermark_seq": self.watermark_seq,
            "generation": self.generation,
            "tick": self.tick,
            "state": _thaw(self.state),
            "validity": self.validity.to_document(),
        }

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "Snapshot":
        state = document.get("state") or {}
        if not isinstance(state, Mapping):
            raise ValidationError("snapshot state must be a mapping")
        return cls(
            snapshot_id=str(document["snapshot_id"]),
            watermark_seq=int(document["watermark_seq"]),
            generation=int(document["generation"]),
            tick=int(document["tick"]),
            state=state,
            validity=Validity.from_document(document["validity"]),
        )


def _thaw(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {key: _thaw(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_thaw(item) for item in value]
    return value


class SnapshotStore:
    """Reads and writes snapshots, either below a directory or in memory."""

    __slots__ = ("_directory", "_memory")

    def __init__(self, directory: Path | str | None = None) -> None:
        self._directory = None if directory is None else Path(directory)
        self._memory: list[Snapshot] = []

    @property
    def directory(self) -> Path | None:
        return self._directory

    def save(self, snapshot: Snapshot) -> Path | None:
        if self._directory is None:
            self._memory.append(snapshot)
            return None
        self._directory.mkdir(parents=True, exist_ok=True)
        target = self._directory / f"{snapshot.snapshot_id}.json"
        text = json.dumps(snapshot.to_document(), sort_keys=True, ensure_ascii=False)
        target.write_text(text + "\n", encoding="utf-8")
        return target

    def load_all(self) -> list[Snapshot]:
        if self._directory is None:
            snapshots = list(self._memory)
            snapshots.sort(key=lambda snap: (snap.watermark_seq, snap.snapshot_id))
            return snapshots
        if not self._directory.exists():
            return []
        snapshots = []
        for path in sorted(self._directory.glob("*.json")):
            document = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(document, Mapping):
                raise ValidationError("snapshot file must contain an object", path=str(path))
            snapshots.append(Snapshot.from_document(document))
        snapshots.sort(key=lambda snap: (snap.watermark_seq, snap.snapshot_id))
        return snapshots
