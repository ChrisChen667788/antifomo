from __future__ import annotations

from app.schemas.research import ResearchEntityEvidenceOut
from app.services.research.delivery_evidence_ledger import build_delivery_evidence_ledger


def _official_evidence(
    *,
    title: str = "某市政务 AI 项目采购公告",
    url: str = "https://example.gov.cn/procurement/GOV-AI-2026-001",
    excerpt: str = "采购人：某市数据局。预算金额 520 万元，建设周期 12 个月。项目编号 GOV-AI-2026-001。",
) -> ResearchEntityEvidenceOut:
    return ResearchEntityEvidenceOut(
        title=title,
        url=url,
        source_label="政府采购公告",
        source_tier="official",
        anchor_text="GOV-AI-2026-001",
        excerpt=excerpt,
        confidence_tone="high",
    )


def test_claim_and_evidence_ids_are_stable_when_input_order_changes() -> None:
    rows = [
        ("投资估算", "预算金额 520 万元，来源：https://example.gov.cn/procurement/GOV-AI-2026-001"),
        ("实施计划", "建设周期 12 个月，项目编号：GOV-AI-2026-001"),
    ]
    evidence = [_official_evidence()]

    first = build_delivery_evidence_ledger(rows, evidence_links=evidence)
    second = build_delivery_evidence_ledger(list(reversed(rows)), evidence_links=list(reversed(evidence)))

    assert [claim.claim_id for claim in first.claims] == [claim.claim_id for claim in second.claims]
    assert [item.evidence_id for item in first.evidence] == [item.evidence_id for item in second.evidence]


def test_external_evidence_supports_matching_numeric_and_entity_claim() -> None:
    ledger = build_delivery_evidence_ledger(
        [("投资估算", "某市数据局项目预算金额 520 万元，建设周期 12 个月。")],
        evidence_links=[_official_evidence()],
        expected_entities=["某市数据局"],
    )

    claim = ledger.claims[0]
    assert claim.verification_status == "supported"
    assert any(relation.relation_type == "supports" for relation in claim.evidence_relations)
    assert ledger.high_confidence_coverage_percent == 100
    assert ledger.entity_consistency_score == 100
    assert ledger.numeric_consistency_score == 100


def test_entity_role_conflict_is_stable_and_blocks_ledger() -> None:
    ledger = build_delivery_evidence_ledger(
        [
            ("项目概况", "目标客户：甲市数据局。"),
            ("项目概况", "目标客户：乙市数据局。"),
        ],
        expected_entities=["甲市数据局"],
    )

    issues = [issue for issue in ledger.consistency_issues if issue.issue_type == "entity_role_conflict"]
    assert issues
    assert all(issue.issue_id.startswith("issue_") for issue in issues)
    assert any(issue.severity == "high" for issue in issues)
    assert ledger.entity_consistency_score < 100
    assert ledger.status == "fail"


def test_equivalent_amount_units_do_not_create_numeric_conflict() -> None:
    ledger = build_delivery_evidence_ledger(
        [
            ("投资估算", "项目预算金额 520 万元。"),
            ("投资估算", "项目预算金额 0.052 亿元。"),
        ]
    )

    assert not [issue for issue in ledger.consistency_issues if issue.issue_type.startswith("numeric_")]
    assert ledger.numeric_consistency_score == 100


def test_conflicting_budget_values_create_high_severity_numeric_issue() -> None:
    ledger = build_delivery_evidence_ledger(
        [
            ("投资估算", "项目预算金额 520 万元。"),
            ("投资估算", "项目预算金额 680 万元。"),
        ]
    )

    issues = [issue for issue in ledger.consistency_issues if issue.issue_type == "numeric_conflict"]
    assert len(issues) == 1
    assert issues[0].severity == "high"
    assert len(issues[0].claim_ids) == 2
    assert ledger.numeric_consistency_score < 100
    assert ledger.status == "fail"
