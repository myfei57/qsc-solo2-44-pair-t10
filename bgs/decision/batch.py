"""Batch identity that must stay unique across the whole history."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import DuplicateError, NotFoundError, ValidationError


@dataclass(frozen=True, slots=True)
class Batch:
    """One declared feed batch."""

    batch_id: str
    generation: int
    tick: int
    quantity: float
    unit: str = "t"

    def describe(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "generation": self.generation,
            "tick": self.tick,
            "quantity": self.quantity,
            "unit": self.unit,
        }


class BatchRegistry:
    """Remembers every batch identifier that was ever declared."""

    __slots__ = ("_batches",)

    def __init__(self) -> None:
        self._batches: dict[str, Batch] = {}

    def declare(self, batch_id: str, *, tick: int, generation: int, quantity: float, unit: str = "t") -> Batch:
        """Register a new batch, refusing identifiers that already exist."""

        if not batch_id:
            raise ValidationError("batch identifier must not be empty")
        if quantity <= 0:
            raise ValidationError("batch quantity must be positive", quantity=quantity)
        if batch_id in self._batches:
            existing = self._batches[batch_id]
            raise DuplicateError(
                "batch identifier was already declared",
                batch_id=batch_id,
                first_declared_tick=existing.tick,
            )
        batch = Batch(batch_id=batch_id, generation=generation, tick=tick, quantity=quantity, unit=unit)
        self._batches[batch_id] = batch
        return batch

    def adopt(self, batch: Batch) -> None:
        """Adopt a batch read back from the stream during replay."""

        if batch.batch_id in self._batches:
            raise DuplicateError("replayed batch identifier is not unique", batch_id=batch.batch_id)
        self._batches[batch.batch_id] = batch

    def has(self, batch_id: str) -> bool:
        return batch_id in self._batches

    def get(self, batch_id: str) -> Batch:
        batch = self._batches.get(batch_id)
        if batch is None:
            raise NotFoundError("batch identifier is unknown", batch_id=batch_id)
        return batch

    def all(self) -> tuple[Batch, ...]:
        return tuple(self._batches[key] for key in sorted(self._batches))

    def count(self) -> int:
        return len(self._batches)
