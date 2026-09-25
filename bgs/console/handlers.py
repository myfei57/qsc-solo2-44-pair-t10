"""Route table for the console."""

from __future__ import annotations

from typing import Any, Mapping

from ..errors import ValidationError
from ..runtime import LineControlRuntime
from .pages import PageStore
from .render import inject_snapshot
from .router import Request, Response, Router

COMMAND_ROUTES: tuple[tuple[str, str, str], ...] = (
    ("POST", "/api/stir/start", "stir.start"),
    ("POST", "/api/stir/stop", "stir.stop"),
    ("POST", "/api/stir/homogenize", "stir.homogenize"),
    ("POST", "/api/stir/persist", "stir.persist"),
    ("POST", "/api/feed/batch", "feed.batch"),
    ("POST", "/api/feed/start", "feed.start"),
    ("POST", "/api/feed/close", "feed.close"),
    ("POST", "/api/heater/ramp", "heat.ramp"),
    ("POST", "/api/heater/cool", "heat.cool"),
    ("POST", "/api/digester/pressure", "digester.pressure"),
    ("POST", "/api/digester/zone", "digester.zone"),
    ("POST", "/api/digester/sensor", "digester.sensor"),
    ("POST", "/api/desul/check", "desul.check"),
    ("POST", "/api/compress/start", "compress.start"),
    ("POST", "/api/compress/stop", "compress.stop"),
    ("POST", "/api/mem/valve", "mem.valve_open"),
    ("POST", "/api/mem/valve/close", "mem.valve_close"),
    ("POST", "/api/mem/press", "mem.ramp"),
    ("POST", "/api/mem/analyze", "mem.analyze"),
    ("POST", "/api/vent/flare", "vent.flare"),
    ("POST", "/api/vent/recover", "vent.recover"),
    ("POST", "/api/gas/inlet", "gas.inlet_open"),
    ("POST", "/api/gas/inlet/close", "gas.inlet_close"),
    ("POST", "/api/gas/store", "gas.store"),
    ("POST", "/api/baseline", "baseline.publish"),
    ("POST", "/api/snapshot", "snapshot.take"),
    ("POST", "/api/rollback", "store.rollback"),
    ("POST", "/api/clock/advance", "clock.advance"),
)


def build_router(runtime: LineControlRuntime, pages: PageStore) -> Router:
    """Build the console router for ``runtime``."""

    router = Router()
    _add_pages(router, runtime, pages)
    _add_reads(router, runtime)
    _add_commands(router, runtime)
    return router


def _add_pages(router: Router, runtime: LineControlRuntime, pages: PageStore) -> None:
    def overview(_: Request) -> Response:
        return Response.html(inject_snapshot(pages.load("overview"), runtime.state()))

    def operations(_: Request) -> Response:
        return Response.html(inject_snapshot(pages.load("operations"), runtime.state()))

    def records(_: Request) -> Response:
        return Response.html(inject_snapshot(pages.load("records"), runtime.records({"limit": "50"})))

    router.add("GET", "/", overview)
    router.add("GET", "/operations", operations)
    router.add("GET", "/records", records)


def _add_reads(router: Router, runtime: LineControlRuntime) -> None:
    router.add("GET", "/api/health", lambda _: Response.json(runtime.health()))
    router.add("GET", "/api/state", lambda _: Response.json(runtime.state()))
    router.add("GET", "/api/alarms", lambda _: Response.json({"alarms": runtime.alarms.recent()}))
    router.add("GET", "/api/records", lambda request: Response.json(runtime.records(dict(request.query))))
    router.add("GET", "/api/feed/timeline", lambda _: Response.json({"timeline": runtime.feed.timeline()}))

    def history(request: Request) -> Response:
        raw = request.require_field("tick")
        try:
            tick = int(raw)
        except (TypeError, ValueError) as exc:
            raise ValidationError("tick must be an integer", tick=str(raw)) from exc
        return Response.json(runtime.history(tick))

    router.add("GET", "/api/history", history)


def _add_commands(router: Router, runtime: LineControlRuntime) -> None:
    for method, path, command in COMMAND_ROUTES:
        router.add(method, path, _command_handler(runtime, command))


def _command_handler(runtime: LineControlRuntime, command: str) -> Any:
    def handler(request: Request) -> Response:
        payload: Mapping[str, Any] = dict(request.body)
        return Response.json(runtime.dispatch(command, payload))

    return handler
