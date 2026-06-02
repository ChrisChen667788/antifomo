from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.schemas.research import (
    ResearchEntityGraphOut,
    ResearchFollowupContextOut,
    ResearchFollowupDiagnosticsOut,
    ResearchReportResponse,
    ResearchSourceDiagnosticsOut,
)
from app.services.llm_parser import ResearchReportResult
from app.services.research.entity_ranking import ResearchEntityRankingSets
from app.services.research.source_documents import SourceDocument


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
        entity_graph=entity_graph,
        generated_at=datetime.now(timezone.utc),
    )
    return enrich_report_for_delivery(report)
