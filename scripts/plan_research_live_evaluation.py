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

from app.services.research.evaluation_budget import build_research_live_evaluation_plan  # noqa: E402
from app.services.research.evaluation_dataset import (  # noqa: E402
    DATASET_PATH,
    load_research_evaluation_dataset,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Plan bounded live-provider evaluation batches.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--batch-size", type=int, default=5)
    parser.add_argument("--budget-usd", type=float, default=None)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / ".tmp" / "research-live-evaluation-plan.json",
    )
    args = parser.parse_args()
    manifest, cases = load_research_evaluation_dataset(args.dataset)
    plan = build_research_live_evaluation_plan(
        manifest,
        cases,
        batch_size=args.batch_size,
        approved_budget_usd=args.budget_usd,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({**plan.model_dump(mode="json"), "artifact": str(args.output)}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
