#!/bin/bash
set -euo pipefail

uv run mcp.py > logs/mcp.log &
server_pid=$!

echo "MCP server started [$server_pid]. Find logs in logs/mcp.log"

cleanup() {
  echo "Shutting down MCP server [$server_pid]..."
  kill -TERM -"$server_pid" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

mcpo --port 8000 --config mcpo.json
wait
