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

from app.services.industry_knowledge_retrieval_benchmark import (  # noqa: E402
    DATASET_PATH,
    DEFAULT_REVIEW_PATH,
    REVIEW_PROTOCOL_VERSION,
    STRATEGY_KEYS,
    _dataset_digest,
    _load_human_review_scores,
    industry_knowledge_retrieval_benchmark_digest,
    load_industry_knowledge_retrieval_benchmark_dataset,
    load_latest_industry_knowledge_retrieval_benchmark,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate the report human-review evidence for retrieval ranking A/B.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW_PATH)
    args = parser.parse_args()
    _payload, cases = load_industry_knowledge_retrieval_benchmark_dataset(args.dataset)
    current_benchmark = load_latest_industry_knowledge_retrieval_benchmark(dataset_path=args.dataset, review_path=args.review)
    scores, warnings = _load_human_review_scores(
        args.review,
        dataset_sha256=_dataset_digest(args.dataset),
        benchmark_digest=industry_knowledge_retrieval_benchmark_digest(current_benchmark),
    )
    review_payload: dict[str, object] = {}
    try:
        parsed = json.loads(args.review.read_text(encoding="utf-8"))
        if isinstance(parsed, dict):
            review_payload = parsed
    except (OSError, json.JSONDecodeError):
        pass
    expected = {(case.case_id, strategy) for case in cases for strategy in STRATEGY_KEYS}
    missing = sorted(f"{case_id}:{strategy}" for case_id, strategy in expected - set(scores))
    output = {
        "review": str(args.review),
        "expected_entry_count": len(expected),
        "valid_score_count": len(scores),
        "complete": not warnings and not missing,
        "review_protocol_version": review_payload.get("review_protocol_version", ""),
        "expected_review_protocol_version": REVIEW_PROTOCOL_VERSION,
        "benchmark_digest": review_payload.get("benchmark_digest", ""),
        "expected_benchmark_digest": industry_knowledge_retrieval_benchmark_digest(current_benchmark),
        "reviewer_name_present": bool(str(review_payload.get("reviewer_name") or "").strip()),
        "reviewer_role_present": bool(str(review_payload.get("reviewer_role") or "").strip()),
        "reviewed_at_present": bool(str(review_payload.get("reviewed_at") or "").strip()),
        "independence_attestation_present": bool(str(review_payload.get("independence_attestation") or "").strip()),
        "conflict_disclosure_present": bool(str(review_payload.get("conflict_disclosure") or "").strip()),
        "warnings": warnings,
        "missing_entries": missing,
    }
    print(json.dumps(output, ensure_ascii=False, indent=2))
    return 0 if output["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
