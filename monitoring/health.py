from __future__ import annotations

import time

from monitoring.models import EventLog, NodeState, NodeStatus


class HealthTracker:
    """Tracks registered nodes, heartbeats and simulated fault modes."""

    def __init__(self, event_log: EventLog, timeout: float = 6.0) -> None:
        self.nodes: dict[str, NodeState] = {}
        self.events = event_log
        self.timeout = timeout

    def register(self, node_id: str) -> NodeState:
        node = self.nodes.get(node_id)
        if node is None:
            node = NodeState(node_id=node_id)
            self.nodes[node_id] = node
            self.events.add(f"{node_id} registered")
        return node

    def heartbeat(self, node_id: str) -> NodeState:
        node = self.register(node_id)
        if node.forced_failed:
            return node
        node.last_heartbeat = time.time()
        if node.status != NodeStatus.HEALTHY:
            node.status = NodeStatus.HEALTHY
            self.events.add(f"{node_id} marked HEALTHY")
            self.events.add(f"{node_id} rejoined cluster")
        return node

    def evaluate(self) -> list[NodeState]:
        """Mark nodes unhealthy when their heartbeat is overdue."""
        now = time.time()
        changed: list[NodeState] = []
        for node in self.nodes.values():
            if node.forced_failed:
                if node.status != NodeStatus.FAILED:
                    node.status = NodeStatus.FAILED
                    changed.append(node)
                continue
            overdue = node.last_heartbeat is None or (now - node.last_heartbeat) > self.timeout
            if overdue and node.status != NodeStatus.UNHEALTHY:
                node.status = NodeStatus.UNHEALTHY
                self.events.add(f"{node.node_id} heartbeat timeout", "error")
                self.events.add(f"{node.node_id} marked UNHEALTHY", "error")
                changed.append(node)
        return changed

    def fail(self, node_id: str) -> NodeState:
        node = self.register(node_id)
        node.forced_failed = True
        node.running = False
        node.status = NodeStatus.FAILED
        node.last_heartbeat = None
        self.events.add(f"{node_id} marked FAILED", "error")
        self.events.add(f"{node_id} heartbeat stopped", "error")
        return node

    def recover(self, node_id: str) -> NodeState:
        node = self.register(node_id)
        node.forced_failed = False
        node.running = True
        node.delay = 0.0
        node.last_heartbeat = time.time()
        node.status = NodeStatus.RECOVERING
        self.events.add(f"{node_id} restarting...", "warn")
        return node

    def set_slow(self, node_id: str, seconds: float) -> NodeState:
        node = self.register(node_id)
        node.delay = float(seconds)
        self.events.add(f"{node_id} response delay set to {seconds}s", "warn")
        return node

    def set_anomaly(self, node_id: str, values: dict[str, float]) -> NodeState:
        node = self.register(node_id)
        node.overrides.update({k: float(v) for k, v in values.items() if v is not None})
        self.events.add(f"{node_id} anomaly injected {node.overrides}", "warn")
        return node

    def control(self, node_id: str) -> dict:
        """Return the current control instruction for a node (consumes overrides)."""
        node = self.register(node_id)
        overrides = dict(node.overrides)
        node.overrides = {}
        return {
            "running": node.running and not node.forced_failed,
            "delay": node.delay,
            "overrides": overrides,
        }

    def healthy_nodes(self) -> list[NodeState]:
        return [n for n in self.nodes.values() if n.healthy]
