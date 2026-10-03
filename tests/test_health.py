import time

from monitoring.health import HealthTracker
from monitoring.models import EventLog, NodeStatus


def test_heartbeat_marks_healthy():
    health = HealthTracker(EventLog(), timeout=5)
    health.register("server-a")
    assert health.nodes["server-a"].status == NodeStatus.UNKNOWN

    health.heartbeat("server-a")
    assert health.nodes["server-a"].status == NodeStatus.HEALTHY
    assert health.nodes["server-a"].healthy


def test_stale_heartbeat_marks_unhealthy():
    health = HealthTracker(EventLog(), timeout=1)
    health.heartbeat("server-a")
    health.nodes["server-a"].last_heartbeat = time.time() - 10

    changed = health.evaluate()
    assert health.nodes["server-a"].status == NodeStatus.UNHEALTHY
    assert not health.nodes["server-a"].healthy
    assert changed


def test_fail_and_recover_transitions():
    health = HealthTracker(EventLog(), timeout=5)
    health.heartbeat("server-a")

    health.fail("server-a")
    assert health.nodes["server-a"].status == NodeStatus.FAILED
    assert not health.nodes["server-a"].running

    health.recover("server-a")
    assert health.nodes["server-a"].status == NodeStatus.RECOVERING

    health.heartbeat("server-a")
    assert health.nodes["server-a"].status == NodeStatus.HEALTHY


def test_control_consumes_overrides_once():
    health = HealthTracker(EventLog(), timeout=5)
    health.set_anomaly("server-a", {"temperature_c": 90})

    first = health.control("server-a")
    second = health.control("server-a")
    assert first["overrides"] == {"temperature_c": 90.0}
    assert second["overrides"] == {}
