from __future__ import annotations

from collections.abc import Iterable

from app.schemas.research import ResearchReportDocument, ResearchReportResponse, ResearchSourceOut
from app.services.content_extractor import normalize_text
from app.services.llm_parser import ResearchReportResult
from app.services.research.report_common import dedupe_strings
from app.services.research.report_storage import report_sources_to_source_documents, stored_report_to_result
from app.services.research.scope_entity_runtime_dependencies import scope_entity_runtime_functions
from app.services.research.source_documents import SourceDocument, clean_source_text_for_analysis
from app.services.research.source_ranking import classify_source_tier, classify_source_type, derive_source_label


def truncate_text(value: str, limit: int) -> str:
    text = normalize_text(value)
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rstrip(" ，,：:；;")
    return f"{cut}…"


def dedupe_sources(sources: Iterable[SourceDocument]) -> list[SourceDocument]:
    deduped: list[SourceDocument] = []
    seen_urls: set[str] = set()
    for source in sources:
        normalized_url = normalize_text(source.url)
        if normalized_url and normalized_url in seen_urls:
            continue
        if normalized_url:
            seen_urls.add(normalized_url)
        deduped.append(source)
    return deduped


def research_section_items(report: ResearchReportDocument, aliases: tuple[str, ...]) -> list[str]:
    normalized_aliases = tuple(alias.lower() for alias in aliases)
    for section in report.sections:
        title = normalize_text(section.title).lower()
        if any(alias in title for alias in normalized_aliases):
            return [normalize_text(item) for item in section.items if normalize_text(item)]
    return []


def report_sources_to_documents(sources: list[ResearchSourceOut]) -> list[SourceDocument]:
    return report_sources_to_source_documents(
        sources,
        classify_source_type=classify_source_type,
        classify_source_tier=classify_source_tier,
        derive_source_label=derive_source_label,
        clean_source_text_for_analysis=clean_source_text_for_analysis,
        truncate_text=truncate_text,
        dedupe_sources=dedupe_sources,
    )


def stored_report_to_runtime_result(report: ResearchReportResponse) -> ResearchReportResult:
    scope_entity = scope_entity_runtime_functions()
    return stored_report_to_result(
        report,
        research_section_items=research_section_items,
        sanitize_report_field_rows=scope_entity.sanitize_report_field_rows,
    )


def report_intelligence_from_result(
    report: ResearchReportResponse,
    result: ResearchReportResult,
) -> dict[str, list[str]]:
    return {
        "industry_brief": list(result.industry_brief),
        "key_signals": list(result.key_signals),
        "policy_and_leadership": list(result.policy_and_leadership),
        "commercial_opportunities": list(result.commercial_opportunities),
        "solution_design": list(result.solution_design),
        "sales_strategy": list(result.sales_strategy),
        "bidding_strategy": list(result.bidding_strategy),
        "outreach_strategy": list(result.outreach_strategy),
        "ecosystem_strategy": list(result.ecosystem_strategy),
        "target_accounts": dedupe_strings(
            [
                *result.target_accounts,
                *(normalize_text(item.name) for item in report.top_target_accounts if normalize_text(item.name)),
                *(normalize_text(item.name) for item in report.pending_target_candidates if normalize_text(item.name)),
            ],
            6,
        ),
        "target_departments": list(result.target_departments),
        "public_contact_channels": list(result.public_contact_channels),
        "account_team_signals": list(result.account_team_signals),
        "budget_signals": list(result.budget_signals),
        "project_distribution": list(result.project_distribution),
        "strategic_directions": list(result.strategic_directions),
        "tender_timeline": list(result.tender_timeline),
        "leadership_focus": list(result.leadership_focus),
        "ecosystem_partners": dedupe_strings(
            [
                *result.ecosystem_partners,
                *(normalize_text(item.name) for item in report.top_ecosystem_partners if normalize_text(item.name)),
                *(normalize_text(item.name) for item in report.pending_partner_candidates if normalize_text(item.name)),
            ],
            6,
        ),
        "competitor_profiles": dedupe_strings(
            [
                *result.competitor_profiles,
                *(normalize_text(item.name) for item in report.top_competitors if normalize_text(item.name)),
                *(normalize_text(item.name) for item in report.pending_competitor_candidates if normalize_text(item.name)),
            ],
            6,
        ),
        "benchmark_cases": list(result.benchmark_cases),
        "flagship_products": list(result.flagship_products),
        "key_people": list(result.key_people),
        "five_year_outlook": list(result.five_year_outlook),
        "client_peer_moves": list(result.client_peer_moves),
        "winner_peer_moves": list(result.winner_peer_moves),
        "competition_analysis": list(result.competition_analysis),
        "risks": list(result.risks),
        "next_actions": list(result.next_actions),
    }
