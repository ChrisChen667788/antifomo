#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMP_DIR="$ROOT_DIR/.tmp"
PID_FILE="$TMP_DIR/wechat_pc_agent.pid"
LOG_FILE="$TMP_DIR/wechat_pc_agent.log"
CONFIG_FILE="$TMP_DIR/wechat_pc_agent_config.json"
STATE_FILE="$TMP_DIR/wechat_pc_agent_state.json"
REPORT_FILE="$TMP_DIR/wechat_pc_agent_latest.json"

PID=""
if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE" || true)"
fi

RUNNING="false"
if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then
  RUNNING="true"
fi

if [[ "$RUNNING" != "true" ]]; then
  ORPHAN_PID="$(pgrep -f "$ROOT_DIR/scripts/wechat_pc_full_auto_agent.py.*--loop" | tail -n 1 || true)"
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
echo "config_file=$CONFIG_FILE"
echo "config_file_present=$([[ -f "$CONFIG_FILE" ]] && echo true || echo false)"
echo "state_file=$STATE_FILE"
echo "state_file_present=$([[ -f "$STATE_FILE" ]] && echo true || echo false)"
echo "report_file=$REPORT_FILE"
echo "report_file_present=$([[ -f "$REPORT_FILE" ]] && echo true || echo false)"
echo "log_file=$LOG_FILE"
echo "log_size_bytes=$LOG_SIZE"
