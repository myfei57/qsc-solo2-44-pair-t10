"""HTTP console and its pages."""

from __future__ import annotations

from .handlers import COMMAND_ROUTES, build_router
from .pages import PageStore
from .render import encode_json, inject_snapshot
from .router import Request, Response, Route, Router
from .server import ConsoleServer

__all__ = [
    "COMMAND_ROUTES",
    "ConsoleServer",
    "PageStore",
    "Request",
    "Response",
    "Route",
    "Router",
    "build_router",
    "encode_json",
    "inject_snapshot",
]
