from __future__ import annotations

import asyncio
import os
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from monitoring.health import HealthTracker
from monitoring.jobs import JobQueue
from monitoring.models import EventLog, Job, JobStatus, NodeStatus
from monitoring.telemetry import TelemetrySample, TelemetryStore

HEARTBEAT_TIMEOUT = float(os.getenv("HEARTBEAT_TIMEOUT", "6"))
ASSIGNMENT_TIMEOUT = float(os.getenv("ASSIGNMENT_TIMEOUT", "30"))
TEMP_ALERT_C = float(os.getenv("TEMP_ALERT_C", "80"))
POWER_ALERT_W = float(os.getenv("POWER_ALERT_W", "700"))

events = EventLog()
health = HealthTracker(events, timeout=HEARTBEAT_TIMEOUT)
telemetry = TelemetryStore()
jobs = JobQueue(events, health, assignment_timeout=ASSIGNMENT_TIMEOUT)
alerts: list[dict[str, Any]] = []


class HeartbeatIn(BaseModel):
    timestamp: float | None = None
    status: str = "healthy"


class TelemetryIn(BaseModel):
    temperature_c: float
    power_watts: float
    cpu_percent: float
    memory_percent: float
    timestamp: float | None = None


class JobIn(BaseModel):
    type: str
    payload: dict[str, Any] | None = None


class CompleteIn(BaseModel):
    result: dict[str, Any] | None = None


class SlowIn(BaseModel):
    seconds: float = 5.0


class AnomalyIn(BaseModel):
    temperature_c: float | None = None
    power_watts: float | None = None
    cpu_percent: float | None = None
    memory_percent: float | None = None


def _node_view(node_id: str) -> dict[str, Any]:
    node = health.nodes.get(node_id)
    if node is None:
        raise HTTPException(status_code=404, detail=f"unknown node {node_id}")
    sample = telemetry.get(node_id)
    return {
        "node_id": node_id,
        "status": node.status.value,
        "healthy": node.healthy,
        "temperature_c": sample.temperature_c if sample else None,
        "power_watts": sample.power_watts if sample else None,
        "cpu_percent": sample.cpu_percent if sample else None,
        "memory_percent": sample.memory_percent if sample else None,
        "last_heartbeat": node.last_heartbeat,
        "active_jobs": node.active_jobs,
        "running": node.running and not node.forced_failed,
        "delay": node.delay,
    }


def _job_view(job: Job) -> dict[str, Any]:
    return {
        "job_id": job.job_id,
        "type": job.type,
        "status": job.status.value,
        "assigned_to": job.assigned_to,
        "attempts": job.attempts,
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "result": job.result,
    }


def _check_alerts(node_id: str, sample: TelemetrySample) -> None:
    if sample.temperature_c >= TEMP_ALERT_C:
        alerts.append(
            {"node_id": node_id, "type": "high_temperature", "value": sample.temperature_c, "timestamp": sample.timestamp}
        )
        events.add(f"{node_id} temperature warning: {sample.temperature_c:.0f}C", "warn")
    if sample.power_watts >= POWER_ALERT_W:
        alerts.append(
            {"node_id": node_id, "type": "power_spike", "value": sample.power_watts, "timestamp": sample.timestamp}
        )
        events.add(f"{node_id} power warning: {sample.power_watts:.0f}W", "warn")


async def _health_loop() -> None:
    while True:
        health.evaluate()
        jobs.requeue_unhealthy()
        jobs.reclaim_timed_out()
        await asyncio.sleep(1)


async def _assignment_loop() -> None:
    while True:
        jobs.assign_pending()
        await asyncio.sleep(0.5)


@asynccontextmanager
async def lifespan(app: FastAPI):
    tasks = [asyncio.create_task(_health_loop()), asyncio.create_task(_assignment_loop())]
    yield
    for task in tasks:
        task.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="Distributed Server Monitor", lifespan=lifespan)


@app.post("/nodes/{node_id}/heartbeat")
def receive_heartbeat(node_id: str, body: HeartbeatIn) -> dict[str, Any]:
    node = health.heartbeat(node_id)
    return {"node_id": node_id, "status": node.status.value}


@app.post("/nodes/{node_id}/telemetry")
def receive_telemetry(node_id: str, body: TelemetryIn) -> dict[str, Any]:
    health.register(node_id)
    sample = TelemetrySample(
        temperature_c=body.temperature_c,
        power_watts=body.power_watts,
        cpu_percent=body.cpu_percent,
        memory_percent=body.memory_percent,
        timestamp=body.timestamp or time.time(),
    )
    telemetry.record(node_id, sample)
    _check_alerts(node_id, sample)
    return {"ok": True}


@app.get("/nodes/{node_id}/control")
def get_control(node_id: str) -> dict[str, Any]:
    return health.control(node_id)


@app.get("/nodes/{node_id}/jobs/next")
def next_job(node_id: str) -> dict[str, Any]:
    job = jobs.next_for_node(node_id)
    return {"job": _job_view(job) if job else None}


@app.post("/nodes/{node_id}/fail")
def fail_node(node_id: str) -> dict[str, Any]:
    health.fail(node_id)
    jobs.requeue_for_node(node_id)
    return _node_view(node_id)


@app.post("/nodes/{node_id}/recover")
def recover_node(node_id: str) -> dict[str, Any]:
    health.recover(node_id)
    return _node_view(node_id)


@app.post("/nodes/{node_id}/slow")
def slow_node(node_id: str, body: SlowIn) -> dict[str, Any]:
    health.set_slow(node_id, body.seconds)
    return _node_view(node_id)


@app.post("/nodes/{node_id}/anomaly")
def inject_anomaly(node_id: str, body: AnomalyIn) -> dict[str, Any]:
    health.set_anomaly(node_id, body.model_dump(exclude_none=True))
    return {"ok": True, "node_id": node_id}


@app.get("/nodes")
def list_nodes() -> list[dict[str, Any]]:
    return [_node_view(node_id) for node_id in health.nodes]


@app.get("/nodes/{node_id}")
def get_node(node_id: str) -> dict[str, Any]:
    return _node_view(node_id)


@app.get("/telemetry")
def all_telemetry() -> dict[str, Any]:
    return {node_id: sample.as_dict() for node_id, sample in telemetry.all().items()}


@app.get("/telemetry/{node_id}")
def node_telemetry(node_id: str) -> dict[str, Any]:
    sample = telemetry.get(node_id)
    if sample is None:
        raise HTTPException(status_code=404, detail=f"no telemetry for {node_id}")
    return sample.as_dict()


@app.get("/health")
def cluster_health() -> dict[str, Any]:
    healthy = [n.node_id for n in health.nodes.values() if n.healthy]
    return {
        "status": "operational" if healthy else "degraded",
        "healthy_nodes": len(healthy),
        "total_nodes": len(health.nodes),
        "nodes": healthy,
    }


@app.get("/events")
def get_events(limit: int = 200) -> list[dict[str, Any]]:
    return [
        {"timestamp": e.timestamp, "message": e.message, "level": e.level}
        for e in events.recent(limit)
    ]


@app.get("/alerts")
def get_alerts() -> list[dict[str, Any]]:
    return alerts


@app.post("/jobs")
def create_job(body: JobIn) -> dict[str, Any]:
    job = jobs.submit(body.type, body.payload)
    return _job_view(job)


@app.get("/jobs")
def list_jobs() -> list[dict[str, Any]]:
    return [_job_view(job) for job in jobs.jobs.values()]


@app.post("/jobs/{job_id}/complete")
def complete_job(job_id: str, body: CompleteIn | None = None) -> dict[str, Any]:
    job = jobs.complete(job_id, body.result if body else None)
    if job is None:
        raise HTTPException(status_code=404, detail=f"unknown job {job_id}")
    return _job_view(job)


@app.post("/jobs/{job_id}/fail")
def fail_job(job_id: str) -> dict[str, Any]:
    job = jobs.fail(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"unknown job {job_id}")
    return _job_view(job)


_dashboard_dir = Path(__file__).resolve().parent.parent / "dashboard"
if _dashboard_dir.is_dir():
    app.mount("/", StaticFiles(directory=str(_dashboard_dir), html=True), name="dashboard")
