from __future__ import annotations

from app.services.content_extractor import normalize_text
from app.schemas.research import ResearchReportResponse
from app.services.llm_parser import ResearchReportResult
from app.services.research.report_common import dedupe_strings
from app.services.research.report_row_quality import looks_like_insufficient
from app.services.research.scope_entity_runtime_dependencies import scope_entity_runtime_functions
from app.services.research.entity_policy import text_has_industry_conflict
from app.services.research.report_sections import build_section_title_map
from app.services.research.source_documents import SourceDocument


_STRUCTURED_SECTION_FIELDS = (
    "target_accounts",
    "target_departments",
    "public_contact_channels",
    "account_team_signals",
    "budget_signals",
    "project_distribution",
    "strategic_directions",
    "tender_timeline",
    "leadership_focus",
    "ecosystem_partners",
    "competitor_profiles",
    "benchmark_cases",
    "flagship_products",
    "key_people",
    "five_year_outlook",
    "client_peer_moves",
    "winner_peer_moves",
    "competition_analysis",
)


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
    *,
    scope_hints: dict[str, object] | None = None,
) -> ResearchReportResult:
    sanitize_rows = scope_entity_runtime_functions().sanitize_report_field_rows

    def scope_sanitize_rows(key: str, values: object) -> list[str]:
        raw_values = values if isinstance(values, list) else []
        return [
            row
            for row in sanitize_rows(key, raw_values)
            if not text_has_industry_conflict(row, scope_hints=scope_hints)
        ]

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
        current = scope_sanitize_rows(key, payload.get(key, []))
        sanitized_values = scope_sanitize_rows(key, values)
        min_count = min_count_overrides.get(key, 2)
        if key in grounded_first_fields and (current or sanitized_values):
            payload[key] = scope_sanitize_rows(
                key,
                dedupe_strings([*current, *sanitized_values], 6),
            )
            continue
        if len(current) >= min_count:
            payload[key] = current
            continue
        payload[key] = scope_sanitize_rows(
            key,
            dedupe_strings(current + sanitized_values, max(6, min_count)),
        )
    for key, values in list(payload.items()):
        if isinstance(values, list):
            payload[key] = scope_sanitize_rows(key, values)
    return ResearchReportResult.model_validate(payload)


def sanitize_report_response_fields(
    report: ResearchReportResponse,
    *,
    allowed_source_urls: set[str] | None = None,
) -> ResearchReportResponse:
    sanitize_rows = scope_entity_runtime_functions().sanitize_report_field_rows
    updates = {
        field_key: sanitize_rows(field_key, getattr(report, field_key, []))
        for field_key in _STRUCTURED_SECTION_FIELDS
    }
    candidate = report.model_copy(update=updates)
    title_to_field = {
        title: field_key
        for field_key, title in build_section_title_map(candidate.output_language).items()
        if field_key in _STRUCTURED_SECTION_FIELDS
    }
    allowed_urls = (
        {normalize_text(url) for url in allowed_source_urls if normalize_text(url)}
        if allowed_source_urls is not None
        else None
    )
    sections = []
    for section in candidate.sections:
        field_key = title_to_field.get(normalize_text(section.title))
        items = list(getattr(candidate, field_key, [])) if field_key else list(section.items)
        if field_key and not items:
            continue
        evidence_links = [
            link
            for link in section.evidence_links
            if allowed_urls is None or normalize_text(link.url) in allowed_urls
        ]
        source_tier_counts: dict[str, int] = {}
        for link in evidence_links:
            tier = normalize_text(link.source_tier or "media") or "media"
            source_tier_counts[tier] = source_tier_counts.get(tier, 0) + 1
        evidence_count = len(evidence_links)
        evidence_quota = int(section.evidence_quota or 0)
        quota_gap = max(evidence_quota - evidence_count, 0)
        meets_evidence_quota = quota_gap == 0
        official_ratio = round(source_tier_counts.get("official", 0) / evidence_count, 2) if evidence_count else 0.0
        sections.append(
            section.model_copy(
                update={
                    "items": items,
                    "evidence_links": evidence_links,
                    "evidence_count": evidence_count,
                    "source_tier_counts": source_tier_counts,
                    "official_source_ratio": official_ratio,
                    "meets_evidence_quota": meets_evidence_quota,
                    "quota_gap": quota_gap,
                    "status": section.status if meets_evidence_quota else "needs_evidence",
                    "evidence_density": section.evidence_density if evidence_count else "low",
                    "source_quality": section.source_quality if evidence_count else "low",
                }
            )
        )
    return candidate.model_copy(update={"sections": sections})
