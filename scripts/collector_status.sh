#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="$ROOT_DIR/.tmp/collector.pid"
LOG_FILE="$ROOT_DIR/.tmp/collector.log"
REPORT_FILE="$ROOT_DIR/.tmp/wechat_collector_latest.md"
DAILY_FILE="$ROOT_DIR/.tmp/collector_daily_summary.md"

PID=""
if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE" || true)"
fi

RUNNING="false"
if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then
  RUNNING="true"
fi

if [[ "$RUNNING" != "true" ]]; then
  ORPHAN_PID="$(pgrep -f "$ROOT_DIR/scripts/desktop_wechat_collector.mjs.*--loop" | tail -n 1 || true)"
  if [[ -n "${ORPHAN_PID:-}" ]] && kill -0 "$ORPHAN_PID" 2>/dev/null; then
    PID="$ORPHAN_PID"
    RUNNING="true"
  fi
fi

LOG_SIZE=0
if [[ -f "$LOG_FILE" ]]; then
  LOG_SIZE="$(wc -c <"$LOG_FILE" | tr -d ' ')"
fi

echo "running=$RUNNING"
echo "pid=${PID:-}"
echo "pid_file_present=$([[ -f "$PID_FILE" ]] && echo true || echo false)"
echo "log_file=$LOG_FILE"
echo "log_size_bytes=$LOG_SIZE"
echo "latest_report_exists=$([[ -f "$REPORT_FILE" ]] && echo true || echo false)"
echo "daily_report_exists=$([[ -f "$DAILY_FILE" ]] && echo true || echo false)"
