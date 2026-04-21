#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8000}"
SMOKE_ARTIFACT_DIR="${SMOKE_ARTIFACT_DIR:-}"
SMOKE_REPORT_FILE="${SMOKE_REPORT_FILE:-}"
SMOKE_STAGE="bootstrap"
SMOKE_REQUEST_PAYLOAD='{"source_type":"text","title":"Smoke 测试","raw_content":"这是 smoke test 文本，用于验证内容处理链路是否可用。"}'

if [ -z "$SMOKE_ARTIFACT_DIR" ] && [ -n "$SMOKE_REPORT_FILE" ]; then
  SMOKE_ARTIFACT_DIR="$(dirname "$SMOKE_REPORT_FILE")"
fi

if [ -n "$SMOKE_ARTIFACT_DIR" ]; then
  mkdir -p "$SMOKE_ARTIFACT_DIR"
fi

if [ -n "$SMOKE_REPORT_FILE" ]; then
  mkdir -p "$(dirname "$SMOKE_REPORT_FILE")"
fi

SMOKE_HEALTH_FILE="${SMOKE_ARTIFACT_DIR:+$SMOKE_ARTIFACT_DIR/health.json}"
SMOKE_CREATE_FILE="${SMOKE_ARTIFACT_DIR:+$SMOKE_ARTIFACT_DIR/create-item.json}"
SMOKE_ITEMS_FILE="${SMOKE_ARTIFACT_DIR:+$SMOKE_ARTIFACT_DIR/items.json}"
SMOKE_REQUEST_FILE="${SMOKE_ARTIFACT_DIR:+$SMOKE_ARTIFACT_DIR/create-item-request.json}"

write_report() {
  SMOKE_REPORT_STATUS="$1" \
    SMOKE_REPORT_STAGE="$2" \
    SMOKE_REPORT_ERROR="${3:-}" \
    SMOKE_REPORT_FILE="$SMOKE_REPORT_FILE" \
    SMOKE_ARTIFACT_DIR="$SMOKE_ARTIFACT_DIR" \
    SMOKE_HEALTH_FILE="$SMOKE_HEALTH_FILE" \
    SMOKE_CREATE_FILE="$SMOKE_CREATE_FILE" \
    SMOKE_ITEMS_FILE="$SMOKE_ITEMS_FILE" \
    SMOKE_API_BASE="$API_BASE" \
    node <<'EOF'
const fs = require("fs");
const path = require("path");

const reportFile = process.env.SMOKE_REPORT_FILE;
if (!reportFile) {
  process.exit(0);
}

function readJson(filePath) {
  if (!filePath || !fs.existsSync(filePath)) {
    return null;
  }
  try {
    return JSON.parse(fs.readFileSync(filePath, "utf8"));
  } catch {
    return null;
  }
}

const health = readJson(process.env.SMOKE_HEALTH_FILE);
const created = readJson(process.env.SMOKE_CREATE_FILE);
const items = readJson(process.env.SMOKE_ITEMS_FILE);
const report = {
  status: process.env.SMOKE_REPORT_STATUS || "unknown",
  stage: process.env.SMOKE_REPORT_STAGE || "unknown",
  apiBase: process.env.SMOKE_API_BASE || null,
  artifactDir: process.env.SMOKE_ARTIFACT_DIR || null,
  healthStatus: health?.status ?? null,
  createdItemId: created?.id ?? null,
  createdItemStatus: created?.status ?? null,
  itemsCount: Array.isArray(items?.items) ? items.items.length : null,
  latestItemId: Array.isArray(items?.items) && items.items.length > 0 ? items.items[0].id ?? null : null,
  error: process.env.SMOKE_REPORT_ERROR || null,
};

fs.mkdirSync(path.dirname(reportFile), { recursive: true });
fs.writeFileSync(reportFile, `${JSON.stringify(report, null, 2)}\n`, "utf8");
EOF
}

trap 'exit_code=$?; if [ $exit_code -ne 0 ]; then write_report "failed" "$SMOKE_STAGE" "Smoke test failed at stage: $SMOKE_STAGE"; fi' EXIT

echo "[1/4] health check"
SMOKE_STAGE="health_check"
HEALTH_JSON="$(curl -fsS "$API_BASE/healthz")"
if [ -n "$SMOKE_HEALTH_FILE" ]; then
  printf '%s\n' "$HEALTH_JSON" > "$SMOKE_HEALTH_FILE"
fi
printf '%s\n' "$HEALTH_JSON"
echo

echo "[2/4] create demo item"
SMOKE_STAGE="create_item"
if [ -n "$SMOKE_REQUEST_FILE" ]; then
  printf '%s\n' "$SMOKE_REQUEST_PAYLOAD" > "$SMOKE_REQUEST_FILE"
fi
CREATE_JSON="$(curl -fsS -X POST "$API_BASE/api/items" \
  -H "Content-Type: application/json" \
  -d "$SMOKE_REQUEST_PAYLOAD")"
if [ -n "$SMOKE_CREATE_FILE" ]; then
  printf '%s\n' "$CREATE_JSON" > "$SMOKE_CREATE_FILE"
fi
printf '%s\n' "$CREATE_JSON"
echo

echo "[3/4] wait processing"
sleep 1

echo "[4/4] list items"
SMOKE_STAGE="list_items"
ITEMS_JSON="$(curl -fsS "$API_BASE/api/items?limit=5")"
if [ -n "$SMOKE_ITEMS_FILE" ]; then
  printf '%s\n' "$ITEMS_JSON" > "$SMOKE_ITEMS_FILE"
fi
printf '%s\n' "$ITEMS_JSON"
echo

SMOKE_STAGE="completed"
write_report "passed" "$SMOKE_STAGE"
echo "Smoke test completed."
