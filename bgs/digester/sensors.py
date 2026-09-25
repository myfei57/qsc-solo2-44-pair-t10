"""Mapping of physical sensors onto zones."""

from __future__ import annotations

from typing import Any

from ..errors import ValidationError
from .zones import validate_zone

SENSOR_KINDS: tuple[str, ...] = ("temperature", "pressure", "level")


def validate_sensor(sensor_id: str, kind: str) -> str:
    """Check a sensor identifier and its measurement kind."""

    if not sensor_id:
        raise ValidationError("sensor identifier must not be empty")
    if kind not in SENSOR_KINDS:
        raise ValidationError("unknown sensor kind", kind=kind, known=list(SENSOR_KINDS))
    return sensor_id


def sensor_payload(sensor_id: str, zone: str, kind: str, tick: int) -> dict[str, Any]:
    """Build the record body for one sensor mapping."""

    return {
        "active": True,
        "sensor_id": validate_sensor(sensor_id, kind),
        "zone": validate_zone(zone),
        "kind": kind,
        "mapped_tick": tick,
    }
