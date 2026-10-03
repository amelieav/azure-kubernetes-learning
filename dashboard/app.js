const REFRESH_MS = 2000;

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) throw new Error(`${path} -> ${response.status}`);
  return response.status === 204 ? null : response.json();
}

function formatTime(epochSeconds) {
  if (!epochSeconds) return "-";
  return new Date(epochSeconds * 1000).toLocaleTimeString();
}

function badge(status) {
  const value = (status || "unknown").toLowerCase();
  return `<span class="badge badge-${value}">${value.toUpperCase()}</span>`;
}

function renderStatus(health) {
  const el = document.getElementById("system-status"); 
  const operational = health.status === "operational";
  el.className = "status " + (operational ? "status-operational" : "status-degraded");
  el.textContent = `SYSTEM STATUS: ${health.status.toUpperCase()} (${health.healthy_nodes}/${health.total_nodes} nodes)`;
}

function renderNodes(nodes) {
  const body = document.getElementById("nodes-body");
  body.innerHTML = nodes
    .map((node) => {
      const temp = node.temperature_c != null ? `${node.temperature_c.toFixed(0)}C` : "-";
      const power = node.power_watts != null ? `${node.power_watts.toFixed(0)}W` : "-";
      const cpu = node.cpu_percent != null ? `${node.cpu_percent.toFixed(0)}%` : "-";
      const mem = node.memory_percent != null ? `${node.memory_percent.toFixed(0)}%` : "-";
      return `<tr>
        <td>${node.node_id}</td>
        <td>${badge(node.status)}</td>
        <td>${temp}</td>
        <td>${power}</td>
        <td>${cpu}</td>
        <td>${mem}</td>
        <td>${formatTime(node.last_heartbeat)}</td>
        <td>${node.active_jobs}</td>
        <td>
          <button onclick="failNode('${node.node_id}')">Fail</button>
          <button onclick="recoverNode('${node.node_id}')">Recover</button>
        </td>
      </tr>`;
    })
    .join("");
}

function renderJobs(jobs) {
  const body = document.getElementById("jobs-body");
  const order = { running: 0, assigned: 1, pending: 2, failed: 3, completed: 4 };
  const sorted = [...jobs].sort((a, b) => (order[a.status] ?? 5) - (order[b.status] ?? 5));
  body.innerHTML = sorted
    .slice(0, 40)
    .map(
      (job) => `<tr>
        <td>${job.job_id}</td>
        <td>${job.type}</td>
        <td>${badge(job.status)}</td>
        <td>${job.assigned_to || "-"}</td>
        <td>${job.attempts}</td>
      </tr>`
    )
    .join("");
}

function renderAlerts(alerts) {
  const list = document.getElementById("alerts-list");
  const recent = alerts.slice(-20).reverse();
  list.innerHTML = recent
    .map(
      (alert) =>
        `<li>${formatTime(alert.timestamp)} ${alert.node_id} - ${alert.type.replace(/_/g, " ")} (${alert.value.toFixed(0)})</li>`
    )
    .join("");
}

function renderEvents(events) {
  const list = document.getElementById("events-list");
  const recent = events.slice(-60).reverse();
  list.innerHTML = recent
    .map(
      (event) =>
        `<li class="level-${event.level}"><span class="time">${formatTime(event.timestamp)}</span>${event.message}</li>`
    )
    .join("");
}

async function refresh() {
  try {
    const [health, nodes, jobs, alerts, events] = await Promise.all([
      api("/health"),
      api("/nodes"),
      api("/jobs"),
      api("/alerts"),
      api("/events"),
    ]);
    renderStatus(health);
    renderNodes(nodes);
    renderJobs(jobs);
    renderAlerts(alerts);
    renderEvents(events);
  } catch (error) {
    console.error(error);
  }
}

function post(path, body) {
  return api(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
}

function failNode(nodeId) {
  post(`/nodes/${nodeId}/fail`).then(refresh);
}

function recoverNode(nodeId) {
  post(`/nodes/${nodeId}/recover`).then(refresh);
}

function slowNode(nodeId) {
  post(`/nodes/${nodeId}/slow`, { seconds: 3 }).then(refresh);
}

function injectAnomaly(nodeId) {
  post(`/nodes/${nodeId}/anomaly`, { temperature_c: 92, power_watts: 880 }).then(refresh);
}

function createJob() {
  const types = [
    "calculate_power_average",
    "calculate_temperature_average",
    "process_telemetry_batch",
    "detect_anomaly",
  ];
  const type = types[Math.floor(Math.random() * types.length)];
  post("/jobs", { type }).then(refresh);
}

refresh();
setInterval(refresh, REFRESH_MS);
