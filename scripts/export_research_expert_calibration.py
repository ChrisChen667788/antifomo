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

from app.services.research.evaluation_dataset import DATASET_PATH, load_research_evaluation_dataset  # noqa: E402
from app.services.research.expert_calibration import build_expert_calibration_template  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Export the 1.8.4 expert calibration workbook.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / ".tmp" / "research-evaluation-expert-calibration.json",
    )
    args = parser.parse_args()
    manifest, cases = load_research_evaluation_dataset(args.dataset)
    artifact = build_expert_calibration_template(manifest, cases)
    artifact.write_json(args.output)
    print(
        json.dumps(
            {
                "artifact": str(args.output),
                "dataset_id": manifest.dataset_id,
                "case_count": len(cases),
                "primary_assignment_count": len(cases),
                "secondary_blind_assignment_count": len(artifact.dual_review_case_ids),
                "quality_audit_count": len(artifact.quality_audits),
                "paired_model_prompt_evaluation_count": len(artifact.paired_model_prompt_evaluations),
                "customer_acceptance_sample_count": len(artifact.customer_acceptance_samples),
                "status": artifact.status,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
