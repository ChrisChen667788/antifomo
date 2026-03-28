#!/usr/bin/env bash
set -euo pipefail

API_BASE="${COLLECTOR_API_BASE:-http://127.0.0.1:8000}"
HOURS="${1:-24}"
LIMIT="${2:-12}"
OUT_FILE="${3:-.tmp/collector_daily_summary.md}"

mkdir -p "$(dirname "$OUT_FILE")"

JSON="$(curl -sf "${API_BASE%/}/api/collector/daily-summary?hours=${HOURS}&limit=${LIMIT}")"
echo "$JSON" | python3 -c "import json,sys;print(json.load(sys.stdin).get('markdown',''))" >"$OUT_FILE"

echo "collector daily summary saved to: $OUT_FILE"
