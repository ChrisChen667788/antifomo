from __future__ import annotations

from app.services.research_evaluation_service import build_golden_research_evaluation


def test_golden_research_evaluation_scores_fixed_cases() -> None:
    evaluation = build_golden_research_evaluation()
    case_map = {case.case_id: case for case in evaluation.cases}

    assert evaluation.total_cases >= 3
    assert evaluation.passed_cases >= 2
    assert evaluation.average_professional_score > 0
    assert evaluation.average_intelligence_value_score > 0
    assert evaluation.summary_lines

    assert case_map["gov-cloud-budget"].passed is True
    assert case_map["gov-cloud-budget"].expected_methodology == "government_cloud"
    assert case_map["gov-cloud-budget"].target_support_rate == 1.0
    assert case_map["compute-llm-capacity"].expected_methodology == "compute_llm"
    assert case_map["weak-generic"].passed is True
    assert case_map["weak-generic"].issues
