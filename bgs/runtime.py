"""Wiring, restart recovery and the command entry point."""

from __future__ import annotations

from typing import Any, Callable, Mapping

from .clock import ManualClock
from .compress.service import CompressService
from .config import RuntimeConfig
from .context import SharedContext
from .decision.batch import Batch, BatchRegistry
from .decision.query import RecordQuery, run_query
from .decision.stateview import StateView
from .decision.thresholds import ThresholdSet
from .desul.service import DesulService
from .digester.service import DigesterService
from .errors import NotFoundError, ValidationError
from .event.bus import Event, EventBus
from .event.topics import STORE
from .event.subscribers import AlarmCollector, AuditSubscriber
from .event.topics import ALARM
from .facts import latch_state
from .feed.service import FeedService
from .gas.service import GasService
from .heat.service import HeatService
from .ids import SequenceIds
from .interlocks import build_engine
from .mem.service import MemService
from .statemachine.gate import PreGate
from .statemachine.machine import SequenceMachine
from .stir.service import StirService
from .store.repository import RecordRepository, RestoreReport
from .vent.service import VentService
from .versioning.confirmation import Confirmation
from .versioning.expiry import Validity
from .versioning.facade import VersionedArtifacts

BOOT_KIND = "line.boot"
CLOCK_KIND = "store.clock"
BASELINE_KIND = "version.baseline"
CONFIRMATION_KIND = "version.confirmation"
GENERATION_SUBJECTS = {
    "stir.persisted": "stir",
    "desul.verified": "desul",
    "feed.batch": "feed",
}
LINES = ("feed", "upgrade", "vent", "gas")


def _text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if value is None or value == "":
        raise ValidationError("command is missing a required field", field=key)
    return str(value)


def _optional_text(payload: Mapping[str, Any], key: str, fallback: str) -> str:
    value = payload.get(key)
    if value is None or value == "":
        return fallback
    return str(value)


def _number(payload: Mapping[str, Any], key: str) -> float:
    value = payload.get(key)
    if value is None or value == "":
        raise ValidationError("command is missing a required field", field=key)
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("command field must be a number", field=key, value=str(value)) from exc


def _integer(payload: Mapping[str, Any], key: str) -> int:
    value = payload.get(key)
    if value is None or value == "":
        raise ValidationError("command is missing a required field", field=key)
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("command field must be an integer", field=key, value=str(value)) from exc


def _optional_integer(payload: Mapping[str, Any], key: str, fallback: int) -> int:
    value = payload.get(key)
    if value is None or value == "":
        return fallback
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("command field must be an integer", field=key, value=str(value)) from exc


class LineControlRuntime:
    """Owns every collaborator and exposes the command surface."""

    def __init__(self, config: RuntimeConfig | None = None) -> None:
        self.config = config or RuntimeConfig()
        self.clock = ManualClock()
        self.ids = SequenceIds()
        self.store = RecordRepository.open(self.config.data_dir, self.clock, self.ids)
        self.versions = VersionedArtifacts.fresh(self.ids)
        self.thresholds = ThresholdSet.from_limits(self.config.limits)
        self.view = StateView(self.store)
        self.batches = BatchRegistry()
        self.engine = build_engine()
        self.gate = PreGate(self.engine)
        self.bus = EventBus()
        self.audit = AuditSubscriber(self.store)
        self.alarms = AlarmCollector()
        self.machines = {line: SequenceMachine(line) for line in LINES}
        self.context = SharedContext(
            store=self.store,
            versions=self.versions,
            bus=self.bus,
            clock=self.clock,
            config=self.config,
            thresholds=self.thresholds,
            view=self.view,
            batches=self.batches,
            gate=self.gate,
            ids=self.ids,
        )
        self.stir = StirService(self.context, self.machines["feed"])
        self.feed = FeedService(self.context, self.machines["feed"])
        self.heat = HeatService(self.context, self.machines["feed"])
        self.digester = DigesterService(self.context, self.machines["feed"])
        self.desul = DesulService(self.context, self.machines["upgrade"])
        self.compress = CompressService(self.context, self.machines["upgrade"])
        self.mem = MemService(self.context, self.machines["upgrade"])
        self.vent = VentService(self.context, self.machines["vent"])
        self.gas = GasService(self.context, self.machines["gas"])
        self.boot_report: RestoreReport | None = None
        self._wire_bus()

    def _wire_bus(self) -> None:
        self.bus.subscribe(ALARM, self.alarms)
        self.bus.subscribe(ALARM, self.vent.on_alarm)
        self.bus.subscribe_all(self.audit)

    def bootstrap(self) -> dict[str, Any]:
        """Rebuild every derived artifact from the stored stream."""

        self._restore_clock()
        report = self.store.restore(self.clock.now())
        self.boot_report = report
        self._restore_id_counters()
        self._adopt_versions()
        self._hydrate_machines()
        self.store.publish(
            BOOT_KIND,
            "console",
            0,
            {
                "line": self.config.line_name,
                "replayed_records": report.replayed_records,
                "snapshot": report.used_snapshot_id,
                "rejected_snapshots": [dict(item) for item in report.rejected_snapshots],
            },
        )
        return report.describe()

    def _restore_clock(self) -> int:
        """Continue the tick at the last one the stream recorded."""

        peak = max((record.tick for record in self.store.visible()), default=0)
        if peak > self.clock.now():
            self.clock.advance(peak - self.clock.now())
        return peak

    def _restore_id_counters(self) -> None:
        """Raise the identifier counters so a restart cannot reuse an id."""

        confirmations = sum(1 for record in self.store.visible() if record.kind == CONFIRMATION_KIND)
        self.ids.restore("conf", confirmations)
        self.ids.restore("snap", len(self.store.snapshots.load_all()))

    def _adopt_versions(self) -> None:
        for record in self.store.visible():
            subject = GENERATION_SUBJECTS.get(record.kind)
            if subject is not None:
                self.versions.observe(subject, record.generation)
            if record.kind == "feed.batch":
                self.batches.adopt(
                    Batch(
                        batch_id=str(record.payload.get("batch_id")),
                        generation=record.generation,
                        tick=record.tick,
                        quantity=float(record.payload.get("quantity", 0.0)),
                        unit=str(record.payload.get("unit", "t")),
                    )
                )
            elif record.kind == BASELINE_KIND:
                payload = record.payload
                self.versions.adopt_baseline(
                    str(payload["name"]),
                    float(payload["value"]),
                    str(payload.get("unit", "")),
                    int(payload["generation"]),
                    validity=Validity.of(int(payload["issued_tick"]), int(payload["ttl_ticks"])),
                )
            elif record.kind == CONFIRMATION_KIND:
                payload = record.payload
                self.versions.confirmations.record(
                    Confirmation(
                        confirmation_id=str(payload["confirmation_id"]),
                        subject=str(payload["subject"]),
                        generation=int(payload["generation"]),
                        issuer=str(payload["issuer"]),
                        validity=Validity.of(int(payload["issued_tick"]), int(payload["ttl_ticks"])),
                    )
                )

    def _hydrate_machines(self) -> None:
        for line, machine in self.machines.items():
            record = self.view.latest(f"{line}.phase")
            if record is None:
                continue
            payload = record.payload
            machine.hydrate(str(payload["phase"]), step=int(payload["step"]), tick=record.tick)

    def health(self) -> dict[str, Any]:
        """Return the values a health probe needs."""

        state = self.store.state()
        return {
            "status": "ok",
            "line": self.config.line_name,
            "tick": self.clock.now(),
            "watermark": self.store.watermark().describe(),
            "records": self.store.last_seq(),
            "visible": len(self.store.visible()),
            "batches": self.batches.count(),
            "alarms": self.alarms.count(),
            "latched": {
                "vent": latch_state(state, "vent"),
                "digester": latch_state(state, "digester"),
            },
        }

    def state(self) -> dict[str, Any]:
        """Return the full console snapshot."""

        now = self.clock.now()
        return {
            "line": self.config.line_name,
            "tick": now,
            "watermark": self.store.watermark().describe(),
            "subsystems": {
                "stir": self.stir.status(),
                "feed": self.feed.status(),
                "heat": self.heat.status(),
                "digester": self.digester.status(),
                "desul": self.desul.status(),
                "compress": self.compress.status(),
                "mem": self.mem.status(),
                "vent": self.vent.status(),
                "gas": self.gas.status(),
            },
            "lines": {
                line: {"phase": machine.phase, "sequence": machine.order(), "next": machine.next_phase()}
                for line, machine in self.machines.items()
            },
            "versioned": self.versions.describe(now),
            "thresholds": self.thresholds.describe(),
            "interlocks": {
                "actions": list(self.engine.actions()),
                "rules": [rule.describe() for rule in self.engine.rules()],
            },
            "batches": [batch.describe() for batch in self.batches.all()],
            "alarms": self.alarms.recent(),
            "facts": self.view.facts(),
            "config": dict(self.config.describe()),
        }

    def records(self, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Run the audit query the caller asked for."""

        params = params or {}
        query = RecordQuery(
            kinds=_split(params.get("kind")),
            origins=_split(params.get("origin")),
            seq_from=_maybe_int(params.get("seq_from")),
            seq_to=_maybe_int(params.get("seq_to")),
            tick_from=_maybe_int(params.get("tick_from")),
            tick_to=_maybe_int(params.get("tick_to")),
            include_tombstones=_maybe_flag(params.get("include_tombstones")),
            limit=_maybe_int(params.get("limit")),
        )
        return run_query(self.store.committed_records(), query).describe()

    def history(self, tick: int) -> dict[str, Any]:
        """Compare the current state with the state at ``tick``."""

        if tick < 0:
            raise ValidationError("tick must not be negative", tick=tick)
        return {
            "tick": tick,
            "now": self.clock.now(),
            "state": self.view.as_of(tick),
            "delta": self.view.delta(tick).describe(),
        }

    def publish_baseline(
        self,
        name: str,
        value: float,
        unit: str,
        *,
        ttl_ticks: int | None = None,
    ) -> dict[str, Any]:
        """Publish a calibration value under a fresh generation."""

        ttl = self.config.defaults.baseline_ttl_ticks if ttl_ticks is None else ttl_ticks
        baseline = self.versions.publish_baseline(name, value, unit, tick=self.clock.now(), ttl_ticks=ttl)
        record = self.store.publish(
            BASELINE_KIND,
            "console",
            baseline.generation,
            {
                "active": True,
                "name": baseline.name,
                "value": baseline.value,
                "unit": baseline.unit,
                "generation": baseline.generation,
                "issued_tick": baseline.issued_tick,
                "ttl_ticks": ttl,
            },
        )
        self.bus.publish(
            Event(
                topic=STORE,
                name="version.baseline_published",
                origin="console",
                tick=self.clock.now(),
                payload={"name": name, "generation": baseline.generation},
            )
        )
        return {"baseline": baseline.describe(self.clock.now()), "seq": record.seq}

    def take_snapshot(self, *, ttl_ticks: int | None = None) -> dict[str, Any]:
        """Materialise the committed state."""

        ttl = self.config.defaults.snapshot_ttl_ticks if ttl_ticks is None else ttl_ticks
        token = self.versions.bump("snapshot", tick=self.clock.now())
        snapshot = self.store.snapshot(
            generation=token.value,
            validity=Validity.of(self.clock.now(), ttl),
        )
        return {"snapshot": snapshot.describe(self.clock.now())}

    def rollback(self, seq: int, *, reason: str = "operator rollback") -> dict[str, Any]:
        """Tombstone every committed record after ``seq``."""

        records = self.store.rollback_after(seq, reason=reason, origin="console", generation=0)
        return {
            "tombstones": [
                {"seq": record.seq, "tombstone_of": record.tombstone_of} for record in records
            ],
            "watermark": self.store.watermark().describe(),
        }

    def commands(self) -> dict[str, Callable[[Mapping[str, Any]], Any]]:
        """Return the command surface the console exposes."""

        return {
            "stir.start": lambda payload: self.stir.start(
                target=_optional_text(payload, "target", "primary")
            ),
            "stir.stop": lambda payload: self.stir.stop(),
            "stir.homogenize": lambda payload: self.stir.homogenize(_number(payload, "level")),
            "stir.persist": lambda payload: self.stir.persist(),
            "feed.batch": lambda payload: self.feed.declare_batch(
                _text(payload, "batch_id"), _number(payload, "quantity")
            ),
            "feed.start": lambda payload: self.feed.start(),
            "feed.close": lambda payload: self.feed.close(),
            "heat.ramp": lambda payload: self.heat.ramp(_number(payload, "target_c")),
            "heat.cool": lambda payload: self.heat.cool(),
            "digester.pressure": lambda payload: self.digester.observe_pressure(_number(payload, "kpa")),
            "digester.zone": lambda payload: self.digester.set_zone(
                _text(payload, "zone"), _number(payload, "temperature_c")
            ),
            "digester.sensor": lambda payload: self.digester.map_sensor(
                _text(payload, "sensor_id"), _text(payload, "zone"), _text(payload, "kind")
            ),
            "desul.check": lambda payload: self.desul.check(_number(payload, "sulfur_ppm")),
            "compress.start": lambda payload: self.compress.start(),
            "compress.stop": lambda payload: self.compress.stop(),
            "mem.valve_open": lambda payload: self.mem.open_valve(
                reason=_optional_text(payload, "reason", "operator request")
            ),
            "mem.valve_close": lambda payload: self.mem.close_valve(
                reason=_optional_text(payload, "reason", "operator request")
            ),
            "mem.ramp": lambda payload: self.mem.press_ramp(
                _number(payload, "pressure_kpa"),
                baseline_generation=_integer(payload, "baseline_generation"),
            ),
            "mem.analyze": lambda payload: self.mem.analyze(_number(payload, "methane")),
            "vent.flare": lambda payload: self.vent.flare(
                reason=_optional_text(payload, "reason", "quality latch")
            ),
            "vent.recover": lambda payload: self.vent.recover(),
            "gas.inlet_open": lambda payload: self.gas.open_inlet(),
            "gas.inlet_close": lambda payload: self.gas.close_inlet(),
            "gas.store": lambda payload: self.gas.store_gas(
                _number(payload, "volume_m3"), _number(payload, "pressure_kpa")
            ),
            "baseline.publish": lambda payload: self.publish_baseline(
                _text(payload, "name"),
                _number(payload, "value"),
                _optional_text(payload, "unit", ""),
                ttl_ticks=_optional_integer(
                    payload, "ttl_ticks", self.config.defaults.baseline_ttl_ticks
                ),
            ),
            "snapshot.take": lambda payload: self.take_snapshot(
                ttl_ticks=_optional_integer(
                    payload, "ttl_ticks", self.config.defaults.snapshot_ttl_ticks
                )
            ),
            "store.rollback": lambda payload: self.rollback(
                _integer(payload, "seq"), reason=_optional_text(payload, "reason", "operator rollback")
            ),
            "clock.advance": lambda payload: {"tick": self.advance_ticks(_integer(payload, "ticks"))},
        }

    def dispatch(self, command: str, payload: Mapping[str, Any] | None = None) -> dict[str, Any]:
        """Run one command and return everything the caller needs."""

        handler = self.commands().get(command)
        if handler is None:
            raise NotFoundError("unknown command", command=command)
        body = payload or {}
        result = handler(body)
        return {
            "command": command,
            "tick": self.clock.now(),
            "result": result,
            "watermark": self.store.watermark().describe(),
            "alarms": self.alarms.count(),
        }

    def advance_ticks(self, ticks: int = 1) -> int:
        """Move the deterministic clock forward and record where it went."""

        moved = self.clock.advance(ticks)
        self.store.publish(CLOCK_KIND, "console", 0, {"active": True, "tick": moved})
        return moved

    def close(self) -> None:
        self.store.close()


def _split(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    text = str(value).strip()
    if not text:
        return ()
    return tuple(part for part in (item.strip() for item in text.split(",")) if part)


def _maybe_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValidationError("query field must be an integer", value=str(value)) from exc


def _maybe_flag(value: Any) -> bool:
    if value is None or value == "":
        return False
    text = str(value).strip().lower()
    if text in ("1", "true", "yes", "on"):
        return True
    if text in ("0", "false", "no", "off"):
        return False
    raise ValidationError("query field must be a boolean", value=str(value))
