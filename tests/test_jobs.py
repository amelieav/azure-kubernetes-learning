from monitoring.health import HealthTracker
from monitoring.jobs import JobQueue
from monitoring.models import EventLog, JobStatus


def build_cluster():
    events = EventLog()
    health = HealthTracker(events, timeout=5)
    jobs = JobQueue(events, health, assignment_timeout=30)
    for node_id in ("server-a", "server-b", "server-c"):
        health.heartbeat(node_id)
    return health, jobs


def test_job_lifecycle():
    health, jobs = build_cluster()
    job = jobs.submit("process_telemetry_batch")

    jobs.assign_pending()
    assert job.status == JobStatus.ASSIGNED

    picked = jobs.next_for_node(job.assigned_to)
    assert picked.job_id == job.job_id
    assert job.status == JobStatus.RUNNING

    jobs.complete(job.job_id, {"processed": 3})
    assert job.status == JobStatus.COMPLETED
    assert job.result == {"processed": 3}
    assert health.nodes[job.assigned_to].active_jobs == 0


def test_least_loaded_assignment():
    health, jobs = build_cluster()
    health.nodes["server-a"].active_jobs = 2

    job = jobs.submit("detect_anomaly")
    jobs.assign_pending()
    assert job.assigned_to in ("server-b", "server-c")


def test_pending_jobs_wait_when_no_healthy_node():
    health, jobs = build_cluster()
    for node_id in ("server-a", "server-b", "server-c"):
        health.fail(node_id)
    jobs.requeue_unhealthy()

    job = jobs.submit("detect_anomaly")
    jobs.assign_pending()
    assert job.status == JobStatus.PENDING


def test_retry_increments_attempts():
    health, jobs = build_cluster()
    job = jobs.submit("detect_anomaly")
    jobs.assign_pending()
    assert job.attempts == 1

    health.fail("server-a")
    jobs.requeue_unhealthy()
    jobs.assign_pending()
    assert job.attempts == 2
