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

from app.services.research.evaluation_review import (  # noqa: E402
    ResearchEvaluationReviewArtifact,
    finalize_research_evaluation_review,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Finalize and digest an independent review artifact.")
    parser.add_argument("--review", type=Path, required=True)
    parser.add_argument("--reviewer-name", required=True)
    parser.add_argument("--reviewer-role", required=True)
    parser.add_argument("--attestation", required=True)
    args = parser.parse_args()
    artifact = ResearchEvaluationReviewArtifact.model_validate_json(
        args.review.read_text(encoding="utf-8")
    )
    finalize_research_evaluation_review(
        artifact,
        reviewer_name=args.reviewer_name,
        reviewer_role=args.reviewer_role,
        attestation=args.attestation,
    )
    artifact.write_json(args.review)
    print(
        json.dumps(
            {
                "artifact": str(args.review),
                "review_status": artifact.review_status,
                "review_content_sha256": artifact.review_content_sha256,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
