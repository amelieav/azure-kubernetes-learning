#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

python -m uvicorn monitoring.main:app --host 127.0.0.1 --port 8000 &
sleep 3

bash "$ROOT/scripts/start_servers.sh"
