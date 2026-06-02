from __future__ import annotations

from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
import re

from app.schemas.research import ResearchRankedEntityOut, ResearchReportResponse
from app.services.content_extractor import extract_domain, normalize_text
from app.services.llm_parser import ResearchReportResult
from app.services.research.source_documents import SourceDocument


@dataclass(frozen=True, slots=True)
class StoredEntityCanonicalizationDependencies:
    canonical_org_name_from_domain: Callable[[str], str]
    resolve_known_org_name: Callable[..., str]
    extract_rank_entity_candidates: Callable[..., list[str]]
    strip_org_public_suffixes: Callable[[str], str]
    is_plausible_entity_name: Callable[[str], bool]
    is_lightweight_entity_name: Callable[[str], bool]
    sanitize_entity_row: Callable[[str, str], str]
    extract_rank_entity_name: Callable[[str], str]
    fallback_entity_name_from_row: Callable[[str], str]
    looks_like_fragment_entity_name: Callable[[str], bool]
    contains_low_value_entity_token: Callable[[str], bool]
    looks_like_placeholder_entity_name: Callable[[str], bool]
    entity_canonical_key: Callable[[str], str]
    source_mentions_entity: Callable[[SourceDocument, str], bool]
    dedupe_strings: Callable[[Iterable[str], int], list[str]]
    looks_like_insufficient: Callable[[str], bool]
    looks_like_scope_prompt_noise: Callable[[str], bool]
    looks_like_source_artifact_text: Callable[[str], bool]
    strip_entity_leading_noise: Callable[[str], str]
    entity_role_fields: Collection[str]


def canonical_org_name_from_evidence_links(
    evidence_links: Iterable[object] | None,
    *,
    scope_hints: dict[str, object],
    deps: StoredEntityCanonicalizationDependencies,
) -> str:
    for raw_link in evidence_links or []:
        if isinstance(raw_link, dict):
            title = normalize_text(str(raw_link.get("title") or ""))
            url = normalize_text(str(raw_link.get("url") or ""))
            source_label = normalize_text(str(raw_link.get("source_label") or ""))
        else:
            title = normalize_text(str(getattr(raw_link, "title", "") or ""))
            url = normalize_text(str(getattr(raw_link, "url", "") or ""))
            source_label = normalize_text(str(getattr(raw_link, "source_label", "") or ""))
        domain_canonical = deps.canonical_org_name_from_domain(extract_domain(url) or "")
        if domain_canonical:
            return deps.resolve_known_org_name(domain_canonical, scope_hints=scope_hints)
        title_candidates = deps.extract_rank_entity_candidates(title, scope_hints=scope_hints)
        if title_candidates:
            return title_candidates[0]
        label_candidate = deps.strip_org_public_suffixes(source_label.removesuffix("官网").removesuffix("集团官网"))
        if label_candidate and (deps.is_plausible_entity_name(label_candidate) or deps.is_lightweight_entity_name(label_candidate)):
            return deps.resolve_known_org_name(label_candidate, scope_hints=scope_hints)
    return ""


def canonicalize_stored_entity_name(
    value: str,
    *,
    field_key: str,
    scope_hints: dict[str, object],
    source_documents: list[SourceDocument],
    evidence_links: Iterable[object] | None = None,
    deps: StoredEntityCanonicalizationDependencies,
) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    role_field = field_key in deps.entity_role_fields
    candidate = deps.sanitize_entity_row(field_key, normalized) if role_field else normalize_text(value)
    linked_canonical = canonical_org_name_from_evidence_links(evidence_links, scope_hints=scope_hints, deps=deps)
    if not candidate:
        return linked_canonical
    entity_name = deps.extract_rank_entity_name(candidate) or deps.fallback_entity_name_from_row(candidate) or candidate
    entity_name = deps.resolve_known_org_name(entity_name, scope_hints=scope_hints)
    if linked_canonical and (
        not entity_name
        or deps.looks_like_fragment_entity_name(entity_name)
        or deps.contains_low_value_entity_token(entity_name)
        or deps.looks_like_placeholder_entity_name(entity_name)
    ):
        entity_name = linked_canonical
    if not entity_name:
        return ""
    if role_field and not (deps.is_plausible_entity_name(entity_name) or deps.is_lightweight_entity_name(entity_name)):
        return (
            linked_canonical
            if linked_canonical and (deps.is_plausible_entity_name(linked_canonical) or deps.is_lightweight_entity_name(linked_canonical))
            else ""
        )
    if linked_canonical and deps.entity_canonical_key(linked_canonical) != deps.entity_canonical_key(entity_name):
        canonical_supported = any(deps.source_mentions_entity(source, linked_canonical) for source in source_documents)
        candidate_supported = any(deps.source_mentions_entity(source, entity_name) for source in source_documents)
        if canonical_supported and not candidate_supported:
            entity_name = linked_canonical
    return normalize_text(entity_name)


def canonicalize_stored_entity_rows(
    values: Iterable[str],
    *,
    field_key: str,
    scope_hints: dict[str, object],
    source_documents: list[SourceDocument],
    deps: StoredEntityCanonicalizationDependencies,
) -> list[str]:
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in values:
        candidate = canonicalize_stored_entity_name(
            normalize_text(str(raw)),
            field_key=field_key,
            scope_hints=scope_hints,
            source_documents=source_documents,
            deps=deps,
        )
        key = deps.entity_canonical_key(candidate)
        if not candidate or not key or key in seen:
            continue
        seen.add(key)
        cleaned.append(candidate)
    return cleaned


def canonicalize_stored_ranked_entities(
    entities: Iterable[ResearchRankedEntityOut],
    *,
    field_key: str,
    scope_hints: dict[str, object],
    source_documents: list[SourceDocument],
    deps: StoredEntityCanonicalizationDependencies,
) -> list[ResearchRankedEntityOut]:
    deduped: dict[str, ResearchRankedEntityOut] = {}
    order: list[str] = []
    for entity in entities:
        canonical_name = canonicalize_stored_entity_name(
            entity.name,
            field_key=field_key,
            scope_hints=scope_hints,
            source_documents=source_documents,
            evidence_links=entity.evidence_links,
            deps=deps,
        )
        canonical_key = deps.entity_canonical_key(canonical_name)
        if not canonical_name or not canonical_key:
            continue
        updated = entity.model_copy(update={"name": canonical_name})
        current = deduped.get(canonical_key)
        if current is None:
            deduped[canonical_key] = updated
            order.append(canonical_key)
            continue
        if int(updated.score or 0) > int(current.score or 0):
            merged_links = list(current.evidence_links)
            for link in updated.evidence_links:
                if getattr(link, "url", "") and not any(getattr(item, "url", "") == getattr(link, "url", "") for item in merged_links):
                    merged_links.append(link)
            deduped[canonical_key] = updated.model_copy(update={"evidence_links": merged_links[:3]})
    return [deduped[key] for key in order]


def canonicalize_stored_report_entities(
    report: ResearchReportResponse,
    *,
    scope_hints: dict[str, object],
    source_documents: list[SourceDocument],
    deps: StoredEntityCanonicalizationDependencies,
) -> ResearchReportResponse:
    canonical_top_targets = canonicalize_stored_ranked_entities(
        report.top_target_accounts,
        field_key="target_accounts",
        scope_hints=scope_hints,
        source_documents=source_documents,
        deps=deps,
    )
    canonical_pending_targets = canonicalize_stored_ranked_entities(
        report.pending_target_candidates,
        field_key="target_accounts",
        scope_hints=scope_hints,
        source_documents=source_documents,
        deps=deps,
    )
    canonical_top_partners = canonicalize_stored_ranked_entities(
        report.top_ecosystem_partners,
        field_key="ecosystem_partners",
        scope_hints=scope_hints,
        source_documents=source_documents,
        deps=deps,
    )
    canonical_pending_partners = canonicalize_stored_ranked_entities(
        report.pending_partner_candidates,
        field_key="ecosystem_partners",
        scope_hints=scope_hints,
        source_documents=source_documents,
        deps=deps,
    )
    canonical_top_competitors = canonicalize_stored_ranked_entities(
        report.top_competitors,
        field_key="competitor_profiles",
        scope_hints=scope_hints,
        source_documents=source_documents,
        deps=deps,
    )
    canonical_pending_competitors = canonicalize_stored_ranked_entities(
        report.pending_competitor_candidates,
        field_key="competitor_profiles",
        scope_hints=scope_hints,
        source_documents=source_documents,
        deps=deps,
    )
    canonical_targets = deps.dedupe_strings(
        [
            *[item.name for item in canonical_top_targets],
            *[item.name for item in canonical_pending_targets],
            *canonicalize_stored_entity_rows(
                report.target_accounts,
                field_key="target_accounts",
                scope_hints=scope_hints,
                source_documents=source_documents,
                deps=deps,
            ),
        ],
        6,
    )
    canonical_partners = deps.dedupe_strings(
        [
            *[item.name for item in canonical_top_partners],
            *[item.name for item in canonical_pending_partners],
            *canonicalize_stored_entity_rows(
                report.ecosystem_partners,
                field_key="ecosystem_partners",
                scope_hints=scope_hints,
                source_documents=source_documents,
                deps=deps,
            ),
        ],
        6,
    )
    canonical_competitors = deps.dedupe_strings(
        [
            *[item.name for item in canonical_top_competitors],
            *[item.name for item in canonical_pending_competitors],
            *canonicalize_stored_entity_rows(
                report.competitor_profiles,
                field_key="competitor_profiles",
                scope_hints=scope_hints,
                source_documents=source_documents,
                deps=deps,
            ),
        ],
        6,
    )
    diagnostics = report.source_diagnostics.model_copy(
        update={
            "scope_clients": canonical_targets[:4],
        }
    )
    return report.model_copy(
        update={
            "target_accounts": canonical_targets,
            "top_target_accounts": canonical_top_targets,
            "pending_target_candidates": canonical_pending_targets,
            "ecosystem_partners": canonical_partners,
            "top_ecosystem_partners": canonical_top_partners,
            "pending_partner_candidates": canonical_pending_partners,
            "competitor_profiles": canonical_competitors,
            "top_competitors": canonical_top_competitors,
            "pending_competitor_candidates": canonical_pending_competitors,
            "source_diagnostics": diagnostics,
        }
    )


def canonicalize_stored_result_entities(
    result: ResearchReportResult,
    *,
    scope_hints: dict[str, object],
    source_documents: list[SourceDocument],
    deps: StoredEntityCanonicalizationDependencies,
) -> ResearchReportResult:
    return result.model_copy(
        update={
            "target_accounts": canonicalize_stored_entity_rows(
                result.target_accounts,
                field_key="target_accounts",
                scope_hints=scope_hints,
                source_documents=source_documents,
                deps=deps,
            ),
            "ecosystem_partners": canonicalize_stored_entity_rows(
                result.ecosystem_partners,
                field_key="ecosystem_partners",
                scope_hints=scope_hints,
                source_documents=source_documents,
                deps=deps,
            ),
            "competitor_profiles": canonicalize_stored_entity_rows(
                result.competitor_profiles,
                field_key="competitor_profiles",
                scope_hints=scope_hints,
                source_documents=source_documents,
                deps=deps,
            ),
        }
    )


def clean_candidate_profile_company_names(
    values: Iterable[str],
    *,
    deps: StoredEntityCanonicalizationDependencies,
) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        normalized = normalize_text(str(value))
        if (
            not normalized
            or "待验证" in normalized
            or "待驗證" in normalized
            or deps.looks_like_insufficient(normalized)
            or deps.looks_like_scope_prompt_noise(normalized)
            or deps.looks_like_source_artifact_text(normalized)
        ):
            continue
        candidate = deps.extract_rank_entity_name(normalized) or deps.fallback_entity_name_from_row(normalized) or normalized
        candidate = deps.strip_entity_leading_noise(candidate)
        if (
            not candidate
            or re.search(r"(19|20)\d{2}", candidate)
            or deps.looks_like_fragment_entity_name(candidate)
            or deps.contains_low_value_entity_token(candidate)
            or deps.looks_like_scope_prompt_noise(candidate)
            or deps.looks_like_placeholder_entity_name(candidate)
        ):
            continue
        if not deps.is_plausible_entity_name(candidate) and not deps.is_lightweight_entity_name(candidate):
            continue
        cleaned.append(candidate)
    return deps.dedupe_strings(cleaned, 6)
