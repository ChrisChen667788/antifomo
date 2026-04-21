#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_URL="${API_URL:-http://127.0.0.1:8000}"

echo "[1/4] codebuddy version"
if command -v codebuddy >/dev/null 2>&1; then
  codebuddy --version || true
else
  echo "codebuddy: not found"
fi

echo
echo "[2/4] codebuddy auth probe"
if command -v codebuddy >/dev/null 2>&1; then
  codebuddy -p "Reply with OK only." --output-format text || true
else
  echo "codebuddy: not found"
fi

echo
echo "[3/4] backend health"
python3 - <<PY
from urllib.request import urlopen, Request

for url in ["${API_URL}/healthz", "${API_URL}/api/workbuddy/health"]:
    print("URL", url)
    try:
        with urlopen(Request(url, headers={"User-Agent":"Mozilla/5.0"}), timeout=10) as resp:
            print(resp.status)
            print(resp.read().decode("utf-8", "replace")[:1600])
    except Exception as exc:
        print("ERR", repr(exc))
    print()
PY

echo "[4/4] next step"
echo "If auth probe shows 'Authentication required', run:"
echo "  codebuddy"
echo "Then enter:"
echo "  /login"
