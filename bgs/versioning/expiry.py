"""Validity windows shared by confirmations, baselines and snapshots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..errors import ArtifactExpiredError, ValidationError

NEVER_EXPIRES = -1


@dataclass(frozen=True, slots=True)
class Validity:
    """Issue tick plus a tick budget."""

    issued_tick: int
    ttl_ticks: int = NEVER_EXPIRES

    def __post_init__(self) -> None:
        if self.issued_tick < 0:
            raise ValidationError("issued tick must not be negative", issued_tick=self.issued_tick)
        if self.ttl_ticks < -1 or self.ttl_ticks == 0:
            raise ValidationError("ttl must be a positive tick budget or never expire", ttl_ticks=self.ttl_ticks)

    @classmethod
    def of(cls, issued_tick: int, ttl_ticks: int) -> "Validity":
        return cls(issued_tick=issued_tick, ttl_ticks=ttl_ticks)

    @classmethod
    def never(cls, issued_tick: int) -> "Validity":
        return cls(issued_tick=issued_tick, ttl_ticks=NEVER_EXPIRES)

    def valid_until(self) -> int:
        """Return the last tick on which the artifact is still usable."""

        if self.ttl_ticks == NEVER_EXPIRES:
            return NEVER_EXPIRES
        return self.issued_tick + self.ttl_ticks

    def is_expired(self, now: int) -> bool:
        limit = self.valid_until()
        return limit != NEVER_EXPIRES and now > limit

    def age(self, now: int) -> int:
        return max(0, now - self.issued_tick)

    def remaining(self, now: int) -> int:
        """Return the ticks left, or a negative number once expired."""

        limit = self.valid_until()
        if limit == NEVER_EXPIRES:
            return NEVER_EXPIRES
        return limit - now

    def require(self, now: int, *, label: str) -> None:
        """Raise when the artifact is past its validity window."""

        if self.is_expired(now):
            raise ArtifactExpiredError(
                f"{label} expired at tick {self.valid_until()}",
                label=label,
                now=now,
                valid_until=self.valid_until(),
                issued_tick=self.issued_tick,
                ttl_ticks=self.ttl_ticks,
            )

    def to_document(self) -> dict[str, Any]:
        return {"issued_tick": self.issued_tick, "ttl_ticks": self.ttl_ticks}

    @classmethod
    def from_document(cls, document: Mapping[str, Any]) -> "Validity":
        return cls(issued_tick=int(document["issued_tick"]), ttl_ticks=int(document.get("ttl_ticks", NEVER_EXPIRES)))
