from __future__ import annotations

from app.services.research.evaluation_dataset import (
    ResearchEvaluationCase,
    load_research_evaluation_dataset,
)
from app.services.research.evaluation_runner import (
    ResearchEvaluationObservation,
    ResearchEvaluationSourceObservation,
    run_research_evaluation,
    score_research_evaluation_case,
)


def _case(**changes) -> ResearchEvaluationCase:
    payload = {
        "case_id": "fixture-001",
        "dataset_id": "fixture",
        "dataset_version": "1.0.0",
        "curation_status": "locked",
        "suite_id": "fixture-suite",
        "category": "fixture",
        "keyword": "上海政务云预算",
        "research_focus": "核验预算和采购主体",
        "language": "zh-CN",
        "expected_methodology": "government_cloud",
        "expected_behavior": "answer",
        "regions": ["上海"],
        "entities": ["上海市数据局"],
        "required_terms": ["预算", "采购"],
        "reference_answer_terms": ["预算", "采购"],
        "expected_source_domains": ["gov.example.cn"],
        "expected_source_urls": [],
        "preferred_source_tiers": ["official"],
        "required_sections": ["项目与商机判断"],
        "metric_targets": {
            "recall_at_5": 0.8,
            "mrr": 0.7,
            "ndcg_at_5": 0.7,
            "citation_support_rate": 0.8,
            "answer_correctness": 0.8,
            "refusal_accuracy": 0.9,
            "latency_ms": 1000,
            "estimated_cost_usd": 0.1,
        },
        "reviewed_by": "test reviewer",
        "reviewed_at": "2026-06-14",
        "curation_notes": "Reviewed fixture behavior and expected answer terms.",
        "source_relevance_notes": "The fixture government domain is the primary source.",
    }
    payload.update(changes)
    return ResearchEvaluationCase.model_validate(payload)


def test_score_case_computes_retrieval_quality_cost_and_behavior() -> None:
    result = score_research_evaluation_case(
        _case(),
        ResearchEvaluationObservation(
            observed_behavior="answer",
            text="已核验预算窗口和采购主体。",
            section_titles=["项目与商机判断"],
            supported_section_count=1,
            section_count=1,
            sources=[
                ResearchEvaluationSourceObservation(
                    url="https://gov.example.cn/notices/1",
                    domain="gov.example.cn",
                    source_tier="official",
                )
            ],
            latency_ms=500,
            estimated_cost_usd=0.02,
        ),
    )

    assert result.status == "passed"
    assert result.metrics["recall_at_5"].value == 1.0
    assert result.metrics["mrr"].value == 1.0
    assert result.metrics["citation_support_rate"].value == 1.0
    assert result.metrics["answer_correctness"].value == 1.0
    assert result.required_section_coverage == 1.0


def test_partial_dataset_run_is_explicitly_not_release_gate_eligible() -> None:
    manifest, cases = load_research_evaluation_dataset()

    result = run_research_evaluation(
        manifest,
        cases[:2],
        lambda case: ResearchEvaluationObservation(
            observed_behavior=case.expected_behavior,
            text=" ".join(case.required_terms),
            section_titles=case.required_sections,
            supported_section_count=len(case.required_sections),
            section_count=len(case.required_sections),
            latency_ms=10,
            estimated_cost_usd=0.0,
        ),
    )

    assert result.release_gate_eligible is False
    assert result.release_gate_passed is False
    assert any("selected 2 of 100" in blocker for blocker in result.gate_blockers)
    assert result.aggregate_metrics["recall_at_5"].available is True


def test_locked_full_dataset_is_release_gate_eligible_with_complete_observations() -> None:
    manifest, cases = load_research_evaluation_dataset()

    result = run_research_evaluation(
        manifest,
        cases,
        lambda case: ResearchEvaluationObservation(
            observed_behavior=case.expected_behavior,
            text=" ".join(case.reference_answer_terms),
            section_titles=case.required_sections,
            supported_section_count=len(case.required_sections),
            section_count=len(case.required_sections),
            sources=[
                ResearchEvaluationSourceObservation(
                    url=f"https://{case.expected_source_domains[0]}/evidence",
                    domain=f"news.{case.expected_source_domains[0]}",
                    source_tier="official",
                )
            ],
            latency_ms=10,
            estimated_cost_usd=0.0,
        ),
    )

    assert result.release_gate_eligible is True
    assert result.release_gate_passed is True
    assert result.gate_blockers == []
    assert result.failed_case_count == 0
    assert result.error_case_count == 0
