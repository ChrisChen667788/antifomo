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

from app.core.config import get_settings  # noqa: E402
from app.services.research.evaluation_dataset import (  # noqa: E402
    DATASET_PATH,
    load_research_evaluation_dataset,
)
from app.services.research.evaluation_runner import (  # noqa: E402
    execute_research_evaluation_case,
    run_research_evaluation,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate or execute the research evaluation dataset.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--execute", action="store_true", help="Run selected cases through the research workflow.")
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N selected cases.")
    parser.add_argument("--case-id", action="append", default=[], help="Select one or more case IDs.")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / ".tmp" / "research-evaluation.json")
    parser.add_argument(
        "--allow-live-provider",
        action="store_true",
        help="Allow execution when a configured LLM route has a remote API key.",
    )
    return parser


def _live_provider_enabled() -> bool:
    settings = get_settings()
    generation_live = settings.llm_provider != "mock" and bool(settings.openai_api_key)
    strategy_live = settings.strategy_llm_provider != "mock" and bool(settings.strategy_openai_api_key)
    return generation_live or strategy_live


def main() -> int:
    args = _parser().parse_args()
    manifest, cases = load_research_evaluation_dataset(args.dataset)
    selected = cases
    if args.case_id:
        requested = set(args.case_id)
        selected = [case for case in selected if case.case_id in requested]
        missing = sorted(requested - {case.case_id for case in selected})
        if missing:
            raise SystemExit("unknown case IDs: " + ", ".join(missing))
    if args.limit is not None:
        if args.limit < 1:
            raise SystemExit("--limit must be positive")
        selected = selected[: args.limit]

    summary = {
        "dataset_id": manifest.dataset_id,
        "dataset_version": manifest.version,
        "dataset_status": manifest.status,
        "case_count": len(cases),
        "selected_case_count": len(selected),
        "required_metrics": manifest.required_metrics,
    }
    if not args.execute:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    if _live_provider_enabled() and not args.allow_live_provider:
        raise SystemExit(
            "remote provider credentials are configured; pass --allow-live-provider to accept token cost"
        )

    result = run_research_evaluation(manifest, selected, execute_research_evaluation_case)
    result.write_json(args.output)
    print(
        json.dumps(
            {
                **summary,
                "artifact": str(args.output),
                "release_gate_eligible": result.release_gate_eligible,
                "release_gate_passed": result.release_gate_passed,
                "gate_blockers": result.gate_blockers,
                "error_case_count": result.error_case_count,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.error_case_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
