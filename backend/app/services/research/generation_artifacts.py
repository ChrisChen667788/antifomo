from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
import json
from typing import Any

from app.schemas.research import (
    ResearchEntityGraphOut,
    ResearchReportResponse,
    ResearchSourceDiagnosticsOut,
)
from app.services.content_extractor import normalize_text
from app.services.language import localized_text
from app.services.llm_parser import ResearchReportResult, parse_research_strategy_refine_response
from app.services.research.source_documents import SourceDocument


def build_partial_report_result(
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    research_mode: str,
    archive_context: str,
    followup_diagnostics: str,
    source_intelligence: dict[str, list[str]],
    scope_hints: dict[str, object],
    llm: object | None,
    llm_timeout_seconds: int,
    render_industry_methodology_context: Callable[[dict[str, object]], str],
    apply_topic_specific_overrides: Callable[..., ResearchReportResult],
) -> ResearchReportResult:
    scope_anchor = normalize_text(str(scope_hints.get("anchor_text", ""))) or normalize_text(research_focus or "") or keyword
    fallback = ResearchReportResult(
        report_title="",
        executive_summary="",
        consulting_angle="",
        industry_brief=list(source_intelligence.get("industry_brief", [])),
        key_signals=list(source_intelligence.get("key_signals", [])),
        policy_and_leadership=list(source_intelligence.get("policy_and_leadership", [])),
        commercial_opportunities=list(source_intelligence.get("commercial_opportunities", [])),
        solution_design=list(source_intelligence.get("solution_design", [])),
        sales_strategy=list(source_intelligence.get("sales_strategy", [])),
        bidding_strategy=list(source_intelligence.get("bidding_strategy", [])),
        outreach_strategy=list(source_intelligence.get("outreach_strategy", [])),
        ecosystem_strategy=list(source_intelligence.get("ecosystem_strategy", [])),
        target_accounts=list(source_intelligence.get("target_accounts", [])),
        target_departments=list(source_intelligence.get("target_departments", [])),
        public_contact_channels=list(source_intelligence.get("public_contact_channels", [])),
        account_team_signals=list(source_intelligence.get("account_team_signals", [])),
        budget_signals=list(source_intelligence.get("budget_signals", [])),
        project_distribution=list(source_intelligence.get("project_distribution", [])),
        strategic_directions=list(source_intelligence.get("strategic_directions", [])),
        tender_timeline=list(source_intelligence.get("tender_timeline", [])),
        leadership_focus=list(source_intelligence.get("leadership_focus", [])),
        ecosystem_partners=list(source_intelligence.get("ecosystem_partners", [])),
        competitor_profiles=list(source_intelligence.get("competitor_profiles", [])),
        benchmark_cases=list(source_intelligence.get("benchmark_cases", [])),
        flagship_products=list(source_intelligence.get("flagship_products", [])),
        key_people=list(source_intelligence.get("key_people", [])),
        five_year_outlook=list(source_intelligence.get("five_year_outlook", [])),
        client_peer_moves=list(source_intelligence.get("client_peer_moves", [])),
        winner_peer_moves=list(source_intelligence.get("winner_peer_moves", [])),
        competition_analysis=list(source_intelligence.get("competition_analysis", [])),
        risks=list(source_intelligence.get("risks", [])),
        next_actions=list(source_intelligence.get("next_actions", [])),
    )

    if llm is not None:
        try:
            raw = llm.run_prompt(
                "research_report_outline.txt",
                {
                    "keyword": keyword,
                    "research_focus": research_focus or "",
                    "output_language": output_language,
                    "research_mode": research_mode,
                    "scope_hints": json.dumps(scope_hints, ensure_ascii=False),
                    "archive_context": archive_context,
                    "followup_diagnostics": followup_diagnostics,
                    "source_intelligence": json.dumps(source_intelligence, ensure_ascii=False),
                    "industry_methodology_context": render_industry_methodology_context(scope_hints),
                    "__timeout_seconds": str(max(14, min(llm_timeout_seconds, 24))),
                },
            )
            outline = parse_research_strategy_refine_response(raw)
            if normalize_text(outline.report_title):
                fallback.report_title = normalize_text(outline.report_title)
            if normalize_text(outline.executive_summary):
                fallback.executive_summary = normalize_text(outline.executive_summary)
            if normalize_text(outline.consulting_angle):
                fallback.consulting_angle = normalize_text(outline.consulting_angle)
        except Exception:
            pass

    fallback = apply_topic_specific_overrides(
        fallback,
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        scope_hints=scope_hints,
        intelligence=source_intelligence,
    )
    if not normalize_text(fallback.consulting_angle):
        fallback.consulting_angle = localized_text(
            output_language,
            {
                "zh-CN": f"优先围绕 {scope_anchor} 做范围锁定、预算核验、竞品对比和伙伴进入路径设计。",
                "zh-TW": f"優先圍繞 {scope_anchor} 做範圍鎖定、預算核驗、競品對比與夥伴進入路徑設計。",
                "en": f"Prioritize scope locking, budget validation, competitor comparison, and partner-led entry design around {scope_anchor}.",
            },
            f"优先围绕 {scope_anchor} 做范围锁定、预算核验、竞品对比和伙伴进入路径设计。",
        )
    return fallback


def build_partial_report_response(
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    research_mode: str,
    parsed: ResearchReportResult,
    query_plan: list[str],
    sources: list[SourceDocument],
    source_diagnostics: ResearchSourceDiagnosticsOut,
    entity_graph: ResearchEntityGraphOut,
    evidence_density_level: Callable[[list[SourceDocument], ResearchReportResult], str],
    source_quality_level: Callable[[list[SourceDocument]], str],
    build_sections: Callable[..., list[Any]],
    source_documents_to_outputs: Callable[[list[SourceDocument]], list[Any]],
    enrich_report_for_delivery: Callable[[ResearchReportResponse], ResearchReportResponse],
) -> ResearchReportResponse:
    evidence_density = evidence_density_level(sources, parsed)
    source_quality = source_quality_level(sources)
    sections = build_sections(parsed, output_language, sources)
    report = ResearchReportResponse(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        research_mode=research_mode,
        report_title=parsed.report_title,
        executive_summary=parsed.executive_summary,
        consulting_angle=parsed.consulting_angle,
        sections=sections,
        target_accounts=parsed.target_accounts,
        top_target_accounts=[],
        target_departments=parsed.target_departments,
        public_contact_channels=parsed.public_contact_channels,
        account_team_signals=parsed.account_team_signals,
        budget_signals=parsed.budget_signals,
        project_distribution=parsed.project_distribution,
        strategic_directions=parsed.strategic_directions,
        tender_timeline=parsed.tender_timeline,
        leadership_focus=parsed.leadership_focus,
        ecosystem_partners=parsed.ecosystem_partners,
        top_ecosystem_partners=[],
        competitor_profiles=parsed.competitor_profiles,
        top_competitors=[],
        benchmark_cases=parsed.benchmark_cases,
        flagship_products=parsed.flagship_products,
        key_people=parsed.key_people,
        five_year_outlook=parsed.five_year_outlook,
        client_peer_moves=parsed.client_peer_moves,
        winner_peer_moves=parsed.winner_peer_moves,
        competition_analysis=parsed.competition_analysis,
        source_count=len(sources),
        evidence_density=evidence_density,
        source_quality=source_quality,
        query_plan=query_plan,
        sources=source_documents_to_outputs(sources),
        source_diagnostics=source_diagnostics,
        entity_graph=entity_graph,
        generated_at=datetime.now(timezone.utc),
    )
    return enrich_report_for_delivery(report)
