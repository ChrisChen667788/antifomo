#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMP_DIR="$ROOT_DIR/.tmp"
PID_FILE="$TMP_DIR/collector.pid"
LOG_FILE="$TMP_DIR/collector.log"
SOURCE_FILE="$TMP_DIR/wechat_collector_sources.txt"
INTERVAL_SEC="${COLLECT_INTERVAL_SEC:-300}"
FLUSH_LIMIT="${COLLECT_FLUSH_LIMIT:-80}"

mkdir -p "$TMP_DIR"

if [[ -f "$PID_FILE" ]]; then
  PID="$(cat "$PID_FILE" || true)"
  if [[ -n "${PID:-}" ]] && kill -0 "$PID" 2>/dev/null; then
    echo "Collector is already running (PID: $PID)"
    exit 0
  fi
fi

if [[ ! -f "$SOURCE_FILE" ]]; then
  cat >"$SOURCE_FILE" <<'EOF'
# 每行一个公众号源页面 URL（可写文章索引页或直接文章 URL）
# https://mp.weixin.qq.com/s/xxxxxxxx
EOF
fi

echo "[$(date '+%Y-%m-%d %H:%M:%S')] collector launcher start interval=${INTERVAL_SEC}s" >>"$LOG_FILE"

nohup bash -lc "
  cd '$ROOT_DIR'
  exec node '$ROOT_DIR/scripts/desktop_wechat_collector.mjs' \
    --loop \
    --source-file '$SOURCE_FILE' \
    --state-file '$TMP_DIR/wechat_collector_state.json' \
    --report-file '$TMP_DIR/wechat_collector_latest.md' \
    --interval-sec '$INTERVAL_SEC' \
    --flush-limit '$FLUSH_LIMIT' \
    --daily-hours 24 \
    --daily-limit 12 \
    --daily-report '$TMP_DIR/collector_daily_summary.md'
" >>"$LOG_FILE" 2>&1 &

LAUNCH_PID=$!
sleep 0.3
RUN_PID="$(pgrep -f "$ROOT_DIR/scripts/desktop_wechat_collector.mjs.*--loop" | tail -n 1 || true)"
if [[ -n "${RUN_PID:-}" ]] && kill -0 "$RUN_PID" 2>/dev/null; then
  echo "$RUN_PID" >"$PID_FILE"
else
  echo "$LAUNCH_PID" >"$PID_FILE"
fi
echo "Collector started."
echo "PID: $(cat "$PID_FILE")"
echo "Log: $LOG_FILE"
