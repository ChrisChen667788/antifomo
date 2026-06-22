from __future__ import annotations

import pytest

from app.services.research.evaluation_budget import (
    BudgetedResearchEvaluationExecutor,
    build_research_live_evaluation_plan,
)
from app.services.research.evaluation_dataset import load_research_evaluation_dataset
from app.services.research.evaluation_review import (
    build_research_evaluation_review_template,
    finalize_research_evaluation_review,
    validate_research_evaluation_review,
)
from app.services.research.evaluation_runner import ResearchEvaluationObservation


def test_independent_review_requires_complete_approval_and_valid_digest() -> None:
    manifest, cases = load_research_evaluation_dataset()
    artifact = build_research_evaluation_review_template(manifest, cases)

    assert artifact.cases[0].regions == cases[0].regions
    assert artifact.cases[0].entities == cases[0].entities

    pending = validate_research_evaluation_review(manifest, cases, artifact)

    assert pending.independent_review_complete is False
    assert pending.pending_case_count == 100
    assert any("expected approved" in blocker for blocker in pending.blockers)

    for case_review in artifact.cases:
        case_review.decision = "approved"
        case_review.notes = "已核对行为标签、答案锚点和首方来源域名。"
    finalize_research_evaluation_review(
        artifact,
        reviewer_name="Independent domain reviewer",
        reviewer_role="Public-sector and enterprise AI research reviewer",
        attestation="I independently reviewed every case against the locked dataset criteria.",
    )

    approved = validate_research_evaluation_review(manifest, cases, artifact)

    assert approved.independent_review_complete is True
    assert approved.approved_case_count == 100
    assert approved.blockers == []

    artifact.cases[0].notes = "tampered after finalization"
    tampered = validate_research_evaluation_review(manifest, cases, artifact)
    assert tampered.independent_review_complete is False
    assert any("digest" in blocker for blocker in tampered.blockers)

    artifact = build_research_evaluation_review_template(manifest, cases)
    artifact.cases[0].regions = ["altered-region"]
    altered_scope = validate_research_evaluation_review(manifest, cases, artifact)
    assert any("changed locked context" in blocker for blocker in altered_scope.blockers)

    artifact = build_research_evaluation_review_template(manifest, cases)
    artifact.cases[0].expected_source_domains = ["altered.example.org"]
    altered_context = validate_research_evaluation_review(manifest, cases, artifact)
    assert any("changed locked context" in blocker for blocker in altered_context.blockers)


def test_independent_review_rejects_the_dataset_locker_as_reviewer() -> None:
    manifest, cases = load_research_evaluation_dataset()
    artifact = build_research_evaluation_review_template(manifest, cases)
    for case_review in artifact.cases:
        case_review.decision = "approved"
        case_review.notes = "Reviewed against the locked behavior and source criteria."
    finalize_research_evaluation_review(
        artifact,
        reviewer_name=manifest.locked_by,
        reviewer_role="Maintainer",
        attestation="I reviewed all cases and confirm the current locked labels and sources.",
    )

    result = validate_research_evaluation_review(manifest, cases, artifact)

    assert result.independent_review_complete is False
    assert any("must differ" in blocker for blocker in result.blockers)


def test_live_evaluation_plan_batches_cases_and_requires_sufficient_budget() -> None:
    manifest, cases = load_research_evaluation_dataset()
    selected = cases[:7]
    required_budget = sum(case.metric_targets["estimated_cost_usd"] for case in selected)

    insufficient = build_research_live_evaluation_plan(
        manifest,
        selected,
        batch_size=5,
        approved_budget_usd=required_budget - 0.01,
    )
    sufficient = build_research_live_evaluation_plan(
        manifest,
        selected,
        batch_size=5,
        approved_budget_usd=required_budget,
    )

    assert sufficient.batch_count == 2
    assert [len(batch.case_ids) for batch in sufficient.batches] == [5, 2]
    assert sufficient.target_cost_ceiling_usd == pytest.approx(required_budget)
    assert insufficient.budget_sufficient is False
    assert sufficient.budget_sufficient is True


def test_budgeted_executor_stops_after_unpriced_or_over_budget_result() -> None:
    manifest, cases = load_research_evaluation_dataset()
    observations = iter(
        [
            ResearchEvaluationObservation(estimated_cost_usd=0.05),
            ResearchEvaluationObservation(estimated_cost_usd=None),
        ]
    )
    executor = BudgetedResearchEvaluationExecutor(
        lambda case: next(observations),
        approved_budget_usd=0.1,
    )

    executor(cases[0])
    assert executor.observed_cost_usd == pytest.approx(0.05)
    with pytest.raises(RuntimeError, match="pricing is unavailable"):
        executor(cases[1])
    with pytest.raises(RuntimeError, match="pricing is unavailable"):
        executor(cases[2])

    over_budget = BudgetedResearchEvaluationExecutor(
        lambda case: ResearchEvaluationObservation(estimated_cost_usd=0.11),
        approved_budget_usd=0.1,
    )
    with pytest.raises(RuntimeError, match="exceeded"):
        over_budget(cases[0])
    with pytest.raises(RuntimeError, match="exceeded"):
        over_budget(cases[1])
