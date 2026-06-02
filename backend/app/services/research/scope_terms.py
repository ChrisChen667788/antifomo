from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Pattern
import re

from app.services.content_extractor import normalize_text


@dataclass(frozen=True, slots=True)
class ScopeTermDependencies:
    dedupe_strings: Callable[[Iterable[str], int], list[str]]
    is_plausible_entity_name: Callable[[str], bool]
    is_lightweight_entity_name: Callable[[str], bool]
    looks_like_fragment_entity_name: Callable[[str], bool]
    contains_low_value_entity_token: Callable[[str], bool]
    org_pattern: Pattern[str]
    compact_entity_pattern: Pattern[str]
    query_noise_suffixes: tuple[str, ...]
    scope_prompt_noise_prefixes: tuple[str, ...]
    scope_prompt_noise_tokens: tuple[str, ...]
    scope_prompt_noise_regexes: tuple[str, ...]
    entity_suffix_tokens: tuple[str, ...]
    generic_focus_tokens: set[str]
    invalid_company_anchor_phrases: tuple[str, ...]
    industry_scope_aliases: dict[str, tuple[str, ...]]
    theme_generic_suppressions: dict[str, tuple[str, ...]]
    special_entity_aliases: tuple[str, ...]
    generic_company_anchor_tokens: tuple[str, ...]
    known_lightweight_entity_names: set[str]


def tokenize_for_match(*values: str) -> list[str]:
    text = normalize_text(" ".join(values))
    if not text:
        return []
    rough = re.split(r"[\s,，、/|:：;；（）()]+", text)
    tokens = [token.strip() for token in rough if len(token.strip()) >= 2]
    compact = re.sub(r"\s+", "", text)
    if 2 <= len(compact) <= 24:
        tokens.append(compact)
    return list(dict.fromkeys(tokens))


def looks_like_scope_prompt_noise(value: str, *, deps: ScopeTermDependencies) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    lowered = normalized.lower()
    if any(lowered.startswith(prefix) for prefix in [item.lower() for item in deps.scope_prompt_noise_prefixes]):
        return True
    if any(token.lower() in lowered for token in deps.scope_prompt_noise_tokens):
        return True
    if any(re.search(pattern, lowered, flags=re.IGNORECASE) for pattern in deps.scope_prompt_noise_regexes):
        return True
    if "的" in normalized and not any(token in normalized for token in deps.entity_suffix_tokens):
        return True
    if any(token in normalized for token in ("哪些", "如何", "怎么", "需求", "预算", "招投标", "找客户", "找项目", "哪位领导")):
        return True
    if (
        any(token in normalized for token in ("和", "及", "与"))
        and any(token in normalized for token in ("全球", "大型", "国际", "重点"))
        and not any(token in normalized for token in ("集团", "公司", "局", "委", "办", "中心", "大学", "医院"))
    ):
        return True
    return False


def strip_query_noise(value: str, *, deps: ScopeTermDependencies) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    stripped = text
    for suffix in deps.query_noise_suffixes:
        stripped = re.sub(f"{re.escape(suffix)}$", "", stripped, flags=re.IGNORECASE)
    stripped = re.sub(r"(相关|相關|关于|關於)$", "", stripped, flags=re.IGNORECASE)
    return normalize_text(stripped) or text


def sanitize_research_focus_text(value: str | None, *, deps: ScopeTermDependencies) -> str:
    text = strip_query_noise(value or "", deps=deps)
    if not text:
        return ""
    negative_scope_phrases = (
        "不要扩展到",
        "不要扩展至",
        "不扩展到",
        "不扩展至",
        "不要包含",
        "不包含",
        "不考虑",
        "排除",
        "剔除",
    )
    for prefix in ("重点关注:", "重点关注：", "包括但不限于", "优先关注", "最好精确到", "精确到"):
        if text.startswith(prefix):
            text = normalize_text(text[len(prefix) :])
    segments = re.split(r"[，,；;。]+", text)
    cleaned_segments: list[str] = []
    for segment in segments:
        normalized = normalize_text(segment)
        if not normalized:
            continue
        if any(phrase in normalized for phrase in negative_scope_phrases):
            continue
        if any(phrase in normalized for phrase in deps.invalid_company_anchor_phrases):
            continue
        if looks_like_scope_prompt_noise(normalized, deps=deps):
            continue
        cleaned_segments.append(normalized)
    compact_tokens = [
        token
        for token in tokenize_for_match(" ".join(cleaned_segments))
        if token not in deps.generic_focus_tokens
        and len(normalize_text(token)) >= 2
        and not any(phrase in normalize_text(token) for phrase in deps.invalid_company_anchor_phrases)
    ]
    if compact_tokens:
        return normalize_text(" ".join(deps.dedupe_strings(compact_tokens, 8)))
    return normalize_text(" ".join(cleaned_segments[:2]))


def extract_explicit_exclusion_terms(value: str | None, *, deps: ScopeTermDependencies) -> list[str]:
    text = normalize_text(value or "")
    if not text:
        return []
    segments = re.split(r"[，,；;。]+", text)
    terms: list[str] = []
    negative_scope_phrases = (
        "不要扩展到",
        "不要扩展至",
        "不扩展到",
        "不扩展至",
        "不要包含",
        "不包含",
        "不考虑",
        "排除",
        "剔除",
    )
    for segment in segments:
        normalized = normalize_text(segment)
        if not normalized:
            continue
        for prefix in negative_scope_phrases:
            if normalized.startswith(prefix):
                tail = normalize_text(normalized[len(prefix) :])
                if not tail:
                    continue
                for part in re.split(r"[、/\\| ]+", tail):
                    candidate = normalize_text(part)
                    if candidate and candidate not in deps.generic_focus_tokens:
                        terms.append(candidate)
                break
    return deps.dedupe_strings(terms, 8)


def extract_topic_anchor_terms(keyword: str, research_focus: str | None, *, deps: ScopeTermDependencies) -> list[str]:
    keyword_seed = strip_query_noise(keyword, deps=deps)
    focus_seed = sanitize_research_focus_text(research_focus, deps=deps)
    anchors: list[str] = []
    for seed in (keyword_seed, focus_seed):
        if not seed:
            continue
        if len(seed) <= 18 and len(seed.split()) <= 4:
            anchors.append(seed)
        compact = re.sub(r"\s+", "", seed)
        if 2 <= len(compact) <= 24:
            anchors.append(compact)
        anchors.extend(
            token
            for token in tokenize_for_match(seed)
            if token not in deps.generic_focus_tokens
            and len(normalize_text(token)) >= 2
            and not any(phrase in normalize_text(token) for phrase in deps.invalid_company_anchor_phrases)
        )
    lowered_seed = normalize_text(f"{keyword_seed} {focus_seed}").lower()
    matched_labels: list[str] = []
    for label, aliases in deps.industry_scope_aliases.items():
        if any(alias.lower() in lowered_seed for alias in aliases):
            matched_labels.append(label)
            anchors.append(label)
            anchors.extend(aliases)
    for dominant, suppressed in deps.theme_generic_suppressions.items():
        if dominant in matched_labels:
            anchors = [
                anchor
                for anchor in anchors
                if normalize_text(anchor) == dominant
                or normalize_text(anchor) not in suppressed
                and normalize_text(anchor).lower() not in {
                    normalize_text(alias).lower()
                    for suppressed_label in suppressed
                    for alias in deps.industry_scope_aliases.get(suppressed_label, ())
                    if normalize_text(alias)
                }
            ]
    return list(dict.fromkeys(normalize_text(anchor) for anchor in anchors if normalize_text(anchor)))


def extract_company_anchor_terms(keyword: str, research_focus: str | None, *, deps: ScopeTermDependencies) -> list[str]:
    keyword_seed = normalize_text(strip_query_noise(keyword, deps=deps))
    focus_seed = normalize_text(sanitize_research_focus_text(research_focus, deps=deps))
    seed_text = normalize_text(" ".join(item for item in [keyword_seed, focus_seed] if normalize_text(item)))
    if not keyword_seed and not focus_seed:
        return []
    anchors: list[str] = []
    for alias in deps.special_entity_aliases:
        if alias in seed_text:
            anchors.append(alias)
    for match in deps.org_pattern.findall(keyword_seed):
        normalized = normalize_text(match)
        if deps.is_plausible_entity_name(normalized) or deps.is_lightweight_entity_name(normalized):
            anchors.append(normalized)
    for match in deps.org_pattern.findall(focus_seed):
        normalized = normalize_text(match)
        if (
            normalized in deps.special_entity_aliases
            or any(normalized.endswith(token) for token in ("集团", "公司", "有限公司", "股份有限公司", "研究院", "研究所"))
        ) and (deps.is_plausible_entity_name(normalized) or deps.is_lightweight_entity_name(normalized)):
            anchors.append(normalized)
    for match in deps.compact_entity_pattern.findall(keyword_seed):
        normalized = normalize_text(match)
        if deps.is_plausible_entity_name(normalized) or deps.is_lightweight_entity_name(normalized):
            anchors.append(normalized)
    for token in tokenize_for_match(keyword_seed):
        normalized = normalize_text(token)
        lowered = normalized.lower()
        if not normalized or normalized in deps.generic_focus_tokens:
            continue
        if any(phrase in normalized for phrase in deps.invalid_company_anchor_phrases):
            continue
        if looks_like_scope_prompt_noise(normalized, deps=deps):
            continue
        if normalized in deps.special_entity_aliases:
            anchors.append(normalized)
            continue
        if any(theme in lowered for theme in deps.generic_company_anchor_tokens):
            continue
        if any(theme in normalized for theme in deps.generic_focus_tokens):
            continue
        if deps.is_lightweight_entity_name(normalized):
            anchors.append(normalized)
    cleaned: list[str] = []
    for anchor in anchors:
        normalized = normalize_text(anchor)
        if not normalized:
            continue
        if any(phrase in normalized for phrase in deps.invalid_company_anchor_phrases):
            continue
        if looks_like_scope_prompt_noise(normalized, deps=deps):
            continue
        if deps.looks_like_fragment_entity_name(normalized):
            continue
        if deps.contains_low_value_entity_token(normalized):
            continue
        if normalized.startswith(("如", "例如", "比如", "诸如", "優先給", "优先给", "官方", "公开")):
            continue
        cleaned.append(normalized)
    return list(dict.fromkeys(cleaned))


def clean_company_anchor_candidate(value: str, *, deps: ScopeTermDependencies) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    if looks_like_scope_prompt_noise(normalized, deps=deps):
        return ""
    normalized = re.sub(r"^(分析|梳理|研究|盘点|聚焦|关注|围绕|拆解|追踪|观察|看|找|筛选)", "", normalized)
    normalized = re.sub(r"(?:这些|这类|相关)?公司.*$", "", normalized)
    normalized = re.sub(r"(?:的)?(?:AI|AIGC)?商机.*$", "", normalized, flags=re.IGNORECASE)
    normalized = re.sub(r"(合作平台|平台合作|商业化路径|商业模式|机会点|落地路径|案例分析).*$", "", normalized)
    normalized = normalize_text(normalized.strip("：:，,、/| "))
    if looks_like_scope_prompt_noise(normalized, deps=deps):
        return ""
    return normalized


def resolved_company_anchor_terms(
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object] | None,
    *,
    deps: ScopeTermDependencies,
) -> list[str]:
    scope = scope_hints or {}
    candidates: list[str] = []
    candidates.extend(extract_company_anchor_terms(keyword, research_focus, deps=deps))
    candidates.extend(normalize_text(str(item)) for item in scope.get("company_anchors", []) or [])
    candidates.extend(normalize_text(str(item)) for item in scope.get("clients", []) or [])
    candidates.extend(normalize_text(str(item)) for item in scope.get("seed_companies", []) or [])
    cleaned: list[str] = []
    generic_company_like_tokens = ("头部", "行业", "赛道", "领域", "玩家", "公司名单", "企业名单", "商业化", "商机")
    generic_theme_tokens = ("ai漫剧", "漫剧", "aigc", "动画", "短剧")
    company_suffixes = ("集团", "公司", "有限公司", "股份有限公司", "科技", "传媒", "控股", "影业", "视频")
    for candidate in candidates:
        normalized = clean_company_anchor_candidate(candidate, deps=deps)
        lowered = normalized.lower()
        if not normalized:
            continue
        if any(token in lowered for token in generic_company_like_tokens):
            continue
        if any(token in lowered for token in generic_theme_tokens) and normalized not in deps.known_lightweight_entity_names:
            continue
        if normalized in deps.known_lightweight_entity_names or normalized in deps.special_entity_aliases:
            cleaned.append(normalized)
            continue
        if any(normalized.endswith(token) for token in company_suffixes):
            cleaned.append(normalized)
            continue
        if re.fullmatch(r"[A-Za-z0-9\u4e00-\u9fa5·]{2,10}", normalized):
            cleaned.append(normalized)
    return deps.dedupe_strings(cleaned, 12)


def build_theme_terms(
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    *,
    deps: ScopeTermDependencies,
) -> list[str]:
    terms = extract_topic_anchor_terms(keyword, research_focus or "", deps=deps)
    for label in scope_hints.get("industries", []) or []:
        normalized = normalize_text(str(label))
        if not normalized:
            continue
        terms.append(normalized)
        for alias in deps.industry_scope_aliases.get(normalized, ()):
            terms.append(alias)
    for item in scope_hints.get("strategy_must_include_terms", []) or []:
        normalized = normalize_text(str(item))
        if normalized:
            terms.append(normalized)
    for region in scope_hints.get("regions", []) or []:
        normalized = normalize_text(str(region))
        if normalized:
            terms.append(normalized)
    return list(dict.fromkeys(term.lower() for term in terms if len(normalize_text(term)) >= 2))


def build_strict_theme_terms(scope_hints: dict[str, object]) -> list[str]:
    terms = [
        normalize_text(str(item)).lower()
        for item in scope_hints.get("strategy_must_include_terms", []) or []
        if normalize_text(str(item))
    ]
    return list(dict.fromkeys(terms))
