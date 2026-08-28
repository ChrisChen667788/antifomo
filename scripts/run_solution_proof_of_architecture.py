#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.delivery.executable_validation import (  # noqa: E402
    DEFAULT_PROOF_ARTIFACT_PATH,
    write_reference_proof_artifact,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the 1.9.1 minimum vertical proof-of-architecture suite.")
    parser.add_argument("--output", type=Path, default=DEFAULT_PROOF_ARTIFACT_PATH)
    args = parser.parse_args()
    payload = write_reference_proof_artifact(args.output)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload["machine_status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
