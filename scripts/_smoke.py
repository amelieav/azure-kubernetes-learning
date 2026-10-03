import time
import requests

BASE = "http://127.0.0.1:8000"

def wait_nodes(timeout=20):
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            nodes = requests.get(f"{BASE}/nodes", timeout=3).json()
            if len(nodes) == 3 and all(n["status"] == "healthy" for n in nodes):
                return nodes
        except Exception:
            pass
        time.sleep(1)
    raise SystemExit(f"nodes not healthy: {nodes if 'nodes' in dir() else 'no response'}")

print("waiting for 3 healthy nodes...")
nodes = wait_nodes()
print("healthy:", sorted(n["node_id"] for n in nodes))

for _ in range(3):
    requests.post(f"{BASE}/jobs", json={"type": "calculate_power_average"}, timeout=5)
print("submitted 3 jobs")

time.sleep(8)
jobs = requests.get(f"{BASE}/jobs", timeout=5).json()
print("job statuses:", [(j["job_id"], j["status"], j["assigned_to"]) for j in jobs])
assert all(j["status"] == "completed" for j in jobs), "jobs did not all complete"

requests.post(f"{BASE}/nodes/server-a/fail", timeout=5)
time.sleep(3)
node_a = requests.get(f"{BASE}/nodes/server-a", timeout=5).json()
print("server-a after fail:", node_a["status"])
assert node_a["status"] == "failed"

requests.post(f"{BASE}/jobs", json={"type": "detect_anomaly"}, timeout=5)
time.sleep(3)
new_job = requests.get(f"{BASE}/jobs", timeout=5).json()[-1]
print("new job assigned to:", new_job["assigned_to"], new_job["status"])
assert new_job["assigned_to"] in ("server-b", "server-c")

health = requests.get(f"{BASE}/health", timeout=5).json()
print("cluster health:", health)
assert health["status"] == "operational"

requests.post(f"{BASE}/nodes/server-a/recover", timeout=5)
time.sleep(4)
node_a = requests.get(f"{BASE}/nodes/server-a", timeout=5).json()
print("server-a after recover:", node_a["status"])
assert node_a["status"] == "healthy"

requests.post(f"{BASE}/nodes/server-a/anomaly", json={"temperature_c": 92, "power_watts": 880}, timeout=5)
time.sleep(4)
alerts = requests.get(f"{BASE}/alerts", timeout=5).json()
print("alerts:", alerts[-3:])
assert any(a["type"] == "high_temperature" for a in alerts)
assert any(a["type"] == "power_spike" for a in alerts)

events = requests.get(f"{BASE}/events", timeout=5).json()
print("recent events:")
for e in events[-8:]:
    print("  ", e["message"])

print("SMOKE TEST PASSED")
