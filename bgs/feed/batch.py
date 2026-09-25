"""Feed batch planning."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..config import Limits
from ..errors import OverLimitError, ValidationError


@dataclass(frozen=True, slots=True)
class CyclePlan:
    """A batch that may be fed in one cycle."""

    batch_id: str
    quantity: float
    unit: str

    def describe(self) -> dict[str, Any]:
        return {"batch_id": self.batch_id, "quantity": self.quantity, "unit": self.unit}


def plan_cycle(batch_id: str, quantity: float, limits: Limits) -> CyclePlan:
    """Validate a batch before it reaches the registry."""

    if not batch_id:
        raise ValidationError("batch identifier must not be empty")
    if quantity <= 0:
        raise ValidationError("batch quantity must be positive", quantity=quantity)
    if quantity > limits.feed_cycle_max_tons:
        raise OverLimitError(
            "batch quantity is above the cycle bound",
            batch_id=batch_id,
            quantity=quantity,
            limit=limits.feed_cycle_max_tons,
        )
    return CyclePlan(batch_id=batch_id, quantity=quantity, unit="t")
