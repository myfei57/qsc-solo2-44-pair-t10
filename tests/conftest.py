"""Shared fixtures for the line control test suite."""

from __future__ import annotations

import http.client
import json
from pathlib import Path
from typing import Any, Callable, Iterator

import pytest

from bgs.clock import ManualClock
from bgs.config import RuntimeConfig
from bgs.console.server import ConsoleServer
from bgs.ids import SequenceIds
from bgs.runtime import LineControlRuntime
from bgs.store.repository import RecordRepository

REPO_ROOT = Path(__file__).resolve().parents[1]
WEB_DIR = REPO_ROOT / "web"


class ConsoleClient:
    """Tiny http client used by the console tests."""

    def __init__(self, server: ConsoleServer) -> None:
        self._server = server

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
        connection = http.client.HTTPConnection(self._server.host, self._server.port, timeout=10)
        payload = None if body is None else json.dumps(body)
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        connection.request(method, path, payload, headers)
        response = connection.getresponse()
        text = response.read().decode("utf-8")
        status = response.status
        connection.close()
        try:
            parsed: Any = json.loads(text)
        except json.JSONDecodeError:
            parsed = text
        return status, parsed

    def get(self, path: str) -> tuple[int, Any]:
        return self.request("GET", path)

    def post(self, path: str, body: dict[str, Any] | None = None) -> tuple[int, Any]:
        return self.request("POST", path, body or {})


@pytest.fixture
def config(tmp_path: Path) -> RuntimeConfig:
    """A runtime configuration that writes into the test's temporary directory."""

    return RuntimeConfig(data_dir=tmp_path / "data", web_dir=WEB_DIR, line_name="line-test")


@pytest.fixture
def boot(config: RuntimeConfig) -> Iterator[Callable[[], LineControlRuntime]]:
    """Open runtimes against the same data directory and close them all."""

    opened: list[LineControlRuntime] = []

    def _boot() -> LineControlRuntime:
        runtime = LineControlRuntime(config)
        runtime.bootstrap()
        opened.append(runtime)
        return runtime

    yield _boot
    for runtime in opened:
        runtime.close()


@pytest.fixture
def runtime(boot: Callable[[], LineControlRuntime]) -> LineControlRuntime:
    return boot()


@pytest.fixture
def console(runtime: LineControlRuntime) -> Iterator[ConsoleClient]:
    server = ConsoleServer(runtime, port=0)
    server.start_background()
    try:
        yield ConsoleClient(server)
    finally:
        server.stop()


@pytest.fixture
def repo_factory(tmp_path: Path) -> Callable[..., tuple[RecordRepository, ManualClock, SequenceIds]]:
    """Build an on-disk repository for the store level tests."""

    def _make(
        data_dir: Path | None = None,
        clock: ManualClock | None = None,
        ids: SequenceIds | None = None,
    ) -> tuple[RecordRepository, ManualClock, SequenceIds]:
        resolved_clock = clock or ManualClock()
        resolved_ids = ids or SequenceIds()
        target = data_dir or (tmp_path / "store")
        return RecordRepository.open(target, resolved_clock, resolved_ids), resolved_clock, resolved_ids

    return _make


@pytest.fixture
def prime(runtime: LineControlRuntime) -> Callable[..., None]:
    """Run the line up to an open product valve."""

    def _prime(*, quantity: float = 10.0) -> None:
        runtime.dispatch("stir.start", {})
        runtime.dispatch("stir.homogenize", {"level": 0.9})
        runtime.dispatch("stir.persist", {})
        runtime.dispatch("feed.batch", {"batch_id": "B-1", "quantity": quantity})
        runtime.dispatch("feed.start", {})
        runtime.dispatch("heat.ramp", {"target_c": 36})
        runtime.dispatch("desul.check", {"sulfur_ppm": 6})
        runtime.dispatch("compress.start", {})
        runtime.dispatch("mem.valve_open", {})

    return _prime


@pytest.fixture
def compressing(runtime: LineControlRuntime) -> Callable[..., None]:
    """Run the line up to a running compressor."""

    def _compressing(*, quantity: float = 10.0) -> None:
        runtime.dispatch("stir.start", {})
        runtime.dispatch("stir.homogenize", {"level": 0.9})
        runtime.dispatch("stir.persist", {})
        runtime.dispatch("feed.batch", {"batch_id": "B-1", "quantity": quantity})
        runtime.dispatch("feed.start", {})
        runtime.dispatch("desul.check", {"sulfur_ppm": 6.0})
        runtime.dispatch("compress.start", {})

    return _compressing


@pytest.fixture
def drive(runtime: LineControlRuntime, prime: Callable[..., None]) -> Callable[..., None]:
    """Bring the line up to a pressurised membrane with gas stored."""

    def _drive(*, methane: float = 97.0, quantity: float = 10.0, inlet: bool = True) -> None:
        prime(quantity=quantity)
        runtime.dispatch(
            "baseline.publish",
            {"name": "membrane_pressure", "value": 1500, "unit": "kPa"},
        )
        generation = runtime.versions.current_generation("membrane_pressure")
        runtime.dispatch("mem.ramp", {"pressure_kpa": 1500, "baseline_generation": generation})
        runtime.dispatch("mem.analyze", {"methane": methane})
        if inlet:
            runtime.dispatch("gas.inlet_open", {})

    return _drive
