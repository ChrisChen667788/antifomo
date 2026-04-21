#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT_DIR/.tmp/collector.pid"

stop_pid() {
  local pid="$1"
  if [[ -z "${pid:-}" ]]; then
    return 0
  fi
  if kill -0 "$pid" 2>/dev/null; then
    kill "$pid" || true
    sleep 1
    if kill -0 "$pid" 2>/dev/null; then
      kill -9 "$pid" || true
    fi
    echo "Collector stopped (PID: $pid)."
  fi
}

if [[ ! -f "$PID_FILE" ]]; then
  echo "Collector pid file not found, checking orphan processes..."
else
  PID="$(cat "$PID_FILE" || true)"
  stop_pid "$PID"
  rm -f "$PID_FILE"
fi

# Fallback: ensure no orphan collector process is left running.
for pattern in \
  "$ROOT_DIR/scripts/desktop_wechat_collector.mjs" \
  "$ROOT_DIR/.tmp/wechat_collector_sources.txt"; do
  while IFS= read -r orphan_pid; do
    if [[ "$orphan_pid" != "$$" ]]; then
      stop_pid "$orphan_pid"
    fi
  done < <(pgrep -f "$pattern" || true)
done

echo "Collector stop completed."
