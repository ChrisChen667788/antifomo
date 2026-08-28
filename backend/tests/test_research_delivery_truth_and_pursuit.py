from __future__ import annotations

from datetime import UTC, datetime

from app.schemas.research import (
    ResearchCitationGateOut,
    ResearchDeliveryTruthOut,
    ResearchEntityAuthenticityGateOut,
    ResearchEntityEvidenceOut,
    ResearchEvidenceGateOut,
    ResearchReportReadinessOut,
    ResearchReportResponse,
    ResearchReportSectionOut,
    ResearchScopeContractOut,
    ResearchSolutionArchitectureBlueprintSectionOut,
    ResearchSolutionArchitectureReadinessOut,
    ResearchSolutionDeliveryPackOut,
    ResearchSourceAdmissionOut,
    ResearchSourceOut,
    ResearchRankedEntityOut,
)
from app.services.research.account_pursuit import build_account_pursuit_pack
from app.services.research.architecture_traceability import build_customer_architecture_traceability
from app.services.research.commercial_bid_engineering import build_commercial_bid_pack
from app.services.research.delivery_truth import apply_delivery_truth
from app.services.research.clarification import attach_research_interaction
from app.services.research.report_readiness import ReportReadinessDependencies, build_report_readiness


def _verified_account_report() -> ResearchReportResponse:
    evidence = ResearchEntityEvidenceOut(
        title="上海市文化和旅游局智慧场馆人工智能采购意向",
        url="https://sh.gov.cn/tourism/ai-procurement",
        source_label="上海市人民政府",
        source_tier="official",
        excerpt="2026年采购人：上海市文化和旅游局，拟采购智慧场馆人工智能导览与服务平台。",
    )
    return ResearchReportResponse(
        keyword="2026年长三角文旅人工智能商机调研",
        report_title="长三角文旅人工智能商机调研",
        executive_summary="已取得本地采购主体线索。",
        consulting_angle="先核验采购范围与系统边界。",
        source_count=1,
        generated_at=datetime(2026, 8, 10, tzinfo=UTC),
        research_scope_contract=ResearchScopeContractOut(
            task_type="account_intelligence",
            regions=["长三角"],
            industries=["文旅文博"],
            status="ready",
        ),
        sources=[
            ResearchSourceOut(
                title=evidence.title,
                url=evidence.url,
                domain="sh.gov.cn",
                snippet=evidence.excerpt,
                search_query="上海 文旅 人工智能 采购意向",
                source_type="procurement",
                content_status="extracted",
                source_label=evidence.source_label,
                source_tier="official",
            )
        ],
        research_source_admissions=[
            ResearchSourceAdmissionOut(
                source_id="src_sh_tourism",
                title=evidence.title,
                url=evidence.url,
                domain="sh.gov.cn",
                source_tier="official",
                decision="accepted",
                source_topology="local_target_proof",
                evidence_lane="decision",
                local_scope_match=True,
                current_signal=True,
                primary_origin=True,
                url_safe=True,
                formal_claim_eligible=True,
                account_pursuit_eligible=True,
            )
        ],
        research_evidence_gate=ResearchEvidenceGateOut(
            enforced=True,
            status="evidence_ready",
            passed=True,
            formal_report_allowed=True,
            solution_delivery_allowed=True,
            local_target_proof_count=1,
            local_decision_source_count=2,
        ),
        research_citation_gate=ResearchCitationGateOut(enforced=True, status="pass", passed=True),
        research_entity_authenticity_gate=ResearchEntityAuthenticityGateOut(enforced=True, status="pass", passed=True),
        report_readiness=ResearchReportReadinessOut(status="ready", score=82, actionable=True, evidence_gate_passed=True),
        top_target_accounts=[ResearchRankedEntityOut(name="上海市文化和旅游局", score=91, evidence_links=[evidence])],
        target_accounts=["上海市文化和旅游局"],
        budget_signals=["上海市文化和旅游局采购意向待披露预算金额。"],
        tender_timeline=["上海市文化和旅游局 2026 年采购意向核验窗口。"],
    )


def test_delivery_truth_caps_commercial_sections_when_citation_gate_fails() -> None:
    report = _verified_account_report().model_copy(
        update={
            "research_citation_gate": ResearchCitationGateOut(
                enforced=True,
                status="fail",
                passed=False,
                blockers=["关键主张证据覆盖不足。"],
            ),
            "sections": [
                ResearchReportSectionOut(
                    title="销售策略",
                    items=["立即按高概率商机投入。"],
                    status="ready",
                    confidence_tone="high",
                    confidence_label="高置信度",
                )
            ],
        }
    )

    guarded = apply_delivery_truth(report)

    assert guarded.delivery_truth.status == "provisional"
    assert guarded.delivery_truth.formal_delivery_allowed is False
    assert guarded.report_readiness.status == "degraded"
    assert guarded.sections[0].status == "needs_evidence"
    assert guarded.sections[0].confidence_tone == "low"


def test_default_legacy_scope_contract_never_authorizes_formal_delivery() -> None:
    report = _verified_account_report().model_copy(
        update={"research_scope_contract": ResearchScopeContractOut()}
    )

    guarded = apply_delivery_truth(report)

    assert guarded.delivery_truth.status == "provisional"
    assert guarded.delivery_truth.formal_delivery_allowed is False
    assert guarded.report_readiness.status == "degraded"


def test_verified_account_generates_pursuit_commercial_and_architecture_traceability_packs() -> None:
    report = _verified_account_report()
    pursuit = build_account_pursuit_pack(report)
    report = report.model_copy(update={"account_pursuit_pack": pursuit})
    commercial = build_commercial_bid_pack(report)
    solution = ResearchSolutionDeliveryPackOut(
        architecture_readiness=ResearchSolutionArchitectureReadinessOut(
            blueprint_sections=[
                ResearchSolutionArchitectureBlueprintSectionOut(
                    title="模型、数据与集成层",
                    purpose="以 API-first 接入客户业务系统、知识库和统一身份认证。",
                )
            ]
        )
    )
    traceability = build_customer_architecture_traceability(report, pack=solution)

    assert pursuit.status == "ready"
    assert pursuit.verified_account_count == 1
    assert pursuit.cards[0].account_name == "上海市文化和旅游局"
    assert commercial.status == "ready_for_review"
    assert commercial.buyer_map[0].status == "verified"
    assert traceability.target_account == "上海市文化和旅游局"
    assert traceability.facts
    assert traceability.assumptions
    assert traceability.recommendations[0].classification == "recommendation"


def test_account_readiness_requires_named_local_target_proof_and_two_decision_sources() -> None:
    report = _verified_account_report().model_copy(
        update={
            "research_evidence_gate": ResearchEvidenceGateOut(
                enforced=True,
                status="evidence_ready",
                passed=True,
                formal_report_allowed=True,
                local_target_proof_count=0,
                local_decision_source_count=1,
                external_benchmark_count=4,
            )
        }
    )

    readiness = build_report_readiness(
        report,
        deps=ReportReadinessDependencies(
            dedupe_strings=lambda values, limit: list(dict.fromkeys(values))[:limit],
            sanitize_entity_row=lambda _field, value: value,
            is_actionable_budget_row=lambda value: bool(value),
        ),
    )

    assert readiness.status == "needs_evidence"
    assert readiness.actionable is False
    assert readiness.evidence_gate_passed is False
    assert "具体账户" in readiness.missing_axes


def test_formal_market_scan_caps_customer_facing_commercial_sections() -> None:
    report = _verified_account_report().model_copy(
        update={
            "top_target_accounts": [],
            "target_accounts": [],
            "research_scope_contract": ResearchScopeContractOut(
                task_type="industry_research",
                regions=["长三角"],
                industries=["文旅文博"],
                status="ready",
            ),
            "sections": [
                ResearchReportSectionOut(
                    title="招投标推进策略",
                    items=["以本地采购窗口推进方案。"],
                    status="ready",
                    confidence_tone="high",
                    confidence_label="高置信度",
                ),
                ResearchReportSectionOut(
                    title="行业趋势",
                    items=["行业公开政策持续推进。"],
                    status="ready",
                    confidence_tone="high",
                    confidence_label="高置信度",
                ),
            ],
        }
    )

    guarded = apply_delivery_truth(report)

    assert guarded.delivery_truth.status == "formal"
    assert guarded.delivery_truth.delivery_mode == "market_scan"
    assert guarded.sections[0].status == "needs_evidence"
    assert guarded.sections[0].confidence_tone == "low"
    assert guarded.sections[1].status == "ready"


def test_delivery_truth_requires_the_named_account_to_match_eligible_local_evidence() -> None:
    report = _verified_account_report().model_copy(
        update={
            "sources": [
                ResearchSourceOut(
                    title="苏州市文化广电和旅游局智慧场馆人工智能采购意向",
                    url="https://sh.gov.cn/tourism/ai-procurement",
                    domain="sh.gov.cn",
                    snippet="2026年采购人：苏州市文化广电和旅游局，拟采购智慧场馆人工智能导览平台。",
                    search_query="苏州 文旅 人工智能 采购意向",
                    source_type="procurement",
                    content_status="extracted",
                    source_label="上海市人民政府",
                    source_tier="official",
                )
            ]
        }
    )

    guarded = apply_delivery_truth(report)

    assert guarded.delivery_truth.status == "awaiting_user"
    assert guarded.delivery_truth.delivery_mode == "evidence_recovery"


def test_resolved_awaiting_user_truth_cannot_fall_back_to_legacy_formal_fields() -> None:
    report = _verified_account_report().model_copy(
        update={
            "delivery_truth": ResearchDeliveryTruthOut(
                status="awaiting_user",
                delivery_mode="evidence_recovery",
                formal_delivery_allowed=False,
                decisive_reasons=["缺少已验证的本地甲方。"],
                blocking_gate_keys=["account_truth"],
                next_action="补充采购人原始页面。",
            )
        }
    )

    resolved = attach_research_interaction(report)

    assert resolved.interaction_state == "awaiting_user"
    assert resolved.clarification_packet.formal_delivery_allowed is False
