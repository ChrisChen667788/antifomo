#!/usr/bin/env python3
from __future__ import annotations

import argparse
from functools import partial
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = PROJECT_ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.core.config import get_settings  # noqa: E402
from app.services.research.evaluation_budget import (  # noqa: E402
    BudgetedResearchEvaluationExecutor,
    build_research_live_evaluation_plan,
)
from app.services.research.evaluation_dataset import (  # noqa: E402
    DATASET_PATH,
    load_research_evaluation_dataset,
)
from app.services.research.evaluation_runner import run_research_evaluation  # noqa: E402
from app.services.research.evaluation_review import (  # noqa: E402
    ResearchEvaluationReviewArtifact,
    validate_research_evaluation_review,
)
from app.services.research_evaluation_runtime import execute_research_evaluation_case  # noqa: E402


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate or execute the research evaluation dataset.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH)
    parser.add_argument("--execute", action="store_true", help="Run selected cases through the research workflow.")
    parser.add_argument("--limit", type=int, default=None, help="Run only the first N selected cases.")
    parser.add_argument("--case-id", action="append", default=[], help="Select one or more case IDs.")
    parser.add_argument("--suite-id", action="append", default=[], help="Select one or more suite IDs.")
    parser.add_argument("--output", type=Path, default=PROJECT_ROOT / ".tmp" / "research-evaluation.json")
    parser.add_argument(
        "--workflow-engine",
        choices=("deterministic", "langgraph", "langgraph_shadow"),
        default="langgraph",
    )
    parser.add_argument(
        "--allow-live-provider",
        action="store_true",
        help="Allow execution when a configured LLM route has a remote API key.",
    )
    parser.add_argument(
        "--budget-usd",
        type=float,
        default=None,
        help="Required approved budget ceiling when a live provider is configured.",
    )
    parser.add_argument(
        "--max-live-cases",
        type=int,
        default=5,
        help="Maximum live-provider cases per invocation.",
    )
    parser.add_argument(
        "--review",
        type=Path,
        default=None,
        help="Completed independent review artifact required for live-provider execution.",
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
    if args.suite_id:
        requested_suites = set(args.suite_id)
        selected = [case for case in selected if case.suite_id in requested_suites]
        missing_suites = sorted(requested_suites - {case.suite_id for case in cases})
        if missing_suites:
            raise SystemExit("unknown suite IDs: " + ", ".join(missing_suites))
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
    live_provider = _live_provider_enabled()
    if live_provider:
        if not args.allow_live_provider:
            raise SystemExit(
                "remote provider credentials are configured; pass --allow-live-provider to accept token cost"
            )
        if args.budget_usd is None:
            raise SystemExit("live-provider evaluation requires --budget-usd")
        if args.review is None:
            raise SystemExit("live-provider evaluation requires --review")
        review_artifact = ResearchEvaluationReviewArtifact.model_validate_json(
            args.review.read_text(encoding="utf-8")
        )
        review_validation = validate_research_evaluation_review(manifest, cases, review_artifact)
        if not review_validation.independent_review_complete:
            raise SystemExit(
                "independent review is incomplete: " + "; ".join(review_validation.blockers)
            )
        if args.max_live_cases < 1:
            raise SystemExit("--max-live-cases must be positive")
        if len(selected) > args.max_live_cases:
            raise SystemExit(
                f"selected {len(selected)} live cases; limit the batch to {args.max_live_cases} or fewer"
            )
        plan = build_research_live_evaluation_plan(
            manifest,
            selected,
            batch_size=args.max_live_cases,
            approved_budget_usd=args.budget_usd,
        )
        if not plan.budget_sufficient:
            raise SystemExit(
                f"approved budget ${args.budget_usd:.6f} is below the selected-case target ceiling "
                f"${plan.target_cost_ceiling_usd:.6f}"
            )

    executor = partial(execute_research_evaluation_case, workflow_engine=args.workflow_engine)
    if live_provider:
        executor = BudgetedResearchEvaluationExecutor(
            executor,
            approved_budget_usd=args.budget_usd,
        )
    result = run_research_evaluation(
        manifest,
        selected,
        executor,
    )
    result.write_json(args.output)
    print(
        json.dumps(
            {
                **summary,
                "artifact": str(args.output),
                "workflow_engine": args.workflow_engine,
                "release_gate_eligible": result.release_gate_eligible,
                "release_gate_passed": result.release_gate_passed,
                "gate_blockers": result.gate_blockers,
                "error_case_count": result.error_case_count,
                "approved_budget_usd": args.budget_usd if live_provider else None,
                "observed_cost_usd": (
                    executor.observed_cost_usd
                    if isinstance(executor, BudgetedResearchEvaluationExecutor)
                    else None
                ),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if result.error_case_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
