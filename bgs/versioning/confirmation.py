"""Operator confirmations that carry a generation and an expiry."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import ArtifactExpiredError, NotFoundError, StaleGenerationError
from .expiry import Validity


@dataclass(frozen=True, slots=True)
class Confirmation:
    """A signed off step such as a verified outlet or a settled mix."""

    confirmation_id: str
    subject: str
    generation: int
    issuer: str
    validity: Validity

    @property
    def issued_tick(self) -> int:
        return self.validity.issued_tick

    def is_expired(self, now: int) -> bool:
        return self.validity.is_expired(now)

    def usable(self, *, generation: int, now: int) -> bool:
        return not self.is_expired(now) and generation == self.generation

    def describe(self, now: int | None = None) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "confirmation_id": self.confirmation_id,
            "subject": self.subject,
            "generation": self.generation,
            "issuer": self.issuer,
            "issued_tick": self.issued_tick,
            "valid_until": self.validity.valid_until(),
        }
        if now is not None:
            payload["expired"] = self.is_expired(now)
            payload["remaining"] = self.validity.remaining(now)
        return payload


class ConfirmationLedger:
    """Keeps the confirmation history of every subject."""

    __slots__ = ("_history",)

    def __init__(self) -> None:
        self._history: dict[str, list[Confirmation]] = {}

    def record(self, confirmation: Confirmation) -> None:
        if confirmation.generation < 1:
            raise StaleGenerationError(
                "confirmation must name a generation that was already issued",
                subject=confirmation.subject,
                generation=confirmation.generation,
            )
        self._history.setdefault(confirmation.subject, []).append(confirmation)

    def latest(self, subject: str) -> Confirmation | None:
        entries = self._history.get(subject)
        return entries[-1] if entries else None

    def history(self, subject: str) -> tuple[Confirmation, ...]:
        return tuple(self._history.get(subject, ()))

    def subjects(self) -> tuple[str, ...]:
        return tuple(sorted(self._history))

    def require(self, subject: str, *, generation: int, now: int) -> Confirmation:
        """Return the confirmation or explain why it cannot be used."""

        confirmation = self.latest(subject)
        if confirmation is None:
            raise NotFoundError("no confirmation was recorded", subject=subject)
        if confirmation.is_expired(now):
            raise ArtifactExpiredError(
                "confirmation expired",
                subject=subject,
                confirmation_id=confirmation.confirmation_id,
                valid_until=confirmation.validity.valid_until(),
                now=now,
            )
        if confirmation.generation != generation:
            raise StaleGenerationError(
                "confirmation belongs to another generation",
                subject=subject,
                confirmation_generation=confirmation.generation,
                required_generation=generation,
            )
        return confirmation
