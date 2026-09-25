"""Start preparation for the compressor."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ..errors import NotFoundError
from ..versioning.facade import VersionedArtifacts

SUBJECT = "desul"


@dataclass(frozen=True, slots=True)
class PreparedStart:
    """The verification a compressor start depends on."""

    generation: int
    confirmation_id: str
    issuer: str
    valid_until: int

    def describe(self) -> dict[str, Any]:
        return {
            "generation": self.generation,
            "confirmation_id": self.confirmation_id,
            "issuer": self.issuer,
            "valid_until": self.valid_until,
        }


def prepare_start(versions: VersionedArtifacts, *, now: int) -> PreparedStart:
    """Fetch the outlet verification that a start must still be allowed to use."""

    generation = versions.current_generation(SUBJECT)
    if generation < 1:
        raise NotFoundError("the outlet was never verified", subject=SUBJECT)
    confirmation = versions.require_confirmation(SUBJECT, generation=generation, now=now)
    return PreparedStart(
        generation=generation,
        confirmation_id=confirmation.confirmation_id,
        issuer=confirmation.issuer,
        valid_until=confirmation.validity.valid_until(),
    )
