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
    DEFAULT_ARTIFACT_PATH,
    DEFAULT_REVIEW_PATH,
    run_industry_knowledge_retrieval_benchmark,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the fixed local industry-knowledge retrieval ranking A/B.")
    parser.add_argument("--library-dir", type=Path, default=None)
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_ARTIFACT_PATH)
    parser.add_argument("--review", type=Path, default=DEFAULT_REVIEW_PATH)
    parser.add_argument("--preview", action="store_true", help="Do not persist the benchmark output or review template.")
    args = parser.parse_args()
    result = run_industry_knowledge_retrieval_benchmark(
        library_dir=args.library_dir,
        dataset_path=args.dataset,
        artifact_path=args.output,
        review_path=args.review,
        persist=not args.preview,
    )
    print(
        json.dumps(
            {
                "benchmark_id": result["benchmark_id"],
                "dataset_version": result.get("dataset_version"),
                "benchmark_digest": result.get("benchmark_digest"),
                "knowledge_base_generation_id": result.get("knowledge_base_generation_id"),
                "status": result["status"],
                "case_count": result["case_count"],
                "arms": [
                    {
                        "strategy": arm["strategy"],
                        "metrics": {metric["key"]: metric["value"] for metric in arm["metrics"]},
                        "rerank_applied_case_count": arm["rerank_applied_case_count"],
                        "rerank_backend": arm["rerank_backend"],
                        "rerank_model": arm.get("rerank_model", ""),
                    }
                    for arm in result["arms"]
                ],
                "promotion": result["promotion"],
                "artifact_path": result["artifact_path"],
                "review_template_path": result.get("review_template_path"),
                "review_sample_directory": result.get("review_sample_directory"),
                "warnings": result["warnings"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result["status"] in {"ready", "partial"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
