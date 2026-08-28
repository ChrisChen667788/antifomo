from __future__ import annotations

from hashlib import sha256
from typing import Iterable

from app.schemas.research import (
    ResearchClarificationOptionOut,
    ResearchClarificationPacketOut,
    ResearchClarificationQuestionOut,
    ResearchEvidenceGateOut,
    ResearchInteractionState,
    ResearchRecoveryOptionOut,
    ResearchReportResponse,
    ResearchScopeContractOut,
    ResearchSourceOut,
)
from app.services.content_extractor import normalize_text


def build_accepted_snapshot_digest(sources: Iterable[ResearchSourceOut]) -> str:
    rows = sorted(
        {
            "|".join(
                [
                    normalize_text(source.url),
                    normalize_text(source.title),
                    normalize_text(source.source_tier),
                    normalize_text(source.source_origin),
                ]
            )
            for source in sources
            if normalize_text(source.url) or normalize_text(source.title)
        }
    )
    if not rows:
        return ""
    return sha256("\n".join(rows).encode("utf-8")).hexdigest()


def is_provisional_evidence_eligible(
    gate: ResearchEvidenceGateOut,
    contract: ResearchScopeContractOut,
) -> bool:
    if (
        gate.status != "evidence_gap"
        or contract.status != "ready"
        or gate.minimum_source_count <= 0
    ):
        return False
    blockers = " ".join(gate.blockers)
    if (
        "采购人" in blockers
        or "建设单位" in blockers
        or "reranker" in blockers.casefold()
        or "运行降级" in blockers
    ):
        return False
    return bool(
        gate.accepted_source_count >= gate.minimum_source_count - 1
        and gate.official_source_count >= gate.minimum_official_source_count
        and gate.unique_domain_count >= gate.minimum_unique_domain_count
        and gate.question_coverage_percent >= gate.minimum_question_coverage_percent
    )


def _has_substantive_output(report: ResearchReportResponse) -> bool:
    if not normalize_text(report.executive_summary):
        return False
    return any(
        section.items and section.title not in {"证据缺口诊断", "候选证据复核清单"}
        for section in report.sections
    )


def _has_resolved_delivery_truth(report: ResearchReportResponse) -> bool:
    """Distinguish the schema default on legacy rows from a 2.3.4+ decision."""

    delivery_truth = getattr(report, "delivery_truth", None)
    if not delivery_truth or getattr(delivery_truth, "framework", "") != "research_delivery_truth_v1":
        return False
    return bool(
        delivery_truth.status != "awaiting_user"
        or delivery_truth.formal_delivery_allowed
        or delivery_truth.customer_material_allowed
        or delivery_truth.decisive_reasons
        or delivery_truth.blocking_gate_keys
        or normalize_text(delivery_truth.next_action)
    )


def _formal_delivery_allowed(report: ResearchReportResponse) -> bool:
    delivery_truth = getattr(report, "delivery_truth", None)
    if _has_resolved_delivery_truth(report):
        return bool(delivery_truth.formal_delivery_allowed)
    entity_gate = report.research_entity_authenticity_gate
    return bool(
        report.research_evidence_gate.formal_report_allowed
        and report.research_citation_gate.passed
        and (not entity_gate.enforced or entity_gate.passed)
        and report.report_readiness.status != "needs_evidence"
        and not report.source_diagnostics.generation_fallback_used
    )


def resolve_research_interaction_state(report: ResearchReportResponse) -> ResearchInteractionState:
    delivery_truth = getattr(report, "delivery_truth", None)
    if _has_resolved_delivery_truth(report):
        if delivery_truth.status == "formal":
            return "ready"
        if delivery_truth.status == "system_degraded":
            return "system_degraded"
        if delivery_truth.status == "provisional":
            return "provisional" if _has_substantive_output(report) else "blocked"
        return "awaiting_user"
    gate = report.research_evidence_gate
    if gate.status == "blocked_runtime_degraded" or report.source_diagnostics.generation_fallback_used:
        return "system_degraded"
    if not gate.formal_report_allowed:
        if is_provisional_evidence_eligible(gate, report.research_scope_contract) and _has_substantive_output(report):
            return "provisional"
        return "awaiting_user"
    if not _formal_delivery_allowed(report):
        return "provisional" if _has_substantive_output(report) else "blocked"
    return "ready"


def _scope_question(report: ResearchReportResponse) -> ResearchClarificationQuestionOut:
    contract = report.research_scope_contract
    missing_labels: list[str] = []
    if not contract.regions:
        missing_labels.append("区域")
    if not contract.industries:
        missing_labels.append("行业")
    if contract.task_type == "account_intelligence" and not contract.clients:
        missing_labels.append("目标机构")
    missing_text = "、".join(missing_labels) or "研究对象与边界"
    return ResearchClarificationQuestionOut(
        question_id="scope_definition",
        input_kind="short_text",
        prompt=f"请补充本次研究的{missing_text}。",
        reason="明确研究边界后，系统才能只保留同主题证据。",
        placeholder="例如：浙江省文旅行业，目标机构为某市文化和旅游局，关注 2025-2027 年项目。",
    )


def _buyer_question() -> ResearchClarificationQuestionOut:
    return ResearchClarificationQuestionOut(
        question_id="target_organization",
        input_kind="short_text",
        prompt="本次需要重点研究哪一个具体采购人、建设单位或主管部门？",
        reason="账户情报必须至少锁定一个可核验的责任主体。",
        placeholder="填写机构全称，必要时补充地区或上级主管单位。",
    )


def _source_question(*, official_gap: bool) -> ResearchClarificationQuestionOut:
    return ResearchClarificationQuestionOut(
        question_id="supporting_sources",
        input_kind="file_or_url",
        prompt=(
            "请补充 1-3 条官网、政策、采购公告或项目材料。"
            if official_gap
            else "请补充可核验的网址或项目材料，系统会保留已有证据并差量续跑。"
        ),
        reason="现有来源接近门槛，但仍不足以支持正式交付。",
        placeholder="可粘贴多个 http(s) 链接，或上传 PDF、DOCX、TXT、MD 文件。",
        accepted_file_types=[".pdf", ".docx", ".txt", ".md", ".csv", ".json"],
    )


def _coverage_question(report: ResearchReportResponse) -> ResearchClarificationQuestionOut:
    axes = [
        node.axis
        for node in report.research_question_tree.questions
        if node.coverage_status != "covered"
    ][:3]
    return ResearchClarificationQuestionOut(
        question_id="missing_analysis_axes",
        input_kind="multi_choice" if axes else "short_text",
        prompt="哪些缺口最值得优先补齐？",
        reason="系统将只重建受这些缺口影响的检索和章节。",
        placeholder="也可以直接描述必须回答的问题。",
        options=[
            ResearchClarificationOptionOut(value=axis, label=axis)
            for axis in axes
        ],
    )


def build_research_clarification_packet(
    report: ResearchReportResponse,
    *,
    state: ResearchInteractionState | None = None,
) -> ResearchClarificationPacketOut:
    resolved_state = state or resolve_research_interaction_state(report)
    gate = report.research_evidence_gate
    active = resolved_state != "ready"
    if not active:
        return ResearchClarificationPacketOut(
            active=False,
            interaction_state="ready",
            title="研报已满足交付条件",
            summary="证据、引用和交付质量检查均已通过。",
            accepted_source_count=gate.accepted_source_count,
            minimum_source_count=gate.minimum_source_count,
            evidence_snapshot_digest=build_accepted_snapshot_digest(report.sources),
            formal_delivery_allowed=True,
        )

    questions: list[ResearchClarificationQuestionOut] = []
    blockers = " ".join(gate.blockers)
    if resolved_state != "system_degraded":
        if report.research_scope_contract.status != "ready":
            questions.append(_scope_question(report))
        if "采购人" in blockers or "建设单位" in blockers:
            questions.append(_buyer_question())
        source_gap = gate.accepted_source_count < gate.minimum_source_count
        official_gap = gate.official_source_count < gate.minimum_official_source_count
        domain_gap = gate.unique_domain_count < gate.minimum_unique_domain_count
        if source_gap or official_gap or domain_gap:
            questions.append(_source_question(official_gap=official_gap))
        if gate.question_coverage_percent < gate.minimum_question_coverage_percent:
            questions.append(_coverage_question(report))
    questions = questions[:3]

    can_view_provisional = resolved_state == "provisional"
    if resolved_state == "system_degraded":
        reason_code = "system_runtime_degraded"
        title = "系统能力暂时降级"
        summary = "无需补充业务信息。恢复模型或语义检索服务后，可从当前证据快照重试。"
        recovery_options = [
            ResearchRecoveryOptionOut(
                action="retry_system",
                label="从当前证据重试",
                description="不重新丢弃已收集来源。",
                recommended=True,
            )
        ]
    elif can_view_provisional:
        reason_code = "near_threshold"
        title = "已生成可阅读草稿，还差少量证据"
        summary = (
            f"已采纳 {gate.accepted_source_count}/{gate.minimum_source_count} 条来源。"
            "草稿可供判断方向，但保存、导出和正式解决方案仍受保护。"
        )
        recovery_options = [
            ResearchRecoveryOptionOut(
                action="submit_answers",
                label="补充资料并续跑",
                description="保留当前证据，只补检缺口并重建受影响章节。",
                recommended=True,
            ),
            ResearchRecoveryOptionOut(
                action="continue_search",
                label="让系统继续查找",
                description="使用当前缺口自动扩展检索一次。",
            ),
            ResearchRecoveryOptionOut(
                action="view_provisional",
                label="先查看受限草稿",
                description="不会解除正式交付保护。",
            ),
        ]
    else:
        reason_code = "clarification_required"
        title = "需要少量补充后继续"
        summary = (
            f"已保留 {gate.accepted_source_count} 条有效来源。"
            "回答下列问题或补充材料后，系统会从当前进度继续，不会整轮重做。"
        )
        recovery_options = [
            ResearchRecoveryOptionOut(
                action="submit_answers",
                label="提交补充并续跑",
                description="系统会复用当前证据快照。",
                recommended=True,
            ),
            ResearchRecoveryOptionOut(
                action="continue_search",
                label="继续自动查找",
                description="适合暂时没有材料可补充的情况。",
            ),
        ]
    return ResearchClarificationPacketOut(
        active=True,
        interaction_state=resolved_state,
        reason_code=reason_code,
        title=title,
        summary=summary,
        accepted_source_count=gate.accepted_source_count,
        minimum_source_count=gate.minimum_source_count,
        evidence_snapshot_digest=build_accepted_snapshot_digest(report.sources),
        can_view_provisional=can_view_provisional,
        formal_delivery_allowed=False,
        system_retryable=resolved_state == "system_degraded",
        questions=questions,
        recovery_options=recovery_options,
        next_steps=[
            "已有来源会固定为父任务证据快照。",
            "只补检未覆盖问题并重建受影响章节。",
            "所有用户补充来源都会标记来源血缘。",
        ],
    )


def attach_research_interaction(report: ResearchReportResponse) -> ResearchReportResponse:
    state = resolve_research_interaction_state(report)
    return report.model_copy(
        update={
            "interaction_state": state,
            "clarification_packet": build_research_clarification_packet(report, state=state),
        }
    )


def require_formal_research_delivery(
    report: ResearchReportResponse,
) -> ResearchReportResponse:
    resolved = attach_research_interaction(report)
    if not resolved.clarification_packet.formal_delivery_allowed:
        raise ValueError(
            "当前研报仍是受限草稿；请补齐证据并通过引用、实体和交付质量检查后再保存或导出。"
        )
    return resolved
