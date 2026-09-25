"""Feed service."""

from __future__ import annotations

from typing import Any

from ..facts import FEED_BATCH_DECLARED
from ..service_base import LineService
from ..statemachine.phases import FeedPhase
from .batch import plan_cycle
from .history import BATCH_KIND, OPEN_KIND, batch_timeline

FERMENT_KIND = "feed.ferment"


class FeedService(LineService):
    """Declares batches and opens the feed gate only after a durable mix."""

    origin = "feed"
    line = "feed"
    subject = "feed"

    def facts(self, **extra: bool) -> dict[str, bool]:
        base = super().facts(**extra)
        base[FEED_BATCH_DECLARED] = self.context.view.latest(BATCH_KIND) is not None
        return base

    def declare_batch(self, batch_id: str, quantity: float) -> dict[str, Any]:
        """Declare the batch that will be fed, once the mix is durable."""

        self.require("feed.batch")
        plan = plan_cycle(batch_id, quantity, self.context.config.limits)
        token = self.context.versions.bump(self.subject, tick=self.context.clock.now())
        batch = self.context.batches.declare(
            plan.batch_id,
            tick=self.context.clock.now(),
            generation=token.value,
            quantity=plan.quantity,
            unit=plan.unit,
        )
        self.publish(
            BATCH_KIND,
            {
                "active": True,
                "batch_id": batch.batch_id,
                "quantity": batch.quantity,
                "unit": batch.unit,
                "generation": batch.generation,
            },
        )
        if self.machine.is_at(FeedPhase.IDLE.value):
            self.advance(FeedPhase.STIR_CONFIRMED.value, "batch declared against a durable mix")
        self.emit("feed.batch_declared", batch.describe())
        return {"batch": batch.describe(), "status": self.status()}

    def start(self) -> dict[str, Any]:
        """Open the feed gate."""

        self.require("feed.start", required_phase=FeedPhase.STIR_CONFIRMED.value)
        batch = self.context.view.latest(BATCH_KIND)
        self.advance(FeedPhase.FEEDING.value, "feed gate opened")
        self.publish(
            OPEN_KIND,
            {
                "active": True,
                "batch_id": batch.payload.get("batch_id") if batch is not None else None,
            },
        )
        self.emit("feed.opened")
        return self.status()

    def close(self) -> dict[str, Any]:
        """Close the feed gate and hand the batch to fermentation."""

        self.require("feed.close", required_phase=FeedPhase.FEEDING.value)
        batch = self.context.view.latest(BATCH_KIND)
        self.advance(FeedPhase.FERMENTING.value, "feed gate closed")
        self.publish(OPEN_KIND, {"active": False})
        self.publish(
            FERMENT_KIND,
            {
                "active": True,
                "batch_id": batch.payload.get("batch_id") if batch is not None else None,
            },
        )
        self.emit("feed.closed")
        return self.status()

    def status(self) -> dict[str, Any]:
        state = self.state()
        feed = state.get("feed", {})
        opened = feed.get("open") if isinstance(feed, dict) else None
        return {
            "phase": self.machine.phase,
            "phase_index": self.machine.index,
            "sequence": self.machine.order(),
            "next_phase": self.machine.next_phase(),
            "open": bool(opened.get("active", False)) if isinstance(opened, dict) else False,
            "batch": (self.context.view.latest(BATCH_KIND).payload.get("batch_id") if self.context.view.latest(BATCH_KIND) else None),
            "batches": self.context.batches.count(),
        }

    def timeline(self, limit: int = 20) -> list[dict[str, Any]]:
        """Return the feed timeline."""

        return batch_timeline(self.context.store.visible())[-limit:]
