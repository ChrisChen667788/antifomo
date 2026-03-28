#!/usr/bin/env bash
set -euo pipefail

API_BASE="${API_BASE:-http://127.0.0.1:8000}"

echo "[1/4] health check"
curl -s "$API_BASE/healthz"
echo

echo "[2/4] create demo item"
curl -s -X POST "$API_BASE/api/items" \
  -H "Content-Type: application/json" \
  -d '{"source_type":"text","title":"Smoke 测试","raw_content":"这是 smoke test 文本，用于验证内容处理链路是否可用。"}'
echo

echo "[3/4] wait processing"
sleep 1

echo "[4/4] list items"
curl -s "$API_BASE/api/items?limit=5"
echo

echo "Smoke test completed."
