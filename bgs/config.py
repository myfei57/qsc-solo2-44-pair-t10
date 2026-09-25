"""Runtime configuration values shared by the services."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True, slots=True)
class Limits:
    """Process bounds used by the decision layer."""

    methane_min_percent: float = 96.0
    sulfur_max_ppm: float = 12.0
    vessel_pressure_max_kpa: float = 18.0
    membrane_pressure_max_kpa: float = 1600.0
    storage_pressure_max_kpa: float = 24.0
    wall_temp_max_c: float = 42.0
    mix_level_min: float = 0.80
    quality_window_ticks: int = 4
    quality_window_capacity: int = 4
    feed_cycle_max_tons: float = 40.0

    def as_mapping(self) -> dict[str, float]:
        return {
            "methane_min_percent": self.methane_min_percent,
            "sulfur_max_ppm": self.sulfur_max_ppm,
            "vessel_pressure_max_kpa": self.vessel_pressure_max_kpa,
            "membrane_pressure_max_kpa": self.membrane_pressure_max_kpa,
            "storage_pressure_max_kpa": self.storage_pressure_max_kpa,
            "wall_temp_max_c": self.wall_temp_max_c,
            "mix_level_min": self.mix_level_min,
        }


@dataclass(frozen=True, slots=True)
class ValidityDefaults:
    """Default validity windows, expressed in ticks."""

    snapshot_ttl_ticks: int = 64
    confirmation_ttl_ticks: int = 12
    baseline_ttl_ticks: int = 24


@dataclass(frozen=True, slots=True)
class RuntimeConfig:
    """Everything the runtime needs to boot."""

    data_dir: Path = Path("data")
    host: str = "127.0.0.1"
    port: int = 8080
    web_dir: Path = Path("web")
    limits: Limits = field(default_factory=Limits)
    defaults: ValidityDefaults = field(default_factory=ValidityDefaults)
    line_name: str = "line-a"

    def with_overrides(self, **changes: Any) -> "RuntimeConfig":
        """Return a copy with ``changes`` applied."""

        return replace(self, **changes)

    def describe(self) -> Mapping[str, Any]:
        return {
            "line": self.line_name,
            "host": self.host,
            "port": self.port,
            "data_dir": str(self.data_dir),
            "limits": self.limits.as_mapping(),
        }
