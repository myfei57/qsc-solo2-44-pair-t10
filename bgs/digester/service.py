"""Vessel service."""

from __future__ import annotations

from typing import Any

from ..errors import OverLimitError
from ..facts import latch_state
from ..service_base import LineService
from ..statemachine.latch import Latch
from .latch import evaluate_pressure
from .sensors import sensor_payload
from .zones import zone_reading

PRESSURE_KIND = "digester.pressure"
ZONE_KIND = "digester.zone"
SENSOR_KIND = "digester.sensor"
LATCH_KIND = "digester.latch"
CLEAR_KIND = "digester.clear"
HYSTERESIS_KPA = 2.0


class DigesterService(LineService):
    """Tracks vessel pressure and the over pressure latch."""

    origin = "digester"
    line = "feed"

    def __init__(self, context, machine=None) -> None:
        super().__init__(context, machine)
        self._latch = Latch("overpressure")

    def observe_pressure(self, kpa: float) -> dict[str, Any]:
        """Record a vessel pressure reading and act on the latch."""

        limit = self.context.config.limits.vessel_pressure_max_kpa
        self._sync_latch()
        decision = evaluate_pressure(
            kpa,
            limit=limit,
            hysteresis=HYSTERESIS_KPA,
            latched=self._latch.latched,
        )
        self.publish(PRESSURE_KIND, {"active": True, **decision.describe()})
        if decision.should_latch and not self._latch.latched:
            event = self._latch.set(tick=self.context.clock.now(), reason="vessel pressure above bound")
            self.publish(LATCH_KIND, {"active": True, "reason": event.reason, "step": event.step})
            self.raise_alarm("digester.overpressure", {"kpa": kpa, "limit": limit})
        elif decision.should_clear:
            event = self._latch.clear(tick=self.context.clock.now(), reason="vessel pressure back inside band")
            self.publish(CLEAR_KIND, {"active": False, "reason": event.reason, "step": event.step})
            self.emit("digester.pressure_recovered", {"kpa": kpa})
        else:
            self.emit("digester.pressure_read", {"kpa": kpa})
        if not decision.ok:
            raise OverLimitError(
                "vessel pressure is above its bound",
                kpa=kpa,
                limit=limit,
            )
        return self.status()

    def set_zone(self, zone: str, temperature_c: float) -> dict[str, Any]:
        """Record a zone temperature."""

        reading = zone_reading(self.context.thresholds, zone, temperature_c, self.context.clock.now())
        self.publish(ZONE_KIND, reading.describe())
        self.emit("digester.zone_read", reading.describe())
        return self.status()

    def map_sensor(self, sensor_id: str, zone: str, kind: str) -> dict[str, Any]:
        """Bind a physical sensor to a zone."""

        payload = sensor_payload(sensor_id, zone, kind, self.context.clock.now())
        self.publish(SENSOR_KIND, payload)
        self.emit("digester.sensor_mapped", payload)
        return self.status()

    def status(self) -> dict[str, Any]:
        state = self.state()
        digester = state.get("digester", {})
        pressure = digester.get("pressure") if isinstance(digester, dict) else None
        zones = {
            leaf: payload
            for leaf, payload in (digester.items() if isinstance(digester, dict) else ())
            if leaf in ("upper", "middle", "lower") or leaf == "zone"
        }
        sensors = digester.get("sensor") if isinstance(digester, dict) else None
        return {
            "kpa": pressure.get("kpa") if isinstance(pressure, dict) else None,
            "pressure_ok": bool(pressure.get("ok", False)) if isinstance(pressure, dict) else False,
            "limit_kpa": self.context.config.limits.vessel_pressure_max_kpa,
            "latched": latch_state(state, "digester"),
            "latch": self._latch.describe(),
            "zones": zones,
            "sensor": sensors,
        }

    def _sync_latch(self) -> None:
        """Adopt the latch position recorded in the stream."""

        state = self.state()
        digester = state.get("digester", {})
        latch = digester.get("latch") if isinstance(digester, dict) else None
        cleared = digester.get("clear") if isinstance(digester, dict) else None
        step = max(
            int(latch.get("step", 0)) if isinstance(latch, dict) else 0,
            int(cleared.get("step", 0)) if isinstance(cleared, dict) else 0,
        )
        self._latch.sync(latched=latch_state(state, "digester"), step=step, reason="synced")
