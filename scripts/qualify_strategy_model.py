from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_DIR = PROJECT_ROOT / "backend"
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import get_settings  # noqa: E402
from app.services.strategy_model_qualification_service import (  # noqa: E402
    DEFAULT_ARTIFACT_PATH,
    run_strategy_model_qualification,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a fixed-evidence strategy model A/B qualification.")
    parser.add_argument("--baseline", default="claude-opus-4-8")
    parser.add_argument("--candidate", default="claude-opus-5")
    parser.add_argument("--output", type=Path, default=DEFAULT_ARTIFACT_PATH)
    args = parser.parse_args()
    result = run_strategy_model_qualification(
        get_settings(),
        baseline_model=args.baseline,
        candidate_model=args.candidate,
        artifact_path=args.output,
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "pass" else 2


if __name__ == "__main__":
    raise SystemExit(main())
