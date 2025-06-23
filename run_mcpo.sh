#!/bin/bash
set -euo pipefail
source .venv/bin/activate

uv sync
uv run server.py > logs/server.log &
server_pid=$!

echo "MCP server started [$server_pid]. Find logs in logs/server.log"

cleanup() {
  echo "Shutting down MCP server [$server_pid]..."
  kill -TERM -"$server_pid" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

mcpo --port 8000 --config mcpo.json
wait
