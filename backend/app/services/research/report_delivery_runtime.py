from __future__ import annotations

from app.services.content_extractor import normalize_text
from app.services.llm_parser import ResearchReportResult
from app.services.research.report_common import dedupe_strings
from app.services.research.report_row_quality import looks_like_insufficient
from app.services.research.scope_entity_runtime_dependencies import scope_entity_runtime_functions
from app.services.research.source_documents import SourceDocument


def source_quality_level(sources: list[SourceDocument]) -> str:
    if not sources:
        return "low"
    official_count = sum(1 for source in sources if source.source_tier == "official")
    official_ratio = official_count / max(len(sources), 1)
    if official_count >= 4 or official_ratio >= 0.55:
        return "high"
    if official_count >= 2 or official_ratio >= 0.3:
        return "medium"
    return "low"


def evidence_density_level(sources: list[SourceDocument], parsed: ResearchReportResult) -> str:
    if not sources:
        return "low"
    concrete_groups = 0
    for values in (
        parsed.target_accounts,
        parsed.target_departments,
        parsed.public_contact_channels,
        parsed.account_team_signals,
        parsed.budget_signals,
        parsed.project_distribution,
        parsed.strategic_directions,
        parsed.tender_timeline,
        parsed.leadership_focus,
        parsed.ecosystem_partners,
        parsed.competitor_profiles,
        parsed.benchmark_cases,
        parsed.flagship_products,
        parsed.key_people,
        parsed.five_year_outlook,
        parsed.client_peer_moves,
        parsed.winner_peer_moves,
        parsed.competition_analysis,
    ):
        if any(normalize_text(value) and not looks_like_insufficient(value) for value in values):
            concrete_groups += 1
    if len(sources) >= 8 and concrete_groups >= 8:
        return "high"
    if len(sources) >= 4 and concrete_groups >= 4:
        return "medium"
    return "low"


def merge_result_with_intelligence(
    parsed: ResearchReportResult,
    intelligence: dict[str, list[str]],
) -> ResearchReportResult:
    sanitize_rows = scope_entity_runtime_functions().sanitize_report_field_rows
    payload = parsed.model_dump(mode="python")
    grounded_first_fields = {
        "public_contact_channels",
        "budget_signals",
        "project_distribution",
        "strategic_directions",
        "tender_timeline",
        "leadership_focus",
        "benchmark_cases",
        "flagship_products",
        "key_people",
        "five_year_outlook",
        "client_peer_moves",
        "winner_peer_moves",
        "competition_analysis",
    }
    min_count_overrides = {
        "target_accounts": 3,
        "target_departments": 3,
        "public_contact_channels": 3,
        "account_team_signals": 3,
        "budget_signals": 3,
        "project_distribution": 3,
        "strategic_directions": 3,
        "tender_timeline": 3,
        "leadership_focus": 3,
        "ecosystem_partners": 3,
        "competitor_profiles": 3,
        "benchmark_cases": 3,
        "flagship_products": 3,
        "key_people": 3,
        "five_year_outlook": 3,
        "client_peer_moves": 3,
        "winner_peer_moves": 3,
        "competition_analysis": 3,
    }
    for key, values in intelligence.items():
        current = sanitize_rows(key, payload.get(key, []))
        sanitized_values = sanitize_rows(key, values)
        min_count = min_count_overrides.get(key, 2)
        if key in grounded_first_fields and sanitized_values:
            payload[key] = sanitized_values
            continue
        if len(current) >= min_count:
            payload[key] = current
            continue
        payload[key] = sanitize_rows(
            key,
            dedupe_strings(current + sanitized_values, max(6, min_count)),
        )
    for key, values in list(payload.items()):
        if isinstance(values, list):
            payload[key] = sanitize_rows(key, values)
    return ResearchReportResult.model_validate(payload)
