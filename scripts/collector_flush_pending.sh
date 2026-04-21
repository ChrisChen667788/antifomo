#!/usr/bin/env bash
set -euo pipefail

API_BASE="${COLLECTOR_API_BASE:-http://127.0.0.1:8000}"
LIMIT="${1:-200}"

curl -sf -X POST "${API_BASE%/}/api/collector/process-pending?limit=${LIMIT}" \
  -H "Content-Type: application/json"
