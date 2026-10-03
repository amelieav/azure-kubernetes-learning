from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Deque


class NodeStatus(str, Enum):
    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    FAILED = "failed"
    RECOVERING = "recovering"
    UNKNOWN = "unknown"


class JobStatus(str, Enum):
    PENDING = "pending"
    ASSIGNED = "assigned"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class NodeState:
    node_id: str
    status: NodeStatus = NodeStatus.UNKNOWN
    last_heartbeat: float | None = None
    forced_failed: bool = False
    running: bool = True
    delay: float = 0.0
    overrides: dict[str, float] = field(default_factory=dict)
    active_jobs: int = 0

    @property
    def healthy(self) -> bool:
        return self.status == NodeStatus.HEALTHY and not self.forced_failed and self.running


@dataclass
class Job:
    job_id: str
    type: str
    payload: dict[str, Any] = field(default_factory=dict)
    status: JobStatus = JobStatus.PENDING
    created_at: float = field(default_factory=time.time)
    assigned_to: str | None = None
    assigned_at: float | None = None
    started_at: float | None = None
    completed_at: float | None = None
    attempts: int = 0
    result: dict[str, Any] | None = None


@dataclass
class Event:
    timestamp: float
    message: str
    level: str = "info"


class EventLog:
    def __init__(self, maxlen: int = 1000) -> None:
        self.events: Deque[Event] = deque(maxlen=maxlen)

    def add(self, message: str, level: str = "info") -> Event:
        event = Event(time.time(), message, level)
        self.events.append(event)
        return event

    def recent(self, limit: int = 200) -> list[Event]:
        return list(self.events)[-limit:]
