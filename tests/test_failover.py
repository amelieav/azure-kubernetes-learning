from monitoring.health import HealthTracker
from monitoring.jobs import JobQueue
from monitoring.models import EventLog, JobStatus, NodeStatus


def build_cluster():
    events = EventLog()
    health = HealthTracker(events, timeout=5)
    jobs = JobQueue(events, health, assignment_timeout=30)
    for node_id in ("server-a", "server-b", "server-c"):
        health.heartbeat(node_id)
    return health, jobs


def test_job_is_reassigned_after_node_failure():
    health, jobs = build_cluster()
    job = jobs.submit("calculate_power_average")
    jobs.assign_pending()
    assert job.assigned_to == "server-a"
    assert job.status == JobStatus.ASSIGNED

    health.fail("server-a")
    jobs.requeue_unhealthy()
    assert job.status == JobStatus.PENDING
    assert job.assigned_to is None

    jobs.assign_pending()
    assert job.assigned_to in ("server-b", "server-c")
    assert job.status == JobStatus.ASSIGNED


def test_running_job_is_requeued_on_failure():
    health, jobs = build_cluster()
    job = jobs.submit("detect_anomaly")
    jobs.assign_pending()
    picked = jobs.next_for_node("server-a")
    assert picked.job_id == job.job_id
    assert job.status == JobStatus.RUNNING

    health.fail("server-a")
    jobs.requeue_unhealthy()
    assert job.status == JobStatus.PENDING


def test_system_keeps_operating_with_one_node():
    health, jobs = build_cluster()
    health.fail("server-a")
    jobs.requeue_unhealthy()

    job = jobs.submit("calculate_temperature_average")
    jobs.assign_pending()
    assert job.assigned_to in ("server-b", "server-c")
    assert health.nodes["server-b"].healthy
    assert health.nodes["server-c"].healthy
