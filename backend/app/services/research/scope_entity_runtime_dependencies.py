from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from functools import lru_cache

from app.services.research.entity_policy import (
    CASE_HINT_TOKENS,
    COMPACT_ENTITY_PATTERN,
    CONTACT_PAGE_TOKENS,
    CONTACT_ROW_HINT_TOKENS,
    DEPARTMENT_HINT_TOKENS,
    DEPARTMENT_PATTERN,
    EMAIL_PATTERN,
    ENTITY_ROLE_CONTEXT_TOKENS,
    ENTITY_ROLE_FIELDS,
    ENTITY_ROLE_NAME_HINTS,
    ENTITY_SUFFIX_TOKENS,
    GENERIC_COMPANY_ANCHOR_TOKENS,
    GENERIC_CONTENT_DOMAINS,
    GENERIC_FOCUS_TOKENS,
    INDUSTRY_SCOPE_ALIASES,
    INVALID_COMPANY_ANCHOR_PHRASES,
    KNOWN_LIGHTWEIGHT_ENTITY_NAMES,
    NON_CONTACT_SOURCE_LABEL_TOKENS,
    ORG_PATTERN,
    PARTNER_CONNECTOR_ALIASES,
    PHONE_PATTERN,
    PRODUCT_HINT_TOKENS,
    QUERY_NOISE_SUFFIXES,
    SCOPE_PROMPT_NOISE_PREFIXES,
    SCOPE_PROMPT_NOISE_REGEXES,
    SCOPE_PROMPT_NOISE_TOKENS,
    SPECIAL_ENTITY_ALIASES,
    THEME_GENERIC_SUPPRESSIONS,
    contains_low_value_entity_token,
    entity_canonical_key,
    extract_rank_entity_name,
    fallback_entity_name_from_row,
    is_lightweight_entity_name,
    is_plausible_entity_name,
    is_theme_aligned_entity_name,
    is_trustworthy_scope_client_name,
    looks_like_fragment_entity_name,
    looks_like_placeholder_contact_row,
    looks_like_placeholder_entity_name,
    strip_entity_leading_noise,
)
from app.services.research.report_common import dedupe_strings
from app.services.research.report_field_sanitization import (
    ReportFieldSanitizationDependencies,
    sanitize_entity_row,
    sanitize_report_field_rows,
)
from app.services.research.report_row_quality import FIELD_ROW_NOISE_TOKENS, is_actionable_budget_row, looks_like_insufficient
from app.services.research.scope_terms import (
    ScopeTermDependencies,
    build_theme_terms,
    extract_topic_anchor_terms,
    looks_like_scope_prompt_noise,
    theme_labels_from_scope,
)
from app.services.research.source_documents import looks_like_source_artifact_text


@dataclass(frozen=True, slots=True)
class ScopeEntityRuntimeFunctions:
    build_theme_terms: Callable[[str, str | None, dict[str, object]], list[str]]
    extract_topic_anchor_terms: Callable[[str, str | None], list[str]]
    theme_labels_from_scope: Callable[..., list[str]]
    extract_rank_entity_name: Callable[[str], str]
    looks_like_scope_prompt_noise: Callable[[str], bool]
    looks_like_placeholder_entity_name: Callable[[str], bool]
    looks_like_fragment_entity_name: Callable[[str], bool]
    contains_low_value_entity_token: Callable[[str], bool]
    is_trustworthy_scope_client_name: Callable[..., bool]
    is_theme_aligned_entity_name: Callable[..., bool]
    is_lightweight_entity_name: Callable[[str], bool]
    sanitize_entity_row: Callable[[str, str], str]
    sanitize_report_field_rows: Callable[[str, Iterable[str]], list[str]]


def scope_term_dependencies() -> ScopeTermDependencies:
    return ScopeTermDependencies(
        dedupe_strings=dedupe_strings,
        is_plausible_entity_name=is_plausible_entity_name,
        is_lightweight_entity_name=is_lightweight_entity_name,
        looks_like_fragment_entity_name=looks_like_fragment_entity_name,
        contains_low_value_entity_token=contains_low_value_entity_token,
        org_pattern=ORG_PATTERN,
        compact_entity_pattern=COMPACT_ENTITY_PATTERN,
        query_noise_suffixes=QUERY_NOISE_SUFFIXES,
        scope_prompt_noise_prefixes=SCOPE_PROMPT_NOISE_PREFIXES,
        scope_prompt_noise_tokens=SCOPE_PROMPT_NOISE_TOKENS,
        scope_prompt_noise_regexes=SCOPE_PROMPT_NOISE_REGEXES,
        entity_suffix_tokens=ENTITY_SUFFIX_TOKENS,
        generic_focus_tokens=GENERIC_FOCUS_TOKENS,
        invalid_company_anchor_phrases=INVALID_COMPANY_ANCHOR_PHRASES,
        industry_scope_aliases=INDUSTRY_SCOPE_ALIASES,
        theme_generic_suppressions=THEME_GENERIC_SUPPRESSIONS,
        special_entity_aliases=SPECIAL_ENTITY_ALIASES,
        generic_company_anchor_tokens=GENERIC_COMPANY_ANCHOR_TOKENS,
        known_lightweight_entity_names=KNOWN_LIGHTWEIGHT_ENTITY_NAMES,
    )


def report_field_sanitization_dependencies() -> ReportFieldSanitizationDependencies:
    scope_deps = scope_term_dependencies()
    return ReportFieldSanitizationDependencies(
        looks_like_insufficient=looks_like_insufficient,
        looks_like_source_artifact_text=looks_like_source_artifact_text,
        looks_like_placeholder_contact_row=looks_like_placeholder_contact_row,
        contains_low_value_entity_token=contains_low_value_entity_token,
        is_plausible_entity_name=is_plausible_entity_name,
        is_lightweight_entity_name=is_lightweight_entity_name,
        extract_rank_entity_name=extract_rank_entity_name,
        fallback_entity_name_from_row=fallback_entity_name_from_row,
        strip_entity_leading_noise=strip_entity_leading_noise,
        looks_like_fragment_entity_name=looks_like_fragment_entity_name,
        looks_like_scope_prompt_noise=lambda value: looks_like_scope_prompt_noise(
            value,
            deps=scope_deps,
        ),
        looks_like_placeholder_entity_name=looks_like_placeholder_entity_name,
        is_actionable_budget_row=is_actionable_budget_row,
        entity_canonical_key=entity_canonical_key,
        email_pattern=EMAIL_PATTERN,
        phone_pattern=PHONE_PATTERN,
        department_pattern=DEPARTMENT_PATTERN,
        generic_content_domains=GENERIC_CONTENT_DOMAINS,
        non_contact_source_label_tokens=NON_CONTACT_SOURCE_LABEL_TOKENS,
        contact_row_hint_tokens=CONTACT_ROW_HINT_TOKENS,
        contact_page_tokens=CONTACT_PAGE_TOKENS,
        department_hint_tokens=DEPARTMENT_HINT_TOKENS,
        entity_role_fields=ENTITY_ROLE_FIELDS,
        entity_role_name_hints=ENTITY_ROLE_NAME_HINTS,
        entity_role_context_tokens=ENTITY_ROLE_CONTEXT_TOKENS,
        partner_connector_aliases=PARTNER_CONNECTOR_ALIASES,
        field_row_noise_tokens=FIELD_ROW_NOISE_TOKENS,
        case_hint_tokens=CASE_HINT_TOKENS,
        product_hint_tokens=PRODUCT_HINT_TOKENS,
    )


def scope_entity_runtime_functions() -> ScopeEntityRuntimeFunctions:
    scope_deps = scope_term_dependencies()
    field_deps = report_field_sanitization_dependencies()

    def bound_build_theme_terms(
        keyword: str,
        research_focus: str | None,
        scope_hints: dict[str, object],
    ) -> list[str]:
        return build_theme_terms(keyword, research_focus, scope_hints, deps=scope_deps)

    def bound_theme_labels_from_scope(
        scope_hints: dict[str, object],
        *,
        keyword: str,
        research_focus: str | None,
    ) -> list[str]:
        return theme_labels_from_scope(
            scope_hints,
            keyword=keyword,
            research_focus=research_focus,
            deps=scope_deps,
        )

    def bound_extract_topic_anchor_terms(keyword: str, research_focus: str | None) -> list[str]:
        return extract_topic_anchor_terms(keyword, research_focus, deps=scope_deps)

    @lru_cache(maxsize=8192)
    def bound_looks_like_scope_prompt_noise(value: str) -> bool:
        return looks_like_scope_prompt_noise(value, deps=scope_deps)

    @lru_cache(maxsize=16384)
    def bound_sanitize_entity_row(field_key: str, value: str) -> str:
        return sanitize_entity_row(field_key, value, deps=field_deps)

    def bound_sanitize_report_field_rows(field_key: str, values: Iterable[str]) -> list[str]:
        return sanitize_report_field_rows(field_key, values, deps=field_deps)

    def bound_is_trustworthy_scope_client_name(
        value: str,
        *,
        theme_labels: list[str] | None = None,
    ) -> bool:
        return is_trustworthy_scope_client_name(
            value,
            theme_labels=theme_labels,
            looks_like_scope_prompt_noise=bound_looks_like_scope_prompt_noise,
        )

    return ScopeEntityRuntimeFunctions(
        build_theme_terms=bound_build_theme_terms,
        extract_topic_anchor_terms=bound_extract_topic_anchor_terms,
        theme_labels_from_scope=bound_theme_labels_from_scope,
        extract_rank_entity_name=extract_rank_entity_name,
        looks_like_scope_prompt_noise=bound_looks_like_scope_prompt_noise,
        looks_like_placeholder_entity_name=looks_like_placeholder_entity_name,
        looks_like_fragment_entity_name=looks_like_fragment_entity_name,
        contains_low_value_entity_token=contains_low_value_entity_token,
        is_trustworthy_scope_client_name=bound_is_trustworthy_scope_client_name,
        is_theme_aligned_entity_name=is_theme_aligned_entity_name,
        is_lightweight_entity_name=is_lightweight_entity_name,
        sanitize_entity_row=bound_sanitize_entity_row,
        sanitize_report_field_rows=bound_sanitize_report_field_rows,
    )
