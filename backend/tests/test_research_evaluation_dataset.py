from __future__ import annotations

from collections import Counter
import json
from pathlib import Path

from app.services.research.evaluation_dataset import load_research_evaluation_dataset


def test_research_evaluation_dataset_has_one_hundred_versioned_unique_cases() -> None:
    manifest, cases = load_research_evaluation_dataset()

    assert manifest.dataset_id == "anti-fomo-research-golden-v1"
    assert manifest.version == "1.2.0"
    assert manifest.status == "locked"
    assert manifest.locked_at is not None
    assert manifest.locked_by
    assert len(manifest.content_sha256) == 64
    assert manifest.expected_case_count == 100
    assert len(cases) == 100
    assert len({case.case_id for case in cases}) == 100
    assert len(manifest.suites) == 10
    assert all(len(suite.cases) == 10 for suite in manifest.suites)


def test_research_evaluation_dataset_covers_quality_cost_latency_and_guardrails() -> None:
    manifest, cases = load_research_evaluation_dataset()
    required_metrics = set(manifest.required_metrics)
    behavior_counts = Counter(case.expected_behavior for case in cases)

    assert {
        "recall_at_5",
        "mrr",
        "ndcg_at_5",
        "citation_support_rate",
        "answer_correctness",
        "refusal_accuracy",
        "latency_ms",
        "estimated_cost_usd",
    } <= required_metrics
    assert behavior_counts["answer"] >= 70
    assert behavior_counts["guard"] >= 5
    assert behavior_counts["refuse"] >= 8
    assert all(case.required_sections for case in cases)
    assert all(case.metric_targets.keys() >= required_metrics for case in cases)
    assert all(case.curation_status == "locked" for case in cases)
    assert all(len(case.reference_answer_terms) >= 2 for case in cases)
    assert all(case.expected_source_domains for case in cases)
    assert all(case.reviewed_by and case.reviewed_at for case in cases)
    assert all(case.curation_notes and case.source_relevance_notes for case in cases)
    assert all(case.regions for case in cases)
    assert all(not ({value.casefold() for value in case.regions} & {"中国", "全国", "全球"}) for case in cases)


def test_scope_feedback_resolution_covers_all_requested_changes() -> None:
    resolution_path = (
        Path(__file__).resolve().parents[1]
        / "evaluation"
        / "research_scope_feedback_resolution_v1_2.json"
    )
    resolution = json.loads(resolution_path.read_text(encoding="utf-8"))

    assert resolution["summary"] == {
        "approved_cases": 21,
        "scope_revision_cases": 78,
        "unanswered_cases": 1,
        "unanswered_case_ids": ["transport-003"],
        "answer_term_changes": 0,
        "source_domain_changes": 0,
        "expected_behavior_changes": 0,
    }
    assert len(resolution["cases"]) == 78
    assert all(change["revised_regions"] for change in resolution["cases"].values())
    assert all(change["revised_entities"] for change in resolution["cases"].values())
