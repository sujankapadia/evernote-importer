#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
START_PORT="${PORT:-8000}"

port_in_use() {
  local port="$1"
  lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1
}

pick_port() {
  local port="$1"
  while port_in_use "$port"; do
    port=$((port + 1))
  done
  printf '%s\n' "$port"
}

PORT="$(pick_port "$START_PORT")"

echo "Starting Evernote Archive at http://${HOST}:${PORT}"
uvicorn backend.main:app --reload --host "$HOST" --port "$PORT"
