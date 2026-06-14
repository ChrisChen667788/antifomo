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
from app.services.research.evaluation_review import (  # noqa: E402
    ResearchEvaluationReviewArtifact,
    validate_research_evaluation_review,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate an independent review artifact.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--review", type=Path, required=True)
    args = parser.parse_args()
    manifest, cases = load_research_evaluation_dataset(args.dataset)
    artifact = ResearchEvaluationReviewArtifact.model_validate_json(
        args.review.read_text(encoding="utf-8")
    )
    result = validate_research_evaluation_review(manifest, cases, artifact)
    print(json.dumps(result.model_dump(mode="json"), ensure_ascii=False, indent=2))
    return 0 if result.independent_review_complete else 1


if __name__ == "__main__":
    raise SystemExit(main())
