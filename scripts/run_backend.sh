#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"

if [ -d "$BACKEND_DIR/.venv312" ]; then
  VENV_DIR="$BACKEND_DIR/.venv312"
elif [ -d "$BACKEND_DIR/.venv" ]; then
  VENV_DIR="$BACKEND_DIR/.venv"
elif [ -d "$BACKEND_DIR/.venv311" ]; then
  VENV_DIR="$BACKEND_DIR/.venv311"
else
  echo "Backend venv missing. Run: npm run demo:setup"
  exit 1
fi

cd "$BACKEND_DIR"
source "$VENV_DIR/bin/activate"

if [ ! -f ".env" ]; then
  cp .env.example .env
fi

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
