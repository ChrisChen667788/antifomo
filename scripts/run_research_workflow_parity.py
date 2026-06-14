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

from app.services.research.evaluation_dataset import (  # noqa: E402
    DATASET_PATH,
    load_research_evaluation_dataset,
)
from app.services.research.workflow_parity import run_research_workflow_parity  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the locked dataset through deterministic and LangGraph offline parity fixtures."
    )
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / ".tmp" / "research-workflow-parity.json",
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    manifest, cases = load_research_evaluation_dataset(args.dataset)
    result = run_research_workflow_parity(manifest, cases)
    result.write_json(args.output)
    print(
        json.dumps(
            {
                "dataset_id": result.dataset_id,
                "dataset_version": result.dataset_version,
                "dataset_status": result.dataset_status,
                "dataset_content_sha256": result.dataset_content_sha256,
                "selected_case_count": result.selected_case_count,
                "parity_rate": result.parity_rate,
                "production_gate_eligible": result.production_gate_eligible,
                "production_gate_passed": result.production_gate_passed,
                "gate_blockers": result.gate_blockers,
                "artifact": str(args.output),
                "scope": "offline orchestration parity; does not replace live retrieval quality evaluation",
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.production_gate_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
