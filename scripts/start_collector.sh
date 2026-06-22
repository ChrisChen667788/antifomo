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

RUN_PID="$(
  ROOT_DIR="$ROOT_DIR" SOURCE_FILE="$SOURCE_FILE" TMP_DIR="$TMP_DIR" LOG_FILE="$LOG_FILE" \
    INTERVAL_SEC="$INTERVAL_SEC" FLUSH_LIMIT="$FLUSH_LIMIT" python3 - <<'PY'
import os
import subprocess

root = os.environ["ROOT_DIR"]
tmp_dir = os.environ["TMP_DIR"]
log = open(os.environ["LOG_FILE"], "ab", buffering=0)
proc = subprocess.Popen(
    [
        "node",
        os.path.join(root, "scripts", "desktop_wechat_collector.mjs"),
        "--loop",
        "--source-file",
        os.environ["SOURCE_FILE"],
        "--state-file",
        os.path.join(tmp_dir, "wechat_collector_state.json"),
        "--report-file",
        os.path.join(tmp_dir, "wechat_collector_latest.md"),
        "--submit-mode",
        "browser-batch",
        "--batch-submit-size",
        "10",
        "--interval-sec",
        os.environ["INTERVAL_SEC"],
        "--flush-limit",
        os.environ["FLUSH_LIMIT"],
        "--daily-hours",
        "24",
        "--daily-limit",
        "12",
        "--daily-report",
        os.path.join(tmp_dir, "collector_daily_summary.md"),
    ],
    stdin=subprocess.DEVNULL,
    stdout=log,
    stderr=subprocess.STDOUT,
    cwd=root,
    start_new_session=True,
)
print(proc.pid)
PY
)"
echo "$RUN_PID" >"$PID_FILE"
sleep 0.3
if ! kill -0 "$RUN_PID" 2>/dev/null; then
  echo "Collector failed to start. Check log: $LOG_FILE"
  rm -f "$PID_FILE"
  exit 1
fi
echo "Collector started."
echo "PID: $(cat "$PID_FILE")"
echo "Log: $LOG_FILE"
