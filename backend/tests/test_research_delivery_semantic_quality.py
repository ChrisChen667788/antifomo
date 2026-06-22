from __future__ import annotations

from app.services.research_delivery_quality_service import evaluate_formal_document_sections


def _complete_sections(*, evidence_suffix: str = "") -> list[tuple[str, list[str]]]:
    suffix = f" {evidence_suffix}" if evidence_suffix else ""
    return [
        ("一、项目背景与编制依据", [f"依据现状调研说明立项背景。{suffix}"]),
        ("二、现状差距与需求分析", [f"梳理现状、业务流程和建设需求。{suffix}"]),
        ("三、建设目标与建设内容", [f"明确目标、范围、任务和功能。{suffix}"]),
        ("四、备选方案比选与推荐方案", [f"比较维持现状、分期建设和整体建设。{suffix}"]),
        ("五、总体架构与接口", [f"说明技术方案、系统边界、数据共享和接口。{suffix}"]),
        ("六、安全合规", [f"覆盖网络安全、数据安全、等保、密码和信创。{suffix}"]),
        ("七、实施采购与运营", [f"明确采购、进度、里程碑、验收、运维和组织机制。{suffix}"]),
        ("八、投资绩效与项目影响", [f"说明预算、资金、绩效、经济影响和社会影响。{suffix}"]),
        ("九、风险、证据矩阵与假设台账", [f"记录风险、来源追溯、待核验项和验收条件。{suffix}"]),
    ]


def _metric_map(profile):
    return {metric.key: metric for metric in profile.metrics}


def test_structure_only_cannot_receive_delivery_pass_without_concrete_evidence_anchors() -> None:
    profile = evaluate_formal_document_sections(
        _complete_sections(),
        review_target="feasibility_study",
        source_support_score=92,
        grounded_count=8,
        checklist_count=8,
        evidence_note_count=8,
    )

    metrics = _metric_map(profile)
    assert metrics["structure_completeness"].status == "pass"
    assert metrics["claim_evidence_traceability"].score <= 72
    assert profile.overall_score <= 83
    assert profile.status != "pass"
    assert any("主张—证据" in gap for gap in profile.gaps)


def test_source_navigation_pollution_hard_caps_delivery_quality() -> None:
    sections = _complete_sections()
    sections[1][1].append("网站首页 关于我们 联系我们 返回顶部 登录 注册")

    profile = evaluate_formal_document_sections(
        sections,
        review_target="feasibility_study",
        source_support_score=95,
        grounded_count=10,
        checklist_count=10,
        evidence_note_count=10,
    )

    metrics = _metric_map(profile)
    assert metrics["content_hygiene"].status == "fail"
    assert profile.overall_score <= 67
    assert profile.status == "fail"
    assert any("污染" in gap for gap in profile.gaps)


def test_traceable_claims_can_pass_when_structure_and_delivery_controls_are_complete() -> None:
    evidence = (
        "来源：https://example.gov.cn/procurement/2026/001；"
        "项目编号：GOV-AI-2026-001"
    )
    sections = _complete_sections(evidence_suffix=evidence)
    sections[7][1].append(
        "预算金额 520 万元，建设周期 12 个月。"
        "来源：https://example.gov.cn/procurement/2026/001；项目编号：GOV-AI-2026-001"
    )

    profile = evaluate_formal_document_sections(
        sections,
        review_target="feasibility_study",
        source_support_score=95,
        grounded_count=10,
        checklist_count=10,
        evidence_note_count=10,
    )

    metrics = _metric_map(profile)
    assert metrics["content_hygiene"].status == "pass"
    assert metrics["claim_evidence_traceability"].status == "pass"
    assert profile.overall_score >= 84
    assert profile.status == "pass"
