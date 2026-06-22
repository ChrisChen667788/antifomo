#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

source "$ROOT_DIR/scripts/backend_python.sh"

if ! BACKEND_PYTHON="$(select_backend_python "$BACKEND_DIR")"; then
  echo "Complete backend environment missing. Run: npm run demo:setup"
  exit 1
fi

cd "$BACKEND_DIR"

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

"$BACKEND_PYTHON" -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
