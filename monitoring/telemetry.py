from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any, Deque


@dataclass
class TelemetrySample:
    temperature_c: float
    power_watts: float
    cpu_percent: float
    memory_percent: float
    timestamp: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "temperature_c": self.temperature_c,
            "power_watts": self.power_watts,
            "cpu_percent": self.cpu_percent,
            "memory_percent": self.memory_percent,
            "timestamp": self.timestamp,
        }


class TelemetryStore:
    def __init__(self, history: int = 200) -> None:
        self.latest: dict[str, TelemetrySample] = {}
        self.history: dict[str, Deque[TelemetrySample]] = defaultdict(
            lambda: deque(maxlen=history)
        )

    def record(self, node_id: str, sample: TelemetrySample) -> None:
        self.latest[node_id] = sample
        self.history[node_id].append(sample)

    def get(self, node_id: str) -> TelemetrySample | None:
        return self.latest.get(node_id)

    def get_history(self, node_id: str, limit: int = 50) -> list[TelemetrySample]:
        return list(self.history.get(node_id, []))[-limit:]

    def all(self) -> dict[str, TelemetrySample]:
        return dict(self.latest)
