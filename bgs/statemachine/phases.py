"""The declared stage order of each line."""

from __future__ import annotations

from enum import Enum
from typing import Mapping

from ..errors import ValidationError


class FeedPhase(str, Enum):
    """Stages of the feed line."""

    IDLE = "idle"
    STIR_CONFIRMED = "stir_confirmed"
    FEEDING = "feeding"
    FERMENTING = "fermenting"


class UpgradePhase(str, Enum):
    """Stages of the upgrading line."""

    IDLE = "idle"
    DESUL_VERIFIED = "desul_verified"
    COMPRESSING = "compressing"
    VALVE_OPEN = "valve_open"
    PRESSURE_RAMP = "pressure_ramp"


class VentPhase(str, Enum):
    """Stages of the vent line."""

    NORMAL = "normal"
    QUALITY_ALARM = "quality_alarm"
    FLARING = "flaring"
    RECOVERED = "recovered"


class GasPhase(str, Enum):
    """Stages of the storage inlet."""

    IDLE = "idle"
    OPEN = "open"
    SEALED = "sealed"


LINE_SEQUENCES: Mapping[str, tuple[Enum, ...]] = {
    "feed": tuple(FeedPhase),
    "upgrade": tuple(UpgradePhase),
    "vent": tuple(VentPhase),
    "gas": tuple(GasPhase),
}


def sequence_for(line: str) -> tuple[Enum, ...]:
    """Return the declared stage order of ``line``."""

    order = LINE_SEQUENCES.get(line)
    if order is None:
        raise ValidationError("unknown line", line=line)
    return order


def phase_names(line: str) -> list[str]:
    """Return the stage names of ``line`` in order."""

    return [str(phase.value) for phase in sequence_for(line)]
