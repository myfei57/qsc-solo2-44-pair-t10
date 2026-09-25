"""Generation counters for parameters, confirmations and baselines."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import StaleGenerationError, ValidationError


@dataclass(frozen=True, slots=True)
class GenerationToken:
    """A named generation handed out when a subject is re-issued."""

    subject: str
    value: int
    issued_tick: int

    def describe(self) -> dict[str, Any]:
        return {"subject": self.subject, "generation": self.value, "issued_tick": self.issued_tick}


class GenerationRegistry:
    """Tracks the newest generation of every subject."""

    __slots__ = ("_current", "_issued")

    def __init__(self) -> None:
        self._current: dict[str, int] = {}
        self._issued: dict[str, int] = {}

    def current(self, subject: str) -> int:
        """Return the newest generation, or zero when never issued."""

        return self._current.get(subject, 0)

    def issued_count(self, subject: str) -> int:
        return self._issued.get(subject, 0)

    def bump(self, subject: str, tick: int) -> GenerationToken:
        """Issue the next generation of ``subject``."""

        if not subject:
            raise ValidationError("generation subject must not be empty")
        if tick < 0:
            raise ValidationError("generation tick must not be negative", tick=tick)
        value = self.current(subject) + 1
        self._current[subject] = value
        self._issued[subject] = self._issued.get(subject, 0) + 1
        return GenerationToken(subject=subject, value=value, issued_tick=tick)

    def observe(self, subject: str, value: int) -> None:
        """Adopt a generation read back from the stream.

        Replay must never move a subject backwards, otherwise a restart could
        silently accept a confirmation that belongs to a replaced generation.
        """

        if value < 0:
            raise ValidationError("observed generation must not be negative", value=value)
        if value < self.current(subject):
            raise StaleGenerationError(
                "replay tried to move a generation backwards",
                subject=subject,
                observed=value,
                current=self.current(subject),
            )
        self._current[subject] = value
        self._issued[subject] = max(self._issued.get(subject, 0), value)

    def require(self, token: GenerationToken, *, now: int) -> None:
        """Raise when ``token`` is not the newest generation of its subject."""

        newest = self.current(token.subject)
        if token.value > newest:
            raise ValidationError(
                "generation was never issued",
                subject=token.subject,
                claimed=token.value,
                current=newest,
            )
        if token.value < newest:
            raise StaleGenerationError(
                "artifact belongs to a replaced generation",
                subject=token.subject,
                claimed=token.value,
                current=newest,
                now=now,
            )

    def snapshot(self) -> dict[str, int]:
        return dict(self._current)
