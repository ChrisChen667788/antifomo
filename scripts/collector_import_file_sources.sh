#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
API_BASE="${COLLECTOR_API_BASE:-http://127.0.0.1:8000}"
SOURCE_FILE="${1:-$ROOT_DIR/.tmp/wechat_collector_sources.txt}"

if [[ ! -f "$SOURCE_FILE" ]]; then
  echo "source file not found: $SOURCE_FILE"
  exit 1
fi

PAYLOAD="$(
  python3 - "$SOURCE_FILE" <<'PY'
import json
import re
import sys
from pathlib import Path

source_file = Path(sys.argv[1])
urls = []
seen = set()
for raw in source_file.read_text(encoding="utf-8").splitlines():
    line = raw.strip()
    if not line or line.startswith("#"):
        continue
    if not re.match(r"^https?://", line, flags=re.I):
        continue
    if line in seen:
        continue
    seen.add(line)
    urls.append(line)

print(json.dumps({"urls": urls, "enabled": True}, ensure_ascii=False))
PY
)"

if [[ -z "$PAYLOAD" ]]; then
  echo "no valid urls found in source file"
  exit 0
fi

curl -sf -X POST "${API_BASE%/}/api/collector/sources/import" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD"

echo
echo "source file imported to collector sources."
