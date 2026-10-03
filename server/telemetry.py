from __future__ import annotations

import os
import random
from typing import Any


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        return default


class TelemetryGenerator:
    """Produces naturally fluctuating telemetry readings within configured ranges."""

    def __init__(self) -> None:
        self.temp_range = (_env_float("TEMP_MIN", 55), _env_float("TEMP_MAX", 75))
        self.power_range = (_env_float("POWER_MIN", 300), _env_float("POWER_MAX", 500))
        self.cpu_range = (_env_float("CPU_MIN", 20), _env_float("CPU_MAX", 90))
        self.memory_range = (_env_float("MEMORY_MIN", 30), _env_float("MEMORY_MAX", 80))

        self.temperature_c = random.uniform(*self.temp_range)
        self.power_watts = random.uniform(*self.power_range)
        self.cpu_percent = random.uniform(*self.cpu_range)
        self.memory_percent = random.uniform(*self.memory_range)

    @staticmethod
    def _walk(value: float, bounds: tuple[float, float], step: float) -> float:
        lo, hi = bounds
        value += random.uniform(-step, step)
        if random.random() < 0.05:  # occasional larger swing
            value += random.uniform(-step * 3, step * 3)
        return round(min(hi, max(lo, value)), 2)

    def next(self, overrides: dict[str, float] | None = None) -> dict[str, Any]:
        self.temperature_c = self._walk(self.temperature_c, self.temp_range, 1.5)
        self.power_watts = self._walk(self.power_watts, self.power_range, 15.0)
        self.cpu_percent = self._walk(self.cpu_percent, self.cpu_range, 8.0)
        self.memory_percent = self._walk(self.memory_percent, self.memory_range, 4.0)

        sample: dict[str, Any] = {
            "temperature_c": round(self.temperature_c, 1),
            "power_watts": round(self.power_watts, 0),
            "cpu_percent": round(self.cpu_percent, 0),
            "memory_percent": round(self.memory_percent, 0),
        }
        for key, value in (overrides or {}).items():
            if key in sample:
                sample[key] = value
        return sample
