"""Storage service."""

from __future__ import annotations

from typing import Any

from ..errors import OverLimitError
from ..service_base import LineService
from ..statemachine.phases import GasPhase
from .inlet import plan_inlet
from .pressure import storage_reading

INLET_KIND = "gas.inlet"
STORED_KIND = "gas.stored"


class GasService(LineService):
    """Opens the inlet only on a clear line and stores within the pressure bound."""

    origin = "gas"
    line = "gas"

    def open_inlet(self) -> dict[str, Any]:
        """Open the storage inlet."""

        self.require("gas.inlet")
        self.advance(GasPhase.OPEN.value, "storage inlet opened")
        self.publish(INLET_KIND, {"active": True, "plan": plan_inlet(self.facts()).describe()})
        self.emit("gas.inlet_opened")
        return self.status()

    def close_inlet(self) -> dict[str, Any]:
        """Close the storage inlet."""

        self.require("gas.inlet_close")
        self.advance(GasPhase.SEALED.value, "storage inlet closed")
        self.publish(INLET_KIND, {"active": False})
        self.emit("gas.inlet_closed")
        return self.status()

    def store_gas(self, volume_m3: float, pressure_kpa: float) -> dict[str, Any]:
        """Record a stored volume."""

        self.require("gas.store", required_phase=GasPhase.OPEN.value)
        reading = storage_reading(self.context.thresholds, volume_m3, pressure_kpa, self.context.clock.now())
        if not reading.ok:
            self.raise_alarm("gas.pressure_high", reading.describe())
            raise OverLimitError(
                "storage pressure is above its bound",
                pressure_kpa=pressure_kpa,
                limit=reading.limit,
            )
        self.publish(STORED_KIND, {"active": True, **reading.describe()})
        self.emit("gas.stored", reading.describe())
        return self.status()

    def status(self) -> dict[str, Any]:
        state = self.state()
        gas = state.get("gas", {})
        inlet = gas.get("inlet") if isinstance(gas, dict) else None
        stored = gas.get("stored") if isinstance(gas, dict) else None
        return {
            "phase": self.machine.phase,
            "sequence": self.machine.order(),
            "inlet_open": bool(inlet.get("active", False)) if isinstance(inlet, dict) else False,
            "blocked_by": list(plan_inlet(self.facts()).blocked_by),
            "volume_m3": stored.get("volume_m3") if isinstance(stored, dict) else None,
            "pressure_kpa": stored.get("pressure_kpa") if isinstance(stored, dict) else None,
            "limit_kpa": self.context.config.limits.storage_pressure_max_kpa,
        }
