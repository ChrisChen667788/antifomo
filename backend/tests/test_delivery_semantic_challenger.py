from __future__ import annotations

from app.schemas.research import ResearchEntityEvidenceOut
from app.services.research.delivery_evidence_ledger import build_delivery_evidence_ledger
from app.services.research.delivery_semantic_challenger import build_delivery_semantic_challenge


def _official_evidence() -> ResearchEntityEvidenceOut:
    return ResearchEntityEvidenceOut(
        title="某市政务服务AI助手公开招标公告",
        url="https://example.gov.cn/procurement/GOV-AI-2026-001",
        source_label="政府采购公告",
        source_tier="official",
        anchor_text="GOV-AI-2026-001",
        excerpt="采购人：某市数据局。预算金额 520 万元，建设周期 12 个月，包含知识库、智能问答、工单协同、接口和等保三级。",
        confidence_tone="high",
    )


def _challenge(
    rows: list[tuple[str, str]],
    *,
    expected_scope_terms: list[str] | None = None,
    expected_entities: list[str] | None = None,
    with_evidence: bool = True,
):
    ledger = build_delivery_evidence_ledger(
        rows,
        evidence_links=[_official_evidence()] if with_evidence else [],
        expected_entities=expected_entities or ["某市数据局"],
    )
    return build_delivery_semantic_challenge(
        rows,
        evidence_ledger=ledger,
        expected_scope_terms=expected_scope_terms or ["政务AI", "某市数据局", "政务服务中心"],
        expected_entities=expected_entities or ["某市数据局"],
        document_kind="project_proposal",
    )


def test_semantic_challenger_passes_clean_traceable_project_sample() -> None:
    rows = [
        ("一、项目概况", "目标客户：某市数据局，建设政务服务 AI 助手和政务服务中心热线协同能力。"),
        ("二、需求分析", "覆盖政务服务、智能问答、知识库和工单协同，来源：https://example.gov.cn/procurement/GOV-AI-2026-001。"),
        ("三、建设目标", "建设知识库问答、接口集成、数据安全和等保三级能力。"),
        ("四、技术方案", "技术方案包含热线接口、工单协同、数据安全和等保三级。"),
        ("五、实施路径", "建设周期 12 个月，项目编号：GOV-AI-2026-001。"),
        ("六、投资", "预算金额 520 万元，项目编号：GOV-AI-2026-001。"),
        ("七、风险", "预算、接口和安全合规需以采购公告和客户确认口径为准。"),
        ("附：证据台账", "证据锚点 GOV-AI-2026-001 绑定预算、建设周期、接口和等保要求。"),
    ]

    challenge = _challenge(rows)

    assert challenge.status in {"pass", "watch"}
    assert challenge.high_severity_count == 0
    assert challenge.scope_drift_count == 0
    assert challenge.golden_sample_id == "gov-ai-service-center"
    assert challenge.golden_sample_alignment_score >= 82


def test_semantic_challenger_blocks_scope_drift_from_locked_project_scope() -> None:
    rows = [
        ("一、项目概况", "目标客户：某市数据局，建设政务服务 AI 助手。"),
        ("三、建设内容", "建设景区游客导览、门票营销和数字人导览平台，面向文旅集团运营。"),
    ]

    challenge = _challenge(rows, with_evidence=False)

    assert challenge.status == "fail"
    assert challenge.scope_drift_count >= 1
    assert any(issue.issue_type == "scope_drift" for issue in challenge.issues)


def test_semantic_challenger_detects_cross_section_entity_conflict() -> None:
    rows = [
        ("一、项目概况", "目标客户：某市数据局。"),
        ("四、实施计划", "建设单位：乙市文旅集团。"),
    ]

    challenge = _challenge(rows, with_evidence=False)

    assert challenge.status == "fail"
    assert any(issue.issue_type == "entity_conflict" for issue in challenge.issues)
    assert challenge.cross_section_conflict_count >= 1


def test_semantic_challenger_detects_cross_section_numeric_conflict() -> None:
    rows = [
        ("一、项目概况", "目标客户：某市数据局。"),
        ("五、投资估算", "项目预算金额 520 万元。"),
        ("七、实施计划", "本项目预算金额 680 万元。"),
    ]

    challenge = _challenge(rows, with_evidence=False)

    assert challenge.status == "fail"
    assert any(issue.issue_type in {"cross_section_conflict", "numeric_conflict"} for issue in challenge.issues)
    assert challenge.cross_section_conflict_count >= 1


def test_semantic_challenger_flags_unsupported_high_confidence_claims() -> None:
    rows = [
        ("一、项目概况", "目标客户：某市数据局。"),
        ("五、投资估算", "预算金额 520 万元，建设周期 12 个月。"),
    ]

    challenge = _challenge(rows, with_evidence=False)

    assert any(issue.issue_type == "unsupported_high_confidence_claim" for issue in challenge.issues)
    assert challenge.status in {"watch", "fail"}
