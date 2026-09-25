"""Desulphurisation service."""

from __future__ import annotations

from typing import Any

from ..errors import OverLimitError
from ..service_base import LineService
from ..statemachine.phases import UpgradePhase
from .check import evaluate_outlet
from .status import OUTLET_KIND, SUBJECT, VERIFIED_KIND, compose_status

CONFIRMATION_KIND = "version.confirmation"


class DesulService(LineService):
    """Verifies the outlet before the compressor may run."""

    origin = "desul"
    line = "upgrade"
    subject = SUBJECT

    def check(self, sulfur_ppm: float) -> dict[str, Any]:
        """Measure the outlet and, when it passes, sign it off."""

        self.require("desul.check")
        now = self.context.clock.now()
        reading = evaluate_outlet(self.context.thresholds, sulfur_ppm, now)
        self.publish(OUTLET_KIND, {"active": True, **reading.describe()})
        if not reading.ok:
            self.raise_alarm("desul.outlet_high", reading.describe())
            raise OverLimitError(
                "outlet sulphur content is above its ceiling",
                sulfur_ppm=sulfur_ppm,
                limit=reading.limit,
            )
        token = self.context.versions.bump(self.subject, tick=now)
        self.publish(VERIFIED_KIND, {"active": True, "sulfur_ppm": sulfur_ppm, "generation": token.value})
        confirmation = self.context.versions.confirm(
            self.subject,
            tick=now,
            ttl_ticks=self.context.config.defaults.confirmation_ttl_ticks,
            issuer=self.origin,
        )
        self.publish(
            CONFIRMATION_KIND,
            {
                "confirmation_id": confirmation.confirmation_id,
                "subject": confirmation.subject,
                "generation": confirmation.generation,
                "issuer": confirmation.issuer,
                "issued_tick": confirmation.issued_tick,
                "ttl_ticks": confirmation.validity.ttl_ticks,
                "active": True,
            },
        )
        if self.machine.is_at(UpgradePhase.IDLE.value):
            self.advance(UpgradePhase.DESUL_VERIFIED.value, "outlet verified")
        self.emit("desul.verified", confirmation.describe(now))
        return self.status()

    def status(self) -> dict[str, Any]:
        return compose_status(self.state(), versions=self.context.versions, now=self.context.clock.now())
