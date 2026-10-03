from __future__ import annotations

import os
import random
import threading
import time
from typing import Any

import requests

from server.telemetry import TelemetryGenerator

MONITORING_URL = os.getenv("MONITORING_URL", "http://127.0.0.1:8000").rstrip("/")
NODE_ID = os.getenv("NODE_ID", "server-a")
INTERVAL = float(os.getenv("INTERVAL", "2"))
JOB_POLL_INTERVAL = float(os.getenv("JOB_POLL_INTERVAL", "0.5"))
JOB_MIN_SECONDS = float(os.getenv("JOB_MIN_SECONDS", "1.5"))
JOB_MAX_SECONDS = float(os.getenv("JOB_MAX_SECONDS", "3.5"))


def _get(path: str) -> Any:
    response = requests.get(f"{MONITORING_URL}{path}", timeout=5)
    response.raise_for_status()
    return response.json()


def _post(path: str, payload: dict[str, Any] | None = None) -> Any:
    response = requests.post(f"{MONITORING_URL}{path}", json=payload or {}, timeout=5)
    response.raise_for_status()
    return response.json()


def telemetry_loop(generator: TelemetryGenerator) -> None:
    while True:
        try:
            control = _get(f"/nodes/{NODE_ID}/control")
        except Exception:
            time.sleep(INTERVAL)
            continue

        if not control.get("running", True):
            time.sleep(INTERVAL)
            continue

        delay = float(control.get("delay") or 0)
        if delay:
            # Simulate an unresponsive node: it stops reporting until the delay is cleared.
            time.sleep(delay)
            continue

        sample = generator.next(control.get("overrides") or {})
        try:
            _post(f"/nodes/{NODE_ID}/heartbeat", {"timestamp": time.time(), "status": "healthy"})
            _post(f"/nodes/{NODE_ID}/telemetry", sample)
        except Exception:
            pass
        time.sleep(INTERVAL)


def compute(job: dict[str, Any]) -> dict[str, Any]:
    job_type = job.get("type", "")
    if job_type in ("calculate_power_average", "calculate_temperature_average", "detect_anomaly"):
        try:
            data = _get("/telemetry")
        except Exception:
            data = {}
        if job_type == "calculate_power_average":
            values = [v["power_watts"] for v in data.values() if v.get("power_watts") is not None]
            return {"average_power_watts": round(sum(values) / len(values), 2) if values else None, "samples": len(values)}
        if job_type == "calculate_temperature_average":
            values = [v["temperature_c"] for v in data.values() if v.get("temperature_c") is not None]
            return {"average_temperature_c": round(sum(values) / len(values), 2) if values else None, "samples": len(values)}
        anomalies = [
            node_id
            for node_id, v in data.items()
            if (v.get("temperature_c") or 0) > 80 or (v.get("power_watts") or 0) > 700
        ]
        return {"anomalies": anomalies}
    return {"processed": True, "node_id": NODE_ID}


def do_job(job: dict[str, Any]) -> None:
    time.sleep(random.uniform(JOB_MIN_SECONDS, JOB_MAX_SECONDS))
    try:
        _post(f"/jobs/{job['job_id']}/complete", {"result": compute(job)})
    except Exception:
        try:
            _post(f"/jobs/{job['job_id']}/fail")
        except Exception:
            pass


def job_loop() -> None:
    while True:
        try:
            job = _get(f"/nodes/{NODE_ID}/jobs/next").get("job")
        except Exception:
            job = None
        if not job:
            time.sleep(JOB_POLL_INTERVAL)
            continue
        do_job(job)


def main() -> None:
    generator = TelemetryGenerator()
    threading.Thread(target=telemetry_loop, args=(generator,), daemon=True).start()
    print(f"{NODE_ID} simulator started, monitoring at {MONITORING_URL}")
    job_loop()


if __name__ == "__main__":
    main()
