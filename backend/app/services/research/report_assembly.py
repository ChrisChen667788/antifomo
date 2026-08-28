from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import re
from typing import Any

from app.schemas.research import (
    ResearchEntityGraphOut,
    ResearchEvidenceGateOut,
    ResearchFollowupContextOut,
    ResearchFollowupDiagnosticsOut,
    ResearchQuestionTreeOut,
    ResearchReportResponse,
    ResearchScopeContractOut,
    ResearchSourceAdmissionOut,
    ResearchSourceDiagnosticsOut,
)
from app.services.llm_parser import ResearchReportResult
from app.services.content_extractor import normalize_text
from app.services.research.entity_ranking import ResearchEntityRankingSets
from app.services.research.source_documents import SourceDocument


_ORGANIZATION_TITLE_SUFFIXES = (
    "集团",
    "公司",
    "人民政府",
    "政府",
    "办公厅",
    "办公室",
    "数据局",
    "管理局",
    "委员会",
    "中心",
    "检察院",
    "法院",
    "研究院",
    "厅",
    "院",
    "署",
    "所",
    "站",
    "局",
    "委",
    "办",
)
_PLACEHOLDER_TITLE_TOKENS = (
    "无法收敛研究标题",
    "无法收敛标题",
    "待补充范围与证据",
    "待补充研究范围",
    "研究范围与目标客户尚未明确",
    "待基于结构化证据收敛",
    "证据不足",
    "待补充区域",
    "待补充场景",
    "待补充主体",
    "后收敛标题",
    "未命名研报",
)
_DIAGNOSTIC_ANGLE_TOKENS = (
    "请先",
    "補齊",
    "补齐三类",
    "补齐区域",
    "补关键证据",
    "区域与行业边界",
    "區域與行業邊界",
    "标题收敛",
    "標題收斂",
    "随后再",
    "隨後再",
    "current_report",
    "避免泛化表达",
)


def _contains_repeated_span(value: str) -> bool:
    compact = re.sub(r"\s+", "", normalize_text(value))
    for width in (48, 36, 28):
        if len(compact) < width * 2:
            continue
        for index in range(len(compact) - width * 2 + 1):
            span = compact[index : index + width]
            if span in compact[index + width :]:
                return True
    return False


def _verified_target_names(report: ResearchReportResponse) -> list[str]:
    return list(
        dict.fromkeys(
            name
            for name in [
                *(normalize_text(item.name) for item in report.top_target_accounts),
                *(normalize_text(item) for item in report.target_accounts),
            ]
            if name
        )
    )


def _summary_target_mismatch(summary: str, verified_targets: list[str]) -> bool:
    match = re.search(r"优先把(.{2,120}?)列为", summary)
    if not match:
        return False
    subject = normalize_text(match.group(1))
    return not verified_targets or not any(
        target in subject or subject in target
        for target in verified_targets
    )


def _stable_report_title(report: ResearchReportResponse, *, verified_targets: list[str]) -> str:
    title = normalize_text(report.report_title)
    title_is_placeholder = not title or any(token in title for token in _PLACEHOLDER_TITLE_TOKENS)
    parts = [normalize_text(part) for part in title.split("｜") if normalize_text(part)]
    title_subject = parts[2].split("：", 1)[0] if len(parts) >= 3 else ""
    subject_is_organization = title_subject.endswith(_ORGANIZATION_TITLE_SUFFIXES)
    if not title_is_placeholder and (not subject_is_organization or any(
        target in title_subject or title_subject in target
        for target in verified_targets
    )):
        return title
    diagnostics = report.source_diagnostics
    regions = [normalize_text(item) for item in diagnostics.scope_regions if normalize_text(item)]
    industries = [normalize_text(item) for item in diagnostics.scope_industries if normalize_text(item)]
    scope = "".join([*(regions[:1]), *(industries[:1])])
    if report.output_language == "en":
        return f"{scope or normalize_text(report.keyword)[:48]} AI Demand and Opportunity Research"
    if report.output_language == "zh-TW":
        return f"{scope or normalize_text(report.keyword)[:36]}AI需求與機會調研"
    return f"{scope or normalize_text(report.keyword)[:36]}AI需求与机会调研"


def _stable_executive_summary(report: ResearchReportResponse, *, verified_targets: list[str]) -> str:
    summary = normalize_text(report.executive_summary)
    should_rebuild = (
        _contains_repeated_span(summary)
        or _summary_target_mismatch(summary, verified_targets)
        or "、竞品侧" in summary
        or "、競品側" in summary
    )
    if not should_rebuild:
        return summary
    preferred_titles = ("行业", "產業", "Industry", "关键信号", "關鍵信號", "政策", "项目与商机", "專案與商機", "Opportunity", "解决方案", "解決方案", "Solution")
    rows: list[str] = []
    for section in report.sections:
        if not any(token in normalize_text(section.title) for token in preferred_titles):
            continue
        if int(getattr(section, "evidence_count", 0) or 0) <= 0:
            continue
        row = re.sub(
            r"^【(?:高|中|低)(?:置信)?】\s*",
            "",
            normalize_text(section.items[0] if section.items else ""),
        )
        if not row or row in rows:
            continue
        rows.append(row if len(row) <= 220 else f"{row[:219].rstrip('，,；;：:')}…")
        if len(rows) >= 3:
            break
    if not rows:
        return summary
    return "".join(
        row if row.endswith(("。", "！", "？", ".", "!", "?", "…")) else f"{row}。"
        for row in rows
    )


def _stable_consulting_angle(report: ResearchReportResponse) -> str:
    angle = normalize_text(report.consulting_angle)
    gate = report.research_evidence_gate
    if not gate.passed or not any(token in angle for token in _DIAGNOSTIC_ANGLE_TOKENS):
        return angle
    preferred_titles = ("解决方案", "解決方案", "Solution", "项目与商机", "專案與商機", "Opportunity", "销售策略", "銷售策略", "Sales")
    for section in report.sections:
        if not any(token in normalize_text(section.title) for token in preferred_titles):
            continue
        if int(section.evidence_count or 0) <= 0:
            continue
        for item in section.items:
            row = re.sub(r"^【(?:高|中|低)(?:置信)?】\s*", "", normalize_text(item))
            if row:
                return row if len(row) <= 260 else f"{row[:259].rstrip('，,；;：:')}…"
    return angle


def _stabilize_report_header(report: ResearchReportResponse) -> ResearchReportResponse:
    verified_targets = _verified_target_names(report)
    return report.model_copy(
        update={
            "report_title": _stable_report_title(report, verified_targets=verified_targets),
            "executive_summary": _stable_executive_summary(report, verified_targets=verified_targets),
            "consulting_angle": _stable_consulting_angle(report),
        }
    )


def assemble_final_research_report(
    *,
    keyword: str,
    research_focus: str | None,
    followup_context: ResearchFollowupContextOut,
    followup_diagnostics: ResearchFollowupDiagnosticsOut,
    output_language: str,
    research_mode: str,
    parsed: ResearchReportResult,
    sources: list[SourceDocument],
    source_diagnostics: ResearchSourceDiagnosticsOut,
    entity_graph: ResearchEntityGraphOut,
    rankings: ResearchEntityRankingSets,
    public_contact_channels: list[str],
    account_team_signals: list[str],
    query_plan: list[str],
    research_scope_contract: ResearchScopeContractOut,
    research_question_tree: ResearchQuestionTreeOut,
    research_source_admissions: list[ResearchSourceAdmissionOut],
    research_evidence_gate: ResearchEvidenceGateOut,
    build_research_claim_governance: Callable[[ResearchReportResponse], Any],
    evidence_density_level: Callable[[list[SourceDocument], ResearchReportResult], str],
    source_quality_level: Callable[[list[SourceDocument]], str],
    build_sections: Callable[..., list[Any]],
    source_documents_to_outputs: Callable[[list[SourceDocument]], list[Any]],
    enrich_report_for_delivery: Callable[[ResearchReportResponse], ResearchReportResponse],
) -> ResearchReportResponse:
    report = ResearchReportResponse(
        keyword=keyword,
        research_focus=research_focus,
        followup_context=followup_context,
        followup_diagnostics=followup_diagnostics,
        output_language=output_language,
        research_mode=research_mode,
        report_title=parsed.report_title,
        executive_summary=parsed.executive_summary,
        consulting_angle=parsed.consulting_angle,
        sections=build_sections(parsed, output_language, sources),
        target_accounts=parsed.target_accounts,
        top_target_accounts=rankings.top_target_accounts,
        pending_target_candidates=rankings.pending_target_candidates,
        target_departments=parsed.target_departments,
        public_contact_channels=public_contact_channels,
        account_team_signals=account_team_signals,
        budget_signals=parsed.budget_signals,
        project_distribution=parsed.project_distribution,
        strategic_directions=parsed.strategic_directions,
        tender_timeline=parsed.tender_timeline,
        leadership_focus=parsed.leadership_focus,
        ecosystem_partners=parsed.ecosystem_partners,
        top_ecosystem_partners=rankings.top_ecosystem_partners,
        pending_partner_candidates=rankings.pending_partner_candidates,
        competitor_profiles=parsed.competitor_profiles,
        top_competitors=rankings.top_competitors,
        pending_competitor_candidates=rankings.pending_competitor_candidates,
        benchmark_cases=parsed.benchmark_cases,
        flagship_products=parsed.flagship_products,
        key_people=parsed.key_people,
        five_year_outlook=parsed.five_year_outlook,
        client_peer_moves=parsed.client_peer_moves,
        winner_peer_moves=parsed.winner_peer_moves,
        competition_analysis=parsed.competition_analysis,
        source_count=len(sources),
        evidence_density=evidence_density_level(sources, parsed),
        source_quality=source_quality_level(sources),
        query_plan=query_plan,
        sources=source_documents_to_outputs(sources),
        source_diagnostics=source_diagnostics,
        research_scope_contract=research_scope_contract,
        research_question_tree=research_question_tree,
        research_source_admissions=research_source_admissions,
        research_evidence_gate=research_evidence_gate,
        entity_graph=entity_graph,
        generated_at=datetime.now(timezone.utc),
    )
    report = _stabilize_report_header(report)
    claim_governance = build_research_claim_governance(report)
    report = report.model_copy(
        update={
            "research_claim_evidence_ledger": claim_governance.ledger,
            "research_citation_gate": claim_governance.citation_gate,
        }
    )
    return enrich_report_for_delivery(report)
