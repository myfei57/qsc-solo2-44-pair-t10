"""Mixer service."""

from __future__ import annotations

from typing import Any

from ..errors import BelowLimitError, NotFoundError
from ..service_base import LineService
from .mix import level_reading, normalize_level
from .persist import PersistOutcome, build_payload
from .status import compose_status

PERSISTED_KIND = "stir.persisted"
MIXER_KIND = "stir.mixer"
MIX_KIND = "stir.mix"


class StirService(LineService):
    """Starts the mixer, records the mix and makes it durable."""

    origin = "stir"
    line = "feed"
    subject = "stir"

    def start(self, *, target: str = "primary") -> dict[str, Any]:
        """Start the mixer."""

        if not target:
            raise NotFoundError("mixer target must be named")
        self.require_order(not self._mixer_active(), "mixer is already running", target=target)
        self.publish(MIXER_KIND, {"active": True, "target": target})
        self.emit("stir.started", {"target": target})
        return self.status()

    def stop(self) -> dict[str, Any]:
        """Stop the mixer, which feeding forbids."""

        self.require("stir.stop")
        self.publish(MIXER_KIND, {"active": False, "target": self._mixer_target()})
        self.emit("stir.stopped")
        return self.status()

    def homogenize(self, level: float) -> dict[str, Any]:
        """Record a homogenisation level and refuse one under the floor."""

        self.require("stir.homogenize")
        normalised = normalize_level(level)
        reading = level_reading(self.context.thresholds, normalised, self.context.clock.now())
        if not reading.ok:
            raise BelowLimitError(
                "homogenisation level is under the configured floor",
                level=normalised,
                code=reading.code,
            )
        self.publish(MIX_KIND, {"active": True, **reading.describe()})
        self.emit("stir.homogenized", {"level": normalised})
        return self.status()

    def persist(self) -> dict[str, Any]:
        """Write the mixer state durably so feeding may start."""

        self.require("stir.persist")
        mixed = self._mix_record()
        token = self.context.versions.bump(self.subject, tick=self.context.clock.now())
        record = self.publish(
            PERSISTED_KIND,
            build_payload(float(mixed["level"]), token.value, self.context.clock.now()),
        )
        outcome = PersistOutcome(
            generation=token.value,
            mix_level=float(mixed["level"]),
            tick=self.context.clock.now(),
            seq=record.seq,
        )
        self.emit("stir.persisted", outcome.describe())
        return {"outcome": outcome.describe(), "status": self.status()}

    def status(self) -> dict[str, Any]:
        return compose_status(
            self.state(),
            now=self.context.clock.now(),
            thresholds=self.context.thresholds,
        )

    def history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the newest mixer records."""

        records = [*self.context.view.history(MIXER_KIND), *self.context.view.history(PERSISTED_KIND)]
        return [
            {
                "seq": record.seq,
                "kind": record.kind,
                "generation": record.generation,
                "tick": record.tick,
                "payload": dict(record.payload),
            }
            for record in records[-limit:]
        ]

    def _mixer_active(self) -> bool:
        mixer = self.state().get("stir", {})
        entry = mixer.get("mixer") if isinstance(mixer, dict) else None
        return bool(entry.get("active", False)) if isinstance(entry, dict) else False

    def _mixer_target(self) -> str | None:
        mixer = self.state().get("stir", {})
        entry = mixer.get("mixer") if isinstance(mixer, dict) else None
        return entry.get("target") if isinstance(entry, dict) else None

    def _mix_record(self) -> dict[str, Any]:
        mixed = self.state().get("stir", {})
        entry = mixed.get("mix") if isinstance(mixed, dict) else None
        if not isinstance(entry, dict):
            raise NotFoundError("mixer state was never recorded", kind=MIX_KIND)
        return entry
