#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

for node in server-a server-b server-c; do
  NODE_ID="$node" python -m server.main &
  echo "started $node"
done
wait
