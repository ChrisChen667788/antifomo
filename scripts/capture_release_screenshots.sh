#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
FRONTEND_PORT="${SCREENSHOT_FRONTEND_PORT:-$(python3 - <<'PY'
import socket

with socket.socket() as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
)}"
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"
API_BASE="${SCREENSHOT_API_BASE:-http://127.0.0.1:8000}"
LOG_DIR="$ROOT_DIR/.tmp"
FRONTEND_LOG="$LOG_DIR/repo-screenshot-frontend.log"

mkdir -p "$LOG_DIR"

if ! curl -fsS "$API_BASE/healthz" >/dev/null; then
  echo "Screenshot backend is not healthy at $API_BASE/healthz" >&2
  exit 1
fi

cleanup() {
  if [[ -n "${FRONTEND_PID:-}" ]] && kill -0 "$FRONTEND_PID" >/dev/null 2>&1; then
    pkill -TERM -P "$FRONTEND_PID" >/dev/null 2>&1 || true
    kill "$FRONTEND_PID" >/dev/null 2>&1 || true
    wait "$FRONTEND_PID" >/dev/null 2>&1 || true
  fi
}
trap cleanup EXIT INT TERM

cd "$ROOT_DIR"
NEXT_PUBLIC_API_BASE_URL="$API_BASE" npm run build
NEXT_PUBLIC_API_BASE_URL="$API_BASE" node node_modules/next/dist/bin/next start --port "$FRONTEND_PORT" >"$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!

for _ in {1..60}; do
  if curl -fsS "$FRONTEND_URL" >/dev/null; then
    node scripts/capture_repo_screenshots.mjs --frontend-url "$FRONTEND_URL" --api-base "$API_BASE" "$@"
    exit 0
  fi
  sleep 1
done

cat "$FRONTEND_LOG" >&2
echo "Screenshot frontend failed to become ready at $FRONTEND_URL" >&2
exit 1
