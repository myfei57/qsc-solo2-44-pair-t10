"""Membrane service."""

from __future__ import annotations

from typing import Any

from ..errors import OverLimitError
from ..service_base import LineService
from ..statemachine.phases import UpgradePhase
from .analyzer import QUALITY_KIND, evaluate_methane, rebuild_window
from .status import compose_status
from .valve import ValveState, valve_payload

VALVE_KIND = "mem.valve"
RAMP_KIND = "mem.ramp"
BASELINE_NAME = "membrane_pressure"
RAMP_BAND_KPA = 2.0


class MemService(LineService):
    """Opens the product valve, ramps pressure and analyses methane."""

    origin = "mem"
    line = "upgrade"

    def open_valve(self, *, reason: str = "operator request") -> dict[str, Any]:
        """Open the product gas valve."""

        self.require("mem.valve")
        self.advance(UpgradePhase.VALVE_OPEN.value, "product valve opened")
        self.publish(
            VALVE_KIND,
            valve_payload(ValveState(open=True, tick=self.context.clock.now(), reason=reason)),
        )
        self.emit("mem.valve_opened", {"reason": reason})
        return self.status()

    def close_valve(self, *, reason: str = "operator request") -> dict[str, Any]:
        """Close the product gas valve."""

        self.require("mem.valve_close")
        self.publish(
            VALVE_KIND,
            valve_payload(ValveState(open=False, tick=self.context.clock.now(), reason=reason)),
        )
        self.emit("mem.valve_closed", {"reason": reason})
        return self.status()

    def press_ramp(self, pressure_kpa: float, *, baseline_generation: int) -> dict[str, Any]:
        """Ramp the membrane pressure against the calibrated design value."""

        self.require("mem.ramp", required_phase=UpgradePhase.VALVE_OPEN.value)
        now = self.context.clock.now()
        baseline = self.context.versions.require_baseline(
            BASELINE_NAME,
            generation=baseline_generation,
            now=now,
        )
        low = baseline.value - RAMP_BAND_KPA
        high = baseline.value + RAMP_BAND_KPA
        if pressure_kpa < low or pressure_kpa > high:
            raise OverLimitError(
                "ramp target sits outside the calibrated band",
                pressure_kpa=pressure_kpa,
                baseline=baseline.value,
                band=RAMP_BAND_KPA,
            )
        self.context.thresholds.require("membrane_pressure", pressure_kpa)
        self.advance(UpgradePhase.PRESSURE_RAMP.value, "pressure ramp started")
        self.publish(
            RAMP_KIND,
            {
                "active": True,
                "pressure_kpa": pressure_kpa,
                "baseline_value": baseline.value,
                "baseline_generation": baseline.generation,
                "unit": baseline.unit,
            },
        )
        self.emit("mem.pressure_ramped", {"pressure_kpa": pressure_kpa})
        return self.status()

    def analyze(self, methane: float) -> dict[str, Any]:
        """Record a methane reading and alarm when it falls under the floor."""

        self.require("mem.analyze", required_phase=UpgradePhase.PRESSURE_RAMP.value)
        now = self.context.clock.now()
        window = rebuild_window(
            self.context.store.visible(),
            span_ticks=self.context.config.limits.quality_window_ticks,
            capacity=self.context.config.limits.quality_window_capacity,
        )
        snapshot = evaluate_methane(self.context.thresholds, window, methane, now)
        self.publish(QUALITY_KIND, {"active": True, **snapshot.describe()})
        if not snapshot.ok:
            self.raise_alarm("mem.quality.low", snapshot.describe())
        else:
            self.emit("mem.quality_read", snapshot.describe())
        return self.status()

    def status(self) -> dict[str, Any]:
        state = self.state()
        mem = state.get("mem", {})
        quality = mem.get("quality") if isinstance(mem, dict) else None
        analyzer = quality if isinstance(quality, dict) else None
        return compose_status(state, machine_phase=self.machine.phase, analyzer=analyzer)
