#!/usr/bin/env python3
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.services.research.evaluation_dataset import (  # noqa: E402
    DATASET_PATH,
    ResearchEvaluationDatasetManifest,
    research_evaluation_content_sha256,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate reviewed research evaluation cases and write an immutable lock digest."
    )
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--locked-by", required=True)
    parser.add_argument("--policy-version", default="1.0")
    return parser


def main() -> int:
    args = _parser().parse_args()
    raw = json.loads(args.dataset.read_text(encoding="utf-8"))
    raw["status"] = "curated"
    raw["content_sha256"] = ""
    manifest = ResearchEvaluationDatasetManifest.model_validate(raw)
    manifest.status = "locked"
    manifest.locked_at = datetime.now(timezone.utc)
    manifest.locked_by = args.locked_by.strip()
    manifest.curation_policy_version = args.policy_version.strip()
    manifest.content_sha256 = research_evaluation_content_sha256(manifest)
    payload = manifest.model_dump(mode="json")
    args.dataset.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    ResearchEvaluationDatasetManifest.model_validate_json(args.dataset.read_text(encoding="utf-8"))
    print(
        json.dumps(
            {
                "dataset": str(args.dataset),
                "status": manifest.status,
                "case_count": sum(len(suite.cases) for suite in manifest.suites),
                "content_sha256": manifest.content_sha256,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
