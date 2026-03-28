#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
TMP_DIR="$ROOT_DIR/.tmp"
BACKEND_PID_FILE="$TMP_DIR/backend.pid"
FRONTEND_PID_FILE="$TMP_DIR/frontend.pid"
BACKEND_LOG="$TMP_DIR/backend.log"
FRONTEND_LOG="$TMP_DIR/frontend.log"
BACKEND_URL="${BACKEND_URL:-http://127.0.0.1:8000}"
FRONTEND_URL="${FRONTEND_URL:-http://127.0.0.1:3000}"
AUTO_OPEN_BROWSER="${AUTO_OPEN_BROWSER:-1}"
FRONTEND_NODE="${FRONTEND_NODE:-}"

mkdir -p "$TMP_DIR"

is_pid_running() {
  local pid="$1"
  if [[ -z "$pid" ]]; then
    return 1
  fi
  kill -0 "$pid" >/dev/null 2>&1
}

read_pid() {
  local pid_file="$1"
  if [[ -f "$pid_file" ]]; then
    cat "$pid_file"
  fi
}

wait_http_ok() {
  local url="$1"
  local max_try="${2:-30}"
  local i=1
  until curl -fsS "$url" >/dev/null 2>&1; do
    if [[ "$i" -ge "$max_try" ]]; then
      return 1
    fi
    i=$((i + 1))
    sleep 1
  done
}

ensure_dependencies() {
  if [[ ! -d "$BACKEND_DIR/.venv312" && ! -d "$BACKEND_DIR/.venv" && ! -d "$BACKEND_DIR/.venv311" || ! -d "$ROOT_DIR/node_modules" ]]; then
    echo "[setup] installing dependencies..."
    "$ROOT_DIR/scripts/setup_demo.sh"
  fi
}

start_backend() {
  local existing_pid
  existing_pid="$(read_pid "$BACKEND_PID_FILE")"
  if is_pid_running "$existing_pid"; then
    echo "[backend] already running (pid=$existing_pid)"
    return
  fi

  echo "[backend] starting..."
  local backend_python
  if [ -d "$BACKEND_DIR/.venv312" ]; then
    backend_python="$BACKEND_DIR/.venv312/bin/python"
  elif [ -d "$BACKEND_DIR/.venv" ]; then
    backend_python="$BACKEND_DIR/.venv/bin/python"
  else
    backend_python="$BACKEND_DIR/.venv311/bin/python"
  fi
  if [ ! -f "$BACKEND_DIR/.env" ]; then
    cp "$BACKEND_DIR/.env.example" "$BACKEND_DIR/.env"
  fi
  local backend_pid
  backend_pid="$(
    BACKEND_PYTHON="$backend_python" BACKEND_DIR="$BACKEND_DIR" BACKEND_LOG="$BACKEND_LOG" python3 - <<'PY'
import os
import subprocess

log = open(os.environ["BACKEND_LOG"], "ab", buffering=0)
proc = subprocess.Popen(
    [
        os.environ["BACKEND_PYTHON"],
        "-m",
        "uvicorn",
        "app.main:app",
        "--host",
        "0.0.0.0",
        "--port",
        "8000",
        "--app-dir",
        os.environ["BACKEND_DIR"],
    ],
    stdin=subprocess.DEVNULL,
    stdout=log,
    stderr=subprocess.STDOUT,
    cwd=os.environ["BACKEND_DIR"],
    start_new_session=True,
)
print(proc.pid)
PY
  )"
  echo "$backend_pid" >"$BACKEND_PID_FILE"

  if wait_http_ok "$BACKEND_URL/healthz" 40; then
    echo "[backend] ready at $BACKEND_URL"
  else
    echo "[backend] failed to become ready. check log: $BACKEND_LOG"
    return 1
  fi
}

start_frontend() {
  local existing_pid
  existing_pid="$(read_pid "$FRONTEND_PID_FILE")"
  if is_pid_running "$existing_pid"; then
    echo "[frontend] already running (pid=$existing_pid)"
    return
  fi

  echo "[frontend] starting..."
  local frontend_pid
  frontend_pid="$(
    ROOT_DIR="$ROOT_DIR" BACKEND_URL="$BACKEND_URL" FRONTEND_LOG="$FRONTEND_LOG" FRONTEND_NODE="$FRONTEND_NODE" python3 - <<'PY'
import os
import subprocess

log = open(os.environ["FRONTEND_LOG"], "ab", buffering=0)
frontend_node = os.environ.get("FRONTEND_NODE", "").strip()
if not frontend_node:
    preferred = [
        "/opt/homebrew/opt/node@22/bin/node",
        "/usr/local/opt/node@22/bin/node",
        "/opt/homebrew/bin/node",
        "/usr/local/bin/node",
    ]
    for candidate in preferred:
        if os.path.exists(candidate):
            frontend_node = candidate
            break
if not frontend_node:
    raise SystemExit("no usable node binary found for frontend")
proc = subprocess.Popen(
    [
        "/bin/bash",
        "-lc",
        (
            f"cd '{os.environ['ROOT_DIR']}' && "
            f"NEXT_PUBLIC_API_BASE_URL='{os.environ['BACKEND_URL']}' "
            f"exec '{frontend_node}' '{os.environ['ROOT_DIR']}/node_modules/next/dist/bin/next' dev --webpack --port 3000"
        ),
    ],
    stdin=subprocess.DEVNULL,
    stdout=log,
    stderr=subprocess.STDOUT,
    cwd=os.environ["ROOT_DIR"],
    start_new_session=True,
)
print(proc.pid)
PY
  )"
  echo "$frontend_pid" >"$FRONTEND_PID_FILE"

  if wait_http_ok "$FRONTEND_URL" 60; then
    echo "[frontend] ready at $FRONTEND_URL"
  else
    echo "[frontend] failed to become ready. check log: $FRONTEND_LOG"
    return 1
  fi
}

open_browser() {
  if [[ "$AUTO_OPEN_BROWSER" != "1" ]]; then
    return
  fi

  if command -v open >/dev/null 2>&1; then
    open "$FRONTEND_URL" >/dev/null 2>&1 || true
  fi
}

ensure_dependencies
start_backend
start_frontend
open_browser

echo
echo "Demo started."
echo "- Web: $FRONTEND_URL"
echo "- API: $BACKEND_URL"
echo "- Backend log: $BACKEND_LOG"
echo "- Frontend log: $FRONTEND_LOG"
echo
echo "Stop command: npm run demo:stop"
