"""Heater service."""

from __future__ import annotations

from typing import Any

from ..errors import NotFoundError, OverLimitError
from ..service_base import LineService
from .ramp import plan_ramp, wall_temperature
from .wall import wall_reading

RAMP_KIND = "heat.ramp"
WALL_KIND = "heat.wall"


class HeatService(LineService):
    """Ramps the wall temperature once the mixer is turning."""

    origin = "heat"
    line = "feed"

    def ramp(self, target_c: float) -> dict[str, Any]:
        """Start a ramp towards ``target_c``."""

        self.require("heat.ramp")
        plan = plan_ramp(target_c, self.context.config.limits)
        measured = wall_temperature(plan.target_c)
        reading = wall_reading(self.context.thresholds, measured, self.context.clock.now())
        if not reading.ok:
            raise OverLimitError(
                "measured wall temperature is above its bound",
                temperature_c=measured,
                code=reading.code,
            )
        self.publish(
            RAMP_KIND,
            {"active": True, "target_c": plan.target_c, "band_c": plan.band_c},
        )
        self.publish(WALL_KIND, {"active": True, **reading.describe()})
        self.emit("heat.ramped", plan.describe())
        return self.status()

    def cool(self) -> dict[str, Any]:
        """End the ramp."""

        self.require("heat.cool")
        ramp = self._ramp_record()
        self.publish(
            RAMP_KIND,
            {"active": False, "target_c": ramp.get("target_c", 0.0)},
        )
        self.emit("heat.cooled")
        return self.status()

    def status(self) -> dict[str, Any]:
        state = self.state()
        heat = state.get("heat", {})
        ramp = heat.get("ramp") if isinstance(heat, dict) else None
        wall = heat.get("wall") if isinstance(heat, dict) else None
        return {
            "ramping": bool(ramp.get("active", False)) if isinstance(ramp, dict) else False,
            "target_c": ramp.get("target_c") if isinstance(ramp, dict) else None,
            "wall_c": wall.get("temperature_c") if isinstance(wall, dict) else None,
            "wall_ok": bool(wall.get("ok", False)) if isinstance(wall, dict) else False,
            "bound_c": self.context.config.limits.wall_temp_max_c,
        }

    def _ramp_record(self) -> dict[str, Any]:
        heat = self.state().get("heat", {})
        entry = heat.get("ramp") if isinstance(heat, dict) else None
        if not isinstance(entry, dict):
            raise NotFoundError("heater was never ramped", kind=RAMP_KIND)
        return entry
