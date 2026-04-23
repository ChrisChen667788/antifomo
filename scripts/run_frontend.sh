#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

cd "$ROOT_DIR"

if [ ! -d "node_modules" ]; then
  npm install
fi

FRONTEND_PORT="${FRONTEND_PORT:-3010}"

NEXT_PUBLIC_API_BASE_URL="${NEXT_PUBLIC_API_BASE_URL:-http://localhost:8000}" npm run dev -- --port "$FRONTEND_PORT"
