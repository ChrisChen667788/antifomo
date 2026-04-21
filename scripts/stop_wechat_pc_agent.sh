#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT_DIR/.tmp/wechat_pc_agent.pid"

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
    echo "WeChat PC agent stopped (PID: $pid)."
  fi
}

if [[ ! -f "$PID_FILE" ]]; then
  echo "WeChat PC agent pid file not found, checking orphan processes..."
else
  PID="$(cat "$PID_FILE" || true)"
  stop_pid "$PID"
  rm -f "$PID_FILE"
fi

while IFS= read -r orphan_pid; do
  if [[ "$orphan_pid" != "$$" ]]; then
    stop_pid "$orphan_pid"
  fi
done < <(pgrep -f "$ROOT_DIR/scripts/wechat_pc_full_auto_agent.py" || true)

echo "WeChat PC agent stop completed."
