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
    ResearchEvaluationDatasetManifest,
)


DEFAULT_RESOLUTION_PATH = (
    PROJECT_ROOT / "backend" / "evaluation" / "research_scope_feedback_resolution_v1_2.json"
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply reviewed region/entity scope feedback to the research dataset."
    )
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--resolution", type=Path, default=DEFAULT_RESOLUTION_PATH)
    parser.add_argument("--target-version", default="1.2.0")
    args = parser.parse_args()

    raw = json.loads(args.dataset.read_text(encoding="utf-8"))
    resolution = json.loads(args.resolution.read_text(encoding="utf-8"))
    expected_digest = resolution["source_dataset_content_sha256"]
    if raw.get("content_sha256") != expected_digest:
        raise SystemExit(
            "dataset digest does not match the scope-feedback source; refusing to apply stale feedback"
        )

    cases_by_id = {
        case["case_id"]: case
        for suite in raw["suites"]
        for case in suite["cases"]
    }
    changes = resolution["cases"]
    if set(changes) - set(cases_by_id):
        raise SystemExit("scope-feedback resolution contains unknown case IDs")
    for case_id, change in changes.items():
        case = cases_by_id[case_id]
        if case.get("regions", []) != change["original_regions"]:
            raise SystemExit(f"case {case_id} original regions changed since review")
        if case.get("entities", []) != change["original_entities"]:
            raise SystemExit(f"case {case_id} original entities changed since review")
        case["regions"] = change["revised_regions"]
        case["entities"] = change["revised_entities"]
        case["curation_notes"] = (
            case.get("curation_notes", "").rstrip()
            + " Scope feedback applied on 2026-06-15: "
            + change["feedback"]
        ).strip()

    raw["version"] = args.target_version
    raw["status"] = "curated"
    raw["description"] = (
        "Curated 100-case research evaluation set with expert scope feedback applied to "
        "region and research-subject precision; behavior, answer terms, and source domains remain unchanged."
    )
    raw["locked_at"] = None
    raw["locked_by"] = ""
    raw["curation_policy_version"] = "1.1"
    raw["content_sha256"] = ""
    ResearchEvaluationDatasetManifest.model_validate(raw)
    args.dataset.write_text(
        json.dumps(raw, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "dataset": str(args.dataset),
                "version": raw["version"],
                "status": raw["status"],
                "scope_revision_count": len(changes),
                "resolution_id": resolution["resolution_id"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
