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

from app.services.industry_knowledge_retrieval_assurance import (  # noqa: E402
    DEFAULT_APPROVAL_PATH,
    DEFAULT_DRIFT_PATH,
    DEFAULT_SHADOW_PATH,
    export_industry_knowledge_retrieval_approval_template,
    export_industry_knowledge_retrieval_evidence_templates,
)
from app.services.industry_knowledge_retrieval_benchmark import DEFAULT_REVIEW_PATH  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create only missing retrieval-assurance templates; existing human evidence is never overwritten."
    )
    parser.add_argument("--approval", type=Path, default=DEFAULT_APPROVAL_PATH)
    parser.add_argument("--shadow", type=Path, default=DEFAULT_SHADOW_PATH)
    parser.add_argument("--drift", type=Path, default=DEFAULT_DRIFT_PATH)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW_PATH)
    parser.add_argument("--approval-only", action="store_true")
    args = parser.parse_args()
    try:
        approval = export_industry_knowledge_retrieval_approval_template(output_path=args.approval)
        output: dict[str, object] = {
            "approval_template_path": str(args.approval),
            "approval_decision": approval.get("decision", "pending"),
            "candidate_strategy": approval.get("candidate_strategy", ""),
            "warning": "This command does not approve, shadow-run, or promote a retrieval strategy.",
        }
        if not args.approval_only:
            output["runtime_templates"] = export_industry_knowledge_retrieval_evidence_templates(
                approval_path=args.approval,
                shadow_path=args.shadow,
                drift_path=args.drift,
                review_path=args.review,
            )
    except ValueError as exc:
        print(json.dumps({"status": "blocked", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 2
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
