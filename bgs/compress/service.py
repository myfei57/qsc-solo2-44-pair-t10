"""Compressor service."""

from __future__ import annotations

from typing import Any

from ..service_base import LineService
from ..statemachine.phases import UpgradePhase
from .start import prepare_start
from .status import compose_status

RUNNING_KIND = "compress.running"


class CompressService(LineService):
    """Runs the compressor once the outlet verification is still usable."""

    origin = "compress"
    line = "upgrade"

    def start(self) -> dict[str, Any]:
        """Start the compressor."""

        self.require("compress.start", required_phase=UpgradePhase.DESUL_VERIFIED.value)
        prepared = prepare_start(self.context.versions, now=self.context.clock.now())
        self.advance(UpgradePhase.COMPRESSING.value, "compressor started")
        self.publish(RUNNING_KIND, {"active": True, **prepared.describe()})
        self.emit("compress.started", prepared.describe())
        return self.status()

    def stop(self) -> dict[str, Any]:
        """Stop the compressor."""

        self.require("compress.stop")
        self.publish(RUNNING_KIND, {"active": False})
        self.emit("compress.stopped")
        return self.status()

    def status(self) -> dict[str, Any]:
        return compose_status(self.state(), machine_phase=self.machine.phase)
