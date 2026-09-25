"""Flare line service."""

from __future__ import annotations

from typing import Any

from ..errors import InterlockBlockedError
from ..event.bus import Event
from ..facts import latch_state
from ..mem.analyzer import QUALITY_KIND, rebuild_window
from ..service_base import LineService
from ..statemachine.latch import Latch
from ..statemachine.phases import VentPhase
from .flare import flare_payload, plan_flare
from .recovery import recovery_ready

LATCH_KIND = "vent.latch"
CLEAR_KIND = "vent.clear"
FLARE_KIND = "vent.flare"
QUALITY_ALARM = "mem.quality.low"


class VentService(LineService):
    """Raises the quality latch on a low reading and releases it after recovery."""

    origin = "vent"
    line = "vent"

    def __init__(self, context, machine=None) -> None:
        super().__init__(context, machine)
        self._latch = Latch("quality")

    def on_alarm(self, event: Event) -> None:
        """Bus handler: latch the line when the analyser reports low quality."""

        if event.name != QUALITY_ALARM:
            return
        self._sync_latch()
        if self._latch.latched:
            return
        now = self.context.clock.now()
        if self.machine.is_at(VentPhase.RECOVERED.value):
            self.rewind(VentPhase.QUALITY_ALARM.value, "quality dropped again")
        elif self.machine.is_at(VentPhase.NORMAL.value):
            self.advance(VentPhase.QUALITY_ALARM.value, "quality dropped under the floor")
        latched = self._latch.set(tick=now, reason="methane below the floor")
        self.publish(LATCH_KIND, {"active": True, "step": latched.step, "reason": latched.reason})
        self.emit("vent.latched", {"step": latched.step})

    def flare(self, *, reason: str = "quality latch") -> dict[str, Any]:
        """Open the flare while the quality latch is set."""

        self.require("vent.flare", required_phase=VentPhase.QUALITY_ALARM.value)
        plan = plan_flare(reason)
        self.advance(VentPhase.FLARING.value, "flare opened")
        self.publish(FLARE_KIND, flare_payload(plan, tick=self.context.clock.now(), open_state=True))
        self.emit("vent.flaring", plan.describe())
        return self.status()

    def recover(self) -> dict[str, Any]:
        """Release the quality latch once a full window sits above the floor."""

        self.require("vent.recover", required_phase=VentPhase.FLARING.value)
        self._sync_latch()
        window = rebuild_window(
            self.context.store.visible(),
            span_ticks=self.context.config.limits.quality_window_ticks,
            capacity=self.context.config.limits.quality_window_capacity,
            kind=QUALITY_KIND,
        )
        check = recovery_ready(window, floor=self.context.config.limits.methane_min_percent)
        if not check.ready:
            raise InterlockBlockedError("quality window does not allow the latch to clear", **check.describe())
        event = self._latch.clear(tick=self.context.clock.now(), reason=check.reason)
        self.advance(VentPhase.RECOVERED.value, "quality recovered")
        self.publish(CLEAR_KIND, {"active": False, "step": event.step, "reason": event.reason})
        self.emit("vent.recovered", check.describe())
        return self.status()

    def status(self) -> dict[str, Any]:
        state = self.state()
        self._sync_latch()
        vent = state.get("vent", {})
        flare = vent.get("flare") if isinstance(vent, dict) else None
        window = rebuild_window(
            self.context.store.visible(),
            span_ticks=self.context.config.limits.quality_window_ticks,
            capacity=self.context.config.limits.quality_window_capacity,
        )
        return {
            "phase": self.machine.phase,
            "sequence": self.machine.order(),
            "latched": latch_state(state, "vent"),
            "latch": self._latch.describe(),
            "flaring": bool(flare.get("active", False)) if isinstance(flare, dict) else False,
            "quality": window.describe(),
            "recovery": recovery_ready(window, floor=self.context.config.limits.methane_min_percent).describe(),
        }

    def _sync_latch(self) -> None:
        state = self.state()
        vent = state.get("vent", {})
        latch = vent.get("latch") if isinstance(vent, dict) else None
        cleared = vent.get("clear") if isinstance(vent, dict) else None
        step = max(
            int(latch.get("step", 0)) if isinstance(latch, dict) else 0,
            int(cleared.get("step", 0)) if isinstance(cleared, dict) else 0,
        )
        self._latch.sync(latched=latch_state(state, "vent"), step=step, reason="synced")
