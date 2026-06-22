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
    build_research_evaluation_review_template,
)


def main() -> int:
    parser = argparse.ArgumentParser(description="Export an independent review template.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT_ROOT / ".tmp" / "research-evaluation-independent-review.json",
    )
    args = parser.parse_args()
    manifest, cases = load_research_evaluation_dataset(args.dataset)
    artifact = build_research_evaluation_review_template(manifest, cases)
    artifact.write_json(args.output)
    print(
        json.dumps(
            {
                "artifact": str(args.output),
                "dataset_id": manifest.dataset_id,
                "dataset_version": manifest.version,
                "dataset_content_sha256": manifest.content_sha256,
                "case_count": len(cases),
                "review_status": artifact.review_status,
                "scope_context_included": True,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
