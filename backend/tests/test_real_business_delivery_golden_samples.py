from __future__ import annotations

from app.services.delivery.market_intelligence import build_market_intelligence_pack
from app.services.research.delivery_golden_samples import load_delivery_golden_samples
from app.services.research.real_business_golden_samples import (
    build_real_business_research_report,
    load_real_business_delivery_golden_samples,
)
from app.services.research_solution_intelligence_service import build_solution_delivery_pack


EXPECTED_REAL_BUSINESS_SAMPLE_IDS = {
    "shanghai-medical-ai-2026",
    "shanghai-culture-tourism-ai-2026",
    "yangtze-delta-gov-ai-2026",
}


def test_real_business_delivery_golden_samples_are_source_backed_and_registered() -> None:
    samples = load_real_business_delivery_golden_samples()
    delivery_samples = load_delivery_golden_samples()

    assert {sample.sample_id for sample in samples} == EXPECTED_REAL_BUSINESS_SAMPLE_IDS
    assert EXPECTED_REAL_BUSINESS_SAMPLE_IDS <= {sample.sample_id for sample in delivery_samples}
    assert all(len(sample.sources) >= 3 for sample in samples)
    assert all(sample.acceptance.get("expected_golden_sample_id") == sample.sample_id for sample in samples)
    assert all(sample.acceptance.get("expected_quantitative_status") == "assumption_required" for sample in samples)
    assert all(any(source.source_tier == "official" for source in sample.sources) for sample in samples)
    assert all(source.url.startswith("https://") for sample in samples for source in sample.sources)


def test_real_business_policy_sources_do_not_create_fake_tender_projects() -> None:
    for sample in load_real_business_delivery_golden_samples():
        report = build_real_business_research_report(sample)
        market_pack = build_market_intelligence_pack(
            report,
            scenario=sample.scenario,
            target_customer=sample.target_customer,
            vertical_scene=sample.vertical_scene,
        )

        assert market_pack.tender_projects == []
        assert "政策" in market_pack.tender_keywords
        assert "试点" in market_pack.tender_keywords
        assert "招标" not in market_pack.tender_keywords
        assert "中标" not in market_pack.tender_keywords
        assert "政府采购" not in market_pack.source_scope_summary


def test_real_business_delivery_golden_samples_validate_current_delivery_pipeline() -> None:
    for sample in load_real_business_delivery_golden_samples():
        report = build_real_business_research_report(sample)
        pack = build_solution_delivery_pack(
            report,
            scenario=sample.scenario,
            target_customer=sample.target_customer,
            vertical_scene=sample.vertical_scene,
            supplemental_context="真实业务主题黄金样本验证。",
        )
        expected_document_kinds = set(sample.acceptance.get("required_document_kinds") or [])
        required_terms = list(sample.acceptance.get("required_pack_terms") or [])
        forbidden_terms = list(sample.acceptance.get("must_not_contain") or [])

        assert pack.source_support_score >= int(sample.acceptance.get("min_source_support_score") or 0)
        assert {document.document_kind for document in pack.compiled_documents} == expected_document_kinds
        assert all(document.sections for document in pack.compiled_documents)
        assert all(document.export_markdown for document in pack.compiled_documents)
        assert pack.client_ppt_outline[1].title == "2. 外部趋势与公开政策/试点参考"

        quantitative_model = pack.quantitative_decision_model
        assert quantitative_model.status == sample.acceptance.get("expected_quantitative_status")
        assert quantitative_model.alternative_options
        assert quantitative_model.tender_score_response_matrix
        assert len(quantitative_model.financial_scenarios) == 3
        assert all(scenario.capex_cny is None for scenario in quantitative_model.financial_scenarios)
        assert any(variable.variable_key == "capex" and variable.base_value is None for variable in quantitative_model.sensitivity_variables)

        challenge = pack.semantic_challenge
        assert challenge.golden_sample_id == sample.acceptance.get("expected_golden_sample_id")
        assert challenge.golden_sample_alignment_score >= 82
        assert challenge.high_severity_count == 0
        assert challenge.scope_drift_count == 0

        export_text = pack.export_markdown
        for term in required_terms:
            assert term in export_text
        for term in forbidden_terms:
            assert term not in export_text
        assert "量化决策模型" in export_text
        assert "四类专用文档编译器" in export_text
