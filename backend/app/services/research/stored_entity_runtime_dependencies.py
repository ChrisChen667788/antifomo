from __future__ import annotations

from collections.abc import Iterable

from app.schemas.research import ResearchReportResponse
from app.services.llm_parser import ResearchReportResult
from app.services.research.entity_policy import (
    ENTITY_ROLE_FIELDS,
    contains_low_value_entity_token,
    extract_rank_entity_name,
    fallback_entity_name_from_row,
    is_lightweight_entity_name,
    is_plausible_entity_name,
    looks_like_fragment_entity_name,
    looks_like_placeholder_entity_name,
    strip_entity_leading_noise,
)
from app.services.research.organization_identity import (
    canonical_org_name_from_domain,
    entity_canonical_key,
    extract_rank_entity_candidates,
    resolve_known_org_name,
    source_mentions_entity,
    strip_org_public_suffixes,
)
from app.services.research.report_common import dedupe_strings
from app.services.research.report_field_sanitization import sanitize_entity_row
from app.services.research.report_row_quality import looks_like_insufficient
from app.services.research.scope_entity_runtime_dependencies import (
    report_field_sanitization_dependencies,
    scope_term_dependencies,
)
from app.services.research.scope_terms import looks_like_scope_prompt_noise
from app.services.research.source_documents import SourceDocument, looks_like_source_artifact_text
from app.services.research.stored_entity_canonicalization import (
    StoredEntityCanonicalizationDependencies,
    canonicalize_stored_entity_name,
    canonicalize_stored_report_entities,
    canonicalize_stored_result_entities,
    clean_candidate_profile_company_names,
)


def stored_entity_canonicalization_dependencies() -> StoredEntityCanonicalizationDependencies:
    scope_deps = scope_term_dependencies()
    field_deps = report_field_sanitization_dependencies()
    return StoredEntityCanonicalizationDependencies(
        canonical_org_name_from_domain=canonical_org_name_from_domain,
        resolve_known_org_name=resolve_known_org_name,
        extract_rank_entity_candidates=extract_rank_entity_candidates,
        strip_org_public_suffixes=strip_org_public_suffixes,
        is_plausible_entity_name=is_plausible_entity_name,
        is_lightweight_entity_name=is_lightweight_entity_name,
        sanitize_entity_row=lambda field_key, value: sanitize_entity_row(field_key, value, deps=field_deps),
        extract_rank_entity_name=extract_rank_entity_name,
        fallback_entity_name_from_row=fallback_entity_name_from_row,
        looks_like_fragment_entity_name=looks_like_fragment_entity_name,
        contains_low_value_entity_token=contains_low_value_entity_token,
        looks_like_placeholder_entity_name=looks_like_placeholder_entity_name,
        entity_canonical_key=entity_canonical_key,
        source_mentions_entity=source_mentions_entity,
        dedupe_strings=dedupe_strings,
        looks_like_insufficient=looks_like_insufficient,
        looks_like_scope_prompt_noise=lambda value: looks_like_scope_prompt_noise(value, deps=scope_deps),
        looks_like_source_artifact_text=looks_like_source_artifact_text,
        strip_entity_leading_noise=strip_entity_leading_noise,
        entity_role_fields=ENTITY_ROLE_FIELDS,
    )


def canonicalize_entity_name(
    value: str,
    *,
    field_key: str,
    scope_hints: dict[str, object],
    source_documents: list[SourceDocument],
    evidence_links: Iterable[object] | None = None,
) -> str:
    return canonicalize_stored_entity_name(
        value,
        field_key=field_key,
        scope_hints=scope_hints,
        source_documents=source_documents,
        evidence_links=evidence_links,
        deps=stored_entity_canonicalization_dependencies(),
    )


def canonicalize_report_entities(
    report: ResearchReportResponse,
    *,
    scope_hints: dict[str, object],
    source_documents: list[SourceDocument],
) -> ResearchReportResponse:
    return canonicalize_stored_report_entities(
        report,
        scope_hints=scope_hints,
        source_documents=source_documents,
        deps=stored_entity_canonicalization_dependencies(),
    )


def canonicalize_result_entities(
    result: ResearchReportResult,
    *,
    scope_hints: dict[str, object],
    source_documents: list[SourceDocument],
) -> ResearchReportResult:
    return canonicalize_stored_result_entities(
        result,
        scope_hints=scope_hints,
        source_documents=source_documents,
        deps=stored_entity_canonicalization_dependencies(),
    )


def clean_candidate_company_names(values: Iterable[str]) -> list[str]:
    return clean_candidate_profile_company_names(
        values,
        deps=stored_entity_canonicalization_dependencies(),
    )
