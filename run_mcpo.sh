#!/bin/bash
set -euo pipefail
source .venv/bin/activate

uv sync
uv run server.py > logs/server.log &
server_pid=$!

echo "MCP server started. Find logs in logs/server.log"

cleanup() {
  echo "Shutting down MCP server..."
  # The minus sign kills the whole process-group, not just the leader
  kill -TERM -"$server_pid" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

mcpo --port 8000 --config mcpo.json
wait
