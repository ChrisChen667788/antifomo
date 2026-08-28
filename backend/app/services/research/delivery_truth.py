from __future__ import annotations

from app.schemas.research import ResearchDeliveryTruthOut, ResearchReportResponse
from app.services.content_extractor import normalize_text
from app.services.research.delivery_scope import requires_account_truth
from app.services.research.hard_failure_policy import evaluate_research_hard_failures
from app.services.research.organization_identity import org_surface_variants


_COMMERCIAL_SECTION_TOKENS = (
    "甲方",
    "账户",
    "商机",
    "项目",
    "预算",
    "招标",
    "投标",
    "销售",
    "方案",
    "机会",
    "采购",
)


def _is_uninitialized_scope_contract(contract: object) -> bool:
    """Recognize schema defaults on reports created before scope contracts existed."""

    if contract is None:
        return True
    return (
        not normalize_text(str(getattr(contract, "contract_id", "") or ""))
        and not normalize_text(str(getattr(contract, "keyword", "") or ""))
        and not normalize_text(str(getattr(contract, "research_focus", "") or ""))
        and not list(getattr(contract, "regions", []) or [])
        and not list(getattr(contract, "industries", []) or [])
        and not list(getattr(contract, "clients", []) or [])
        and str(getattr(contract, "task_type", "general_research") or "general_research") == "general_research"
        and str(getattr(contract, "status", "needs_clarification") or "needs_clarification") == "needs_clarification"
    )


def _has_verified_account(report: ResearchReportResponse) -> bool:
    pursuit = report.account_pursuit_pack
    if pursuit.status == "ready" and pursuit.verified_account_count >= 1 and pursuit.cards:
        return True
    if not report.top_target_accounts or report.research_evidence_gate.local_target_proof_count < 1:
        return False
    eligible_urls = {
        normalize_text(row.url)
        for row in report.research_source_admissions
        if row.decision == "accepted" and row.account_pursuit_eligible and normalize_text(row.url)
    }
    if not eligible_urls:
        return False
    for account in report.top_target_accounts:
        variants = [value.casefold() for value in org_surface_variants(account.name) if normalize_text(value)]
        if not variants:
            continue
        for source in report.sources:
            if normalize_text(source.url) not in eligible_urls:
                continue
            evidence_text = normalize_text(
                " ".join([source.title, source.snippet, source.search_query])
            ).casefold()
            if any(value in evidence_text for value in variants):
                return True
    return False


def build_delivery_truth(report: ResearchReportResponse) -> ResearchDeliveryTruthOut:
    """Produce the only delivery state that can authorize customer-facing output."""

    evidence_gate = report.research_evidence_gate
    citation_gate = report.research_citation_gate
    entity_gate = report.research_entity_authenticity_gate
    readiness = report.report_readiness
    contract = report.research_scope_contract
    diagnostics = report.source_diagnostics
    hard_failure = evaluate_research_hard_failures(report)
    account_task = requires_account_truth(contract)
    scope_contract_uninitialized = _is_uninitialized_scope_contract(contract)
    has_verified_account = _has_verified_account(report)
    reasons: list[str] = []
    gates: list[str] = []

    if diagnostics.generation_fallback_used or evidence_gate.status == "blocked_runtime_degraded":
        reasons.extend(hard_failure.reasons or ("正式生成或检索运行已降级。",))
        return ResearchDeliveryTruthOut(
            status="system_degraded",
            delivery_mode="evidence_recovery",
            formal_delivery_allowed=False,
            customer_material_allowed=False,
            decisive_reasons=list(dict.fromkeys(reasons))[:6],
            blocking_gate_keys=["runtime"],
            next_action="恢复正式模型和检索运行后，用全新证据重跑。",
        )

    if contract.status != "ready" and not scope_contract_uninitialized:
        return ResearchDeliveryTruthOut(
            status="awaiting_user",
            delivery_mode="evidence_recovery",
            formal_delivery_allowed=False,
            customer_material_allowed=False,
            decisive_reasons=["研究范围尚未锁定行业、区域、主体或具体场景。"],
            blocking_gate_keys=["scope"],
            next_action="补充目标区域、行业、客户类型或已有项目材料。",
        )

    if account_task and not has_verified_account:
        reasons.append("尚无同时具备本地归属、真实机构和采购/业主角色证据的目标账户。")
        if evidence_gate.external_benchmark_count:
            reasons.append("外部标杆只能用于对标，不得替代本地甲方机会证明。")
        return ResearchDeliveryTruthOut(
            status="awaiting_user",
            delivery_mode="evidence_recovery",
            formal_delivery_allowed=False,
            customer_material_allowed=False,
            decisive_reasons=reasons,
            blocking_gate_keys=["account_truth", "source_topology"],
            next_action="补检本地采购意向、招标公告、建设单位或业务牵头部门的原始页面。",
        )

    formal_allowed = bool(
        evidence_gate.formal_report_allowed
        and citation_gate.passed
        and (not entity_gate.enforced or entity_gate.passed)
        and not hard_failure.blocked
        and not scope_contract_uninitialized
        and readiness.status == "ready"
    )
    if formal_allowed:
        mode = "account_pursuit" if has_verified_account else "market_scan"
        return ResearchDeliveryTruthOut(
            status="formal",
            delivery_mode=mode,
            formal_delivery_allowed=True,
            customer_material_allowed=mode == "account_pursuit",
            section_confidence_cap="high",
            decisive_reasons=["证据、引用、实体和交付就绪度门均已通过。"],
            next_action="按交付模式进入客户评审或内部账户推进。",
        )

    if not evidence_gate.formal_report_allowed:
        gates.append("evidence")
        reasons.extend(evidence_gate.blockers)
    if not citation_gate.passed:
        gates.append("citation")
        reasons.extend(citation_gate.blockers)
    if entity_gate.enforced and not entity_gate.passed:
        gates.append("entity")
        reasons.extend(entity_gate.blockers)
    if readiness.status == "needs_evidence":
        gates.append("readiness")
        reasons.extend(readiness.reasons)
    if hard_failure.blocked:
        gates.append("hard_failure")
        reasons.extend(hard_failure.reasons)
    mode = "account_pursuit" if has_verified_account else "market_scan"
    return ResearchDeliveryTruthOut(
        status="provisional",
        delivery_mode=mode,
        formal_delivery_allowed=False,
        customer_material_allowed=False,
        decisive_reasons=list(dict.fromkeys(value for value in reasons if normalize_text(value)))[:6]
        or ["当前结论仍缺少正式交付所需的独立验证。"],
        blocking_gate_keys=list(dict.fromkeys(gates))[:6] or ["readiness"],
        next_action="仅以市场扫描或待补证材料使用，逐条关闭阻断门后再生成正式版本。",
    )


def apply_delivery_truth(report: ResearchReportResponse) -> ResearchReportResponse:
    truth = build_delivery_truth(report)
    readiness = report.report_readiness
    if truth.status == "formal":
        normalized_readiness = readiness.model_copy(
            update={"status": "ready", "actionable": True, "evidence_gate_passed": True}
        )
    elif truth.status == "provisional":
        normalized_readiness = readiness.model_copy(
            update={
                "status": "degraded",
                "score": min(int(readiness.score or 59), 59),
                "actionable": False,
                "evidence_gate_passed": False,
                "reasons": list(dict.fromkeys([*truth.decisive_reasons, *readiness.reasons]))[:6],
                "next_verification_steps": list(
                    dict.fromkeys([truth.next_action, *readiness.next_verification_steps])
                )[:6],
            }
        )
    else:
        normalized_readiness = readiness.model_copy(
            update={
                "status": "needs_evidence",
                "score": min(int(readiness.score or 40), 40),
                "actionable": False,
                "evidence_gate_passed": False,
                "reasons": list(dict.fromkeys([*truth.decisive_reasons, *readiness.reasons]))[:6],
                "next_verification_steps": list(
                    dict.fromkeys([truth.next_action, *readiness.next_verification_steps])
                )[:6],
            }
        )

    sections = []
    for section in report.sections:
        title = normalize_text(section.title)
        is_commercial = any(token in title for token in _COMMERCIAL_SECTION_TOKENS)
        if (truth.status == "formal" and truth.delivery_mode == "account_pursuit") or not is_commercial:
            sections.append(section)
            continue
        insufficiency = list(dict.fromkeys([*section.insufficiency_reasons, *truth.decisive_reasons]))[:5]
        sections.append(
            section.model_copy(
                update={
                    "status": "needs_evidence",
                    "confidence_tone": "low",
                    "confidence_label": "待补证",
                    "confidence_reason": truth.next_action,
                    "insufficiency_reasons": insufficiency,
                    "insufficiency_summary": truth.next_action,
                }
            )
        )
    return report.model_copy(
        update={
            "delivery_truth": truth,
            "report_readiness": normalized_readiness,
            "sections": sections,
        }
    )


def formal_delivery_allowed(report: ResearchReportResponse) -> bool:
    return bool(getattr(report, "delivery_truth", None) and report.delivery_truth.formal_delivery_allowed)
