"""Desulphurisation outlet verification."""

from __future__ import annotations

from .check import OutletReading, evaluate_outlet
from .service import DesulService
from .status import compose_status

__all__ = ["DesulService", "OutletReading", "compose_status", "evaluate_outlet"]
