#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMP_DIR="$ROOT_DIR/.tmp"
PID_FILE="$TMP_DIR/wechat_pc_agent.pid"
LOG_FILE="$TMP_DIR/wechat_pc_agent.log"
CONFIG_FILE="$TMP_DIR/wechat_pc_agent_config.json"
STATE_FILE="$TMP_DIR/wechat_pc_agent_state.json"
REPORT_FILE="$TMP_DIR/wechat_pc_agent_latest.json"
INTERVAL_SEC="${WECHAT_AGENT_INTERVAL_SEC:-}"

mkdir -p "$TMP_DIR"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE" || true)"
  if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then
    echo "WeChat PC agent is already running (PID: $PID)"
    exit 0
  fi
fi

python3 "$ROOT_DIR/scripts/wechat_pc_full_auto_agent.py" \
  --config "$CONFIG_FILE" \
  --state-file "$STATE_FILE" \
  --report-file "$REPORT_FILE" \
  --init-config-only >/dev/null

if [[ -z "$INTERVAL_SEC" ]]; then
  INTERVAL_SEC="$(python3 - "$CONFIG_FILE" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
try:
    payload = json.loads(path.read_text(encoding="utf-8"))
except Exception:
    payload = {}
value = payload.get("loop_interval_sec", 300)
try:
    number = int(value)
except Exception:
    number = 300
number = max(20, min(3600, number))
print(number)
PY
)"
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] wechat pc agent launcher start interval=${INTERVAL_SEC}s" >>"$LOG_FILE"

nohup bash -lc "
  cd '$ROOT_DIR'
  exec python3 '$ROOT_DIR/scripts/wechat_pc_full_auto_agent.py' \
    --loop \
    --interval-sec '$INTERVAL_SEC' \
    --config '$CONFIG_FILE' \
    --state-file '$STATE_FILE' \
    --report-file '$REPORT_FILE'
" >>"$LOG_FILE" 2>&1 &

LAUNCH_PID=$!
sleep 0.3
RUN_PID="$(pgrep -f "$ROOT_DIR/scripts/wechat_pc_full_auto_agent.py.*--loop" | tail -n 1 || true)"
if [[ -n "${RUN_PID:-}" ]] && kill -0 "$RUN_PID" 2>/dev/null; then
  echo "$RUN_PID" >"$PID_FILE"
else
  echo "$LAUNCH_PID" >"$PID_FILE"
fi
echo "WeChat PC agent started."
echo "PID: $(cat "$PID_FILE")"
echo "Log: $LOG_FILE"
