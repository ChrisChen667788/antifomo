from __future__ import annotations

from app.services.research.delivery_golden_samples import (
    load_delivery_golden_samples,
    match_delivery_golden_sample,
)


def test_delivery_golden_samples_are_versioned_and_reviewable() -> None:
    samples = load_delivery_golden_samples()

    assert len(samples) >= 6
    assert {sample.sample_id for sample in samples} >= {
        "gov-ai-service-center",
        "tourism-aigc-guide",
        "smart-manufacturing-quality-platform",
        "shanghai-medical-ai-2026",
        "shanghai-culture-tourism-ai-2026",
        "yangtze-delta-gov-ai-2026",
    }
    assert all(sample.document_types for sample in samples)
    assert all(len(sample.required_scope_terms) >= 5 for sample in samples)
    assert all(len(sample.forbidden_scope_terms) >= 4 for sample in samples)
    assert all(sample.min_alignment_score >= 80 for sample in samples)


def test_delivery_golden_sample_match_scores_scope_and_forbidden_terms() -> None:
    matched = match_delivery_golden_sample(
        [
            "项目概况：某市数据局建设政务服务 AI 助手。",
            "需求分析：覆盖政务服务、智能问答、知识库和工单协同。",
            "技术方案：支持接口、数据安全、等保和热线业务协同。",
            "实施路径、投资、风险和证据台账同步建立。",
        ],
        expected_scope_terms=["政务AI", "某市数据局", "政务服务中心"],
        document_kind="project_proposal",
    )

    assert matched.sample is not None
    assert matched.sample.sample_id == "gov-ai-service-center"
    assert matched.score >= 82
    assert "景区" not in matched.forbidden_hits

    drifted = match_delivery_golden_sample(
        [
            "项目概况：某市数据局建设政务服务 AI 助手。",
            "建设内容：重点建设景区游客导览、门票营销和数字人导览。",
        ],
        expected_scope_terms=["政务AI", "某市数据局", "政务服务中心"],
        document_kind="project_proposal",
    )

    assert drifted.sample is not None
    assert drifted.sample.sample_id == "gov-ai-service-center"
    assert drifted.score < matched.score
    assert {"景区", "游客", "数字人导览"} & set(drifted.forbidden_hits)
