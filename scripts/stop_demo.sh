#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TMP_DIR="$ROOT_DIR/.tmp"
BACKEND_PID_FILE="$TMP_DIR/backend.pid"
FRONTEND_PID_FILE="$TMP_DIR/frontend.pid"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

stop_pid_file() {
  local name="$1"
  local pid_file="$2"

  if [[ ! -f "$pid_file" ]]; then
    echo "[$name] not running"
    return
  fi

  local pid
  pid="$(cat "$pid_file")"
  if [[ -z "$pid" ]]; then
    rm -f "$pid_file"
    echo "[$name] cleaned empty pid file"
    return
  fi

  if kill -0 "$pid" >/dev/null 2>&1; then
    kill "$pid" >/dev/null 2>&1 || true
    sleep 1
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
    echo "[$name] stopped pid=$pid"
  else
    echo "[$name] process already exited"
  fi

  rm -f "$pid_file"
}

kill_by_port() {
  local name="$1"
  local port="$2"
  local pids
  if ! command -v lsof >/dev/null 2>&1; then
    return
  fi
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [[ -z "$pids" ]]; then
    return
  fi
  for pid in $pids; do
    kill "$pid" >/dev/null 2>&1 || true
  done
  sleep 1
  pids="$(lsof -ti tcp:"$port" 2>/dev/null || true)"
  if [[ -n "$pids" ]]; then
    for pid in $pids; do
      kill -9 "$pid" >/dev/null 2>&1 || true
    done
  fi
  echo "[$name] cleaned remaining process on port $port"
}

stop_pid_file "frontend" "$FRONTEND_PID_FILE"
stop_pid_file "backend" "$BACKEND_PID_FILE"
kill_by_port "frontend" "$FRONTEND_PORT"
kill_by_port "backend" "$BACKEND_PORT"

echo "Demo stopped."
