# Azure Kubernetes Application

## Prerequisites
Install...
- [ ] Docker
- [ ] kubectl `choco install kubernetes-cli`
- [ ] Minikube (run setup with Docker Desktop open)
- [ ] Terraform (add it to path)
- [ ] Azure CLI
- [ ] uv `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`

## Useful Commands

`kubectl get po -A` - lists all pods in your cluster

`minikube dashboard` - opens web based ui for kubernetes

**Docker**
`docker compose up --build -d` - Start the system in the background

`docker compose logs -f` - View logs from all services

`docker compose logs -f server` - Or only the server logs

`Invoke-RestMethod http://localhost:8000/health` - Test the monitoring API:
`Invoke-RestMethod http://localhost:8000/nodes` - Test the monitoring API:

`docker compose up --build -d --scale server=3` - Scale the server service:

`docker compose ps` - Check the scaled containers:

`docker compose up -d --scale server=1` - Scale back down

`docker compose down` - Stop and remove the containers
 
## Running

### 1. Set up the environment

```powershell
uv sync
```

### 2. Start the demo (recommended)

Starts the monitoring service, all three simulated servers, and opens the dashboard:

```powershell
.\scripts\start_demo.ps1
```

Once running, open the dashboard at http://127.0.0.1:8000

### 3. Start components manually

Terminal 1 - monitoring service:

```powershell
uv run python -m uvicorn monitoring.main:app --host 127.0.0.1 --port 8000
```

Terminal 2, 3, 4 - one simulated server per terminal:

```powershell
$env:NODE_ID='server-a'; uv run python -m server.main
$env:NODE_ID='server-b'; uv run python -m server.main
$env:NODE_ID='server-c'; uv run python -m server.main
```

### 4. Run the tests

```powershell
uv run pytest
```

### Configuration

Environment variables (with defaults):

```text
MONITORING_URL=http://127.0.0.1:8000
NODE_ID=server-a
INTERVAL=2
HEARTBEAT_TIMEOUT=6
ASSIGNMENT_TIMEOUT=30
TEMP_ALERT_C=80
POWER_ALERT_W=700
```