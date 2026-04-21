#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

if ! command -v python3.11 >/dev/null 2>&1; then
  echo "python3.11 is required. Install Python 3.11 first."
  exit 1
fi

cd "$BACKEND_DIR"

if [ ! -d ".venv311" ]; then
  python3.11 -m venv .venv311
fi

source .venv311/bin/activate
pip install -r requirements.txt

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

cd "$ROOT_DIR"
npm install

echo "Demo setup complete."
echo "Run backend:  npm run demo:backend"
echo "Run frontend: npm run demo:frontend"
