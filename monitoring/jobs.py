from __future__ import annotations

import time
import uuid
from collections import deque
from typing import Any

from monitoring.health import HealthTracker
from monitoring.models import EventLog, Job, JobStatus, NodeState


class JobQueue:
    """In-memory job queue with least-loaded assignment on healthy nodes."""

    def __init__(
        self,
        event_log: EventLog,
        health: HealthTracker,
        assignment_timeout: float = 30.0,
    ) -> None:
        self.jobs: dict[str, Job] = {}
        self.pending: deque[str] = deque()
        self.events = event_log
        self.health = health
        self.assignment_timeout = assignment_timeout

    def submit(self, job_type: str, payload: dict[str, Any] | None = None) -> Job:
        job = Job(job_id=f"job-{uuid.uuid4().hex[:6]}", type=job_type, payload=payload or {})
        self.jobs[job.job_id] = job
        self.pending.append(job.job_id)
        self.events.add(f"{job.job_id} created ({job_type})")
        return job

    def _pick_node(self) -> NodeState | None:
        nodes = self.health.healthy_nodes()
        if not nodes:
            return None
        return min(nodes, key=lambda n: n.active_jobs)

    def assign_pending(self) -> list[Job]:
        assigned: list[Job] = []
        while self.pending:
            node = self._pick_node()
            if node is None:
                break
            job = self.jobs.get(self.pending.popleft())
            if job is None or job.status != JobStatus.PENDING:
                continue
            job.status = JobStatus.ASSIGNED
            job.assigned_to = node.node_id
            job.assigned_at = time.time()
            job.attempts += 1
            node.active_jobs += 1
            assigned.append(job)
            self.events.add(f"{job.job_id} assigned to {node.node_id}")
        return assigned

    def _release(self, job: Job) -> None:
        node = self.health.nodes.get(job.assigned_to or "")
        if node is not None and node.active_jobs > 0:
            node.active_jobs -= 1

    def next_for_node(self, node_id: str) -> Job | None:
        node = self.health.nodes.get(node_id)
        if node is None or not node.healthy:
            return None
        for job in self.jobs.values():
            if job.assigned_to == node_id and job.status == JobStatus.ASSIGNED:
                job.status = JobStatus.RUNNING
                job.started_at = time.time()
                self.events.add(f"{job.job_id} started on {node_id}")
                return job
        return None

    def complete(self, job_id: str, result: dict[str, Any] | None = None) -> Job | None:
        job = self.jobs.get(job_id)
        if job is None:
            return None
        job.status = JobStatus.COMPLETED
        job.completed_at = time.time()
        job.result = result or {}
        self.events.add(f"{job.job_id} completed by {job.assigned_to}")
        self._release(job)
        return job

    def fail(self, job_id: str, reason: str = "reported failure") -> Job | None:
        job = self.jobs.get(job_id)
        if job is None:
            return None
        job.status = JobStatus.FAILED
        job.completed_at = time.time()
        self.events.add(f"{job.job_id} failed on {job.assigned_to} ({reason})", "error")
        self._release(job)
        return job

    def requeue_for_node(self, node_id: str) -> list[Job]:
        """Return unfinished jobs on a node to the pending queue."""
        requeued: list[Job] = []
        for job in self.jobs.values():
            if job.assigned_to == node_id and job.status in (JobStatus.ASSIGNED, JobStatus.RUNNING):
                self._release(job)
                job.status = JobStatus.PENDING
                job.assigned_to = None
                job.assigned_at = None
                self.pending.append(job.job_id)
                requeued.append(job)
                self.events.add(f"{job.job_id} reassigned from {node_id} (node unavailable)", "error")
        return requeued

    def requeue_unhealthy(self) -> list[Job]:
        requeued: list[Job] = []
        for node in self.health.nodes.values():
            if not node.healthy:
                requeued.extend(self.requeue_for_node(node.node_id))
        return requeued

    def reclaim_timed_out(self) -> list[Job]:
        now = time.time()
        requeued: list[Job] = []
        for job in self.jobs.values():
            if job.status in (JobStatus.ASSIGNED, JobStatus.RUNNING) and job.assigned_at:
                if now - job.assigned_at > self.assignment_timeout:
                    self._release(job)
                    self.events.add(f"{job.job_id} timed out on {job.assigned_to}", "warn")
                    job.status = JobStatus.PENDING
                    job.assigned_to = None
                    job.assigned_at = None
                    self.pending.append(job.job_id)
                    requeued.append(job)
        return requeued
