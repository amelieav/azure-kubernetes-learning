import time, requests
BASE="http://127.0.0.1:8000"

# ensure all healthy
for n in ("server-a","server-b","server-c"):
    requests.post(f"{BASE}/nodes/{n}/recover", timeout=5)
time.sleep(4)

# submit a job and immediately fail the node it lands on
job = requests.post(f"{BASE}/jobs", json={"type":"calculate_temperature_average"}, timeout=5).json()
time.sleep(1)
current = [j for j in requests.get(f"{BASE}/jobs", timeout=5).json() if j["job_id"]==job["job_id"]][0]
target = current["assigned_to"]
print("job", job["job_id"], "assigned to", target, "status", current["status"])
requests.post(f"{BASE}/nodes/{target}/fail", timeout=5)
time.sleep(2)
after = [j for j in requests.get(f"{BASE}/jobs", timeout=5).json() if j["job_id"]==job["job_id"]][0]
print("after fail:", after["status"], after["assigned_to"], "attempts", after["attempts"])

time.sleep(8)
final = [j for j in requests.get(f"{BASE}/jobs", timeout=5).json() if j["job_id"]==job["job_id"]][0]
print("final:", final["status"], final["assigned_to"], "attempts", final["attempts"])
assert final["status"] == "completed"
assert final["assigned_to"] != target
requests.post(f"{BASE}/nodes/{target}/recover", timeout=5)

# slow node test
requests.post(f"{BASE}/nodes/server-c/slow", json={"seconds": 9}, timeout=5)
print("server-c slowed, waiting for timeout...")
time.sleep(16)
c = requests.get(f"{BASE}/nodes/server-c", timeout=5).json()
print("server-c status:", c["status"])
assert c["status"] == "unhealthy"
events = requests.get(f"{BASE}/events", timeout=5).json()
assert any("heartbeat timeout" in e["message"] and "server-c" in e["message"] for e in events)
print("FAILOVER + SLOW NODE TEST PASSED")
