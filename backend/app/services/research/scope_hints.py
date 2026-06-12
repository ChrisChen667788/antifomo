from __future__ import annotations

from collections import Counter
from collections.abc import Iterable

from app.services.content_extractor import normalize_text
from app.services.research.entity_policy import (
    COMPACT_ENTITY_PATTERN,
    ENTITY_SUFFIX_TOKENS,
    INDUSTRY_SCOPE_ALIASES,
    KNOWN_LIGHTWEIGHT_ENTITY_NAMES,
    ORG_PATTERN,
    REGION_TOKENS,
    SPECIAL_ENTITY_ALIASES,
    THEME_COMPANY_PUBLIC_SOURCE_SEEDS,
    contains_low_value_entity_token,
    extract_rank_entity_name,
    fallback_entity_name_from_row,
    is_lightweight_entity_name,
    is_plausible_entity_name,
    is_theme_aligned_entity_name,
    is_trustworthy_scope_client_name,
    looks_like_fragment_entity_name,
    looks_like_placeholder_entity_name,
    strip_entity_leading_noise,
    trim_product_spec_from_entity_name,
)
from app.services.research.entity_heuristics import (
    extract_rank_entity_candidates as heuristic_extract_rank_entity_candidates,
    resolve_known_org_name,
)
from app.services.research.industry_methodology import build_industry_methodology_scope_hints
from app.services.research.report_common import dedupe_strings
from app.services.research.report_row_quality import looks_like_insufficient
from app.services.research.report_scope_runtime import prune_industry_hints
from app.services.research.scope_entity_runtime_dependencies import scope_term_dependencies
from app.services.research.scope_terms import (
    extract_company_anchor_terms,
    extract_explicit_exclusion_terms,
    looks_like_scope_prompt_noise,
    sanitize_research_focus_text,
    theme_labels_from_scope,
)
from app.services.research.source_documents import SourceDocument, looks_like_source_artifact_text, source_document_text


REGION_SCOPE_ALIASES: dict[str, tuple[str, ...]] = {
    "长三角": ("长三角", "上海", "江苏", "浙江", "安徽", "南京", "苏州", "杭州", "宁波", "无锡", "合肥"),
    "京津冀": ("京津冀", "北京", "天津", "河北"),
    "粤港澳": ("粤港澳", "广东", "广州", "深圳", "珠海", "佛山", "东莞", "中山", "香港", "澳门"),
    "成渝": ("成渝", "成都", "重庆", "四川"),
}
THEME_STRICT_MUST_INCLUDE_TERMS: dict[str, tuple[str, ...]] = {
    "AI漫剧": ("ai漫剧", "漫剧", "ai短剧", "aigc短剧", "aigc漫剧", "ai动画", "aigc动画", "动漫短剧", "漫画短剧"),
}
COMPANY_ENTITY_QUERY_TOKENS = (
    "公司", "企业", "厂商", "平台方", "平台", "工作室", "发行方", "版权方", "内容方", "甲方公司",
    "公司名单", "企业名单", "头部玩家", "company", "companies", "player", "players", "studio",
)
HEAD_COMPANY_QUERY_TOKENS = (
    "头部", "龙头", "领先", "头部玩家", "top", "leading", "leader", "leaders", "头部公司",
)


def sanitize_research_focus_text_bound(value: str | None) -> str:
    return sanitize_research_focus_text(value, deps=scope_term_dependencies())


def extract_explicit_exclusion_terms_bound(value: str | None) -> list[str]:
    return extract_explicit_exclusion_terms(value, deps=scope_term_dependencies())


def extract_company_anchor_terms_bound(keyword: str, research_focus: str | None) -> list[str]:
    return extract_company_anchor_terms(keyword, research_focus, deps=scope_term_dependencies())


def theme_labels_from_scope_bound(
    scope_hints: dict[str, object],
    *,
    keyword: str,
    research_focus: str | None,
) -> list[str]:
    return theme_labels_from_scope(
        scope_hints,
        keyword=keyword,
        research_focus=research_focus,
        deps=scope_term_dependencies(),
    )


def safe_int(value: object, default: int, *, minimum: int = 0, maximum: int = 1000) -> int:
    try:
        parsed = int(value if value is not None else default)
    except (TypeError, ValueError):
        parsed = default
    return max(minimum, min(maximum, parsed))


def expand_region_scope_terms(regions: list[str]) -> list[str]:
    expanded: list[str] = []
    for raw_region in regions:
        normalized = normalize_text(raw_region)
        if not normalized:
            continue
        expanded.append(normalized)
        expanded.extend(REGION_SCOPE_ALIASES.get(normalized, ()))
    return dedupe_strings(expanded, 24)


def infer_company_query_preferences(seed_text: str, *, theme_labels: list[str]) -> tuple[bool, bool]:
    lowered = normalize_text(seed_text).lower()
    prefer_company_entities = any(token in lowered for token in COMPANY_ENTITY_QUERY_TOKENS)
    prefer_head_companies = prefer_company_entities and any(token in lowered for token in HEAD_COMPANY_QUERY_TOKENS)
    if not prefer_company_entities and "AI漫剧" in theme_labels:
        prefer_company_entities = any(
            token in lowered
            for token in ("发行方", "版权方", "平台方", "工作室", "内容平台", "短剧平台", "动漫平台")
        )
    return prefer_company_entities, prefer_head_companies


def looks_like_target_scope_entity_name(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized or not is_plausible_entity_name(normalized):
        return False
    if normalized in SPECIAL_ENTITY_ALIASES and normalized not in {"中国移动", "中国电信", "中国联通"}:
        return False
    target_tokens = (
        "政府", "人民政府", "局", "委", "厅", "办", "中心", "医院", "大学", "学院", "学校",
        "银行", "集团", "城投", "交投", "水务", "地铁", "文旅", "医药", "药业", "制药", "生物",
    )
    vendor_only_tokens = ("OpenAI", "Microsoft", "Azure", "云", "软件", "信息", "算法", "模型")
    if any(token in normalized for token in target_tokens):
        return True
    if any(token in normalized for token in vendor_only_tokens):
        return False
    return False


def extract_rank_entity_candidates(
    value: str,
    *,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    text = normalize_text(value)
    if not text:
        return []
    candidates = [*ORG_PATTERN.findall(text), *COMPACT_ENTITY_PATTERN.findall(text)]
    candidates.extend(alias for alias in KNOWN_LIGHTWEIGHT_ENTITY_NAMES if alias in text)
    candidates.extend(heuristic_extract_rank_entity_candidates(text, scope_hints=scope_hints))
    filtered: list[str] = []
    for candidate in candidates:
        normalized = resolve_known_org_name(candidate, scope_hints=scope_hints)
        normalized = strip_entity_leading_noise(trim_product_spec_from_entity_name(normalized))
        if not (is_plausible_entity_name(normalized) or is_lightweight_entity_name(normalized)):
            continue
        if looks_like_fragment_entity_name(normalized):
            continue
        if (
            any(connector in normalized for connector in ("与", "及", "和"))
            and normalized not in SPECIAL_ENTITY_ALIASES
            and not any(token in normalized for token in ENTITY_SUFFIX_TOKENS)
        ):
            continue
        filtered.append(normalized)
    return dedupe_strings(filtered, 5)


def extract_org_candidates(
    sources: list[SourceDocument],
    *,
    limit: int,
    scope_hints: dict[str, object] | None = None,
) -> list[str]:
    candidates: list[str] = []
    for source in sources:
        candidates.extend(
            extract_rank_entity_candidates(
                source_document_text(source),
                scope_hints=scope_hints,
            )
        )
    return dedupe_strings(candidates, limit)


def clean_scope_entity_names(
    values: Iterable[str],
    *,
    limit: int = 4,
    theme_labels: list[str] | None = None,
) -> list[str]:
    scope_deps = scope_term_dependencies()

    def is_scope_prompt_noise(value: str) -> bool:
        return looks_like_scope_prompt_noise(value, deps=scope_deps)

    cleaned: list[str] = []
    for value in values:
        normalized = normalize_text(str(value))
        if (
            not normalized
            or looks_like_insufficient(normalized)
            or is_scope_prompt_noise(normalized)
            or looks_like_source_artifact_text(normalized)
        ):
            continue
        candidate = extract_rank_entity_name(normalized) or fallback_entity_name_from_row(normalized)
        candidate = strip_entity_leading_noise(candidate)
        if (
            not candidate
            or looks_like_fragment_entity_name(candidate)
            or contains_low_value_entity_token(candidate)
            or is_scope_prompt_noise(candidate)
            or looks_like_placeholder_entity_name(candidate)
        ):
            continue
        if not is_plausible_entity_name(candidate) and not is_lightweight_entity_name(candidate):
            continue
        if not is_trustworthy_scope_client_name(
            candidate,
            theme_labels=theme_labels,
            looks_like_scope_prompt_noise=is_scope_prompt_noise,
        ):
            continue
        cleaned.append(candidate)
    return dedupe_strings(cleaned, limit)


def source_theme_match_score(
    source: SourceDocument,
    *,
    theme_terms: list[str],
    scope_hints: dict[str, object],
) -> int:
    if not theme_terms:
        return 0
    lowered = source_document_text(source).lower()
    title_lower = normalize_text(source.title).lower()
    label_lower = normalize_text(source.source_label or "").lower()
    regions = [
        item.lower()
        for item in expand_region_scope_terms(
            [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
        )
    ]
    clients = [normalize_text(str(item)).lower() for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    exclusion_terms = [
        normalize_text(str(item)).lower()
        for item in scope_hints.get("strategy_exclusion_terms", [])
        if normalize_text(str(item))
    ]
    score = 0
    title_hits = sum(1 for term in theme_terms if term in title_lower)
    body_hits = sum(1 for term in theme_terms if term in lowered)
    label_hits = sum(1 for term in theme_terms if term in label_lower)
    if title_hits:
        score += min(title_hits, 3) * 6
    if body_hits:
        score += min(body_hits, 4) * 4
    if label_hits:
        score += min(label_hits, 2) * 3
    if regions and any(region in lowered for region in regions):
        score += 3
    if clients and any(client in lowered or client in title_lower for client in clients):
        score += 5
    if exclusion_terms and any(term in lowered or term in title_lower for term in exclusion_terms):
        score -= 18
    return score


def infer_input_scope_hints(
    keyword: str,
    research_focus: str | None,
) -> dict[str, object]:
    seed_text = normalize_text(" ".join([keyword, sanitize_research_focus_text_bound(research_focus)]))
    exclusion_terms = extract_explicit_exclusion_terms_bound(research_focus)
    if not seed_text:
        return {
            "regions": [],
            "industries": [],
            "clients": [],
            "company_anchors": [],
            "strategy_must_include_terms": [],
            "strategy_exclusion_terms": exclusion_terms,
            "strategy_query_expansions": [],
            "strategy_scope_summary": "",
            "anchor_text": "",
            "industry_methodology_profile": "",
            "industry_methodology_authority": "",
            "industry_methodology_framework": "",
            "industry_methodology_questions": [],
            "industry_methodology_source_preferences": [],
            "industry_methodology_solution_lenses": [],
            "industry_methodology_sales_lenses": [],
            "industry_methodology_bidding_lenses": [],
            "industry_methodology_outreach_lenses": [],
            "industry_methodology_ecosystem_lenses": [],
        }

    region_hints = dedupe_strings(
        [
            label
            for label, aliases in REGION_SCOPE_ALIASES.items()
            if any(alias in seed_text for alias in aliases)
        ]
        + [region for region in REGION_TOKENS if region in seed_text],
        4,
    )
    industry_hints = prune_industry_hints(
        [
            label
            for label, aliases in INDUSTRY_SCOPE_ALIASES.items()
            if any(alias in seed_text for alias in aliases)
        ]
    )
    theme_labels = dedupe_strings(
        [*industry_hints, *theme_labels_from_scope_bound({}, keyword=keyword, research_focus=research_focus)],
        3,
    )
    prefer_company_entities, prefer_head_companies = infer_company_query_preferences(
        seed_text,
        theme_labels=theme_labels,
    )
    company_anchors = extract_company_anchor_terms_bound(keyword, research_focus)
    client_candidates = [
        item
        for item in company_anchors[:3]
        if is_theme_aligned_entity_name(item, role="target", theme_labels=theme_labels)
    ]
    if not client_candidates:
        client_candidates = dedupe_strings(
            [
                item
                for item in ORG_PATTERN.findall(seed_text)
                if is_theme_aligned_entity_name(item, role="target", theme_labels=theme_labels)
            ],
            3,
        )
    strategy_must_include_terms = dedupe_strings(
        [
            term
            for label in industry_hints
            for term in THEME_STRICT_MUST_INCLUDE_TERMS.get(label, ())
        ],
        8,
    )
    seed_companies = dedupe_strings(
        [
            item
            for label in theme_labels
            for item in THEME_COMPANY_PUBLIC_SOURCE_SEEDS.get(label, ())
        ],
        12,
    )
    methodology_scope_hints = build_industry_methodology_scope_hints(
        keyword=keyword,
        research_focus=research_focus,
        regions=region_hints,
        industries=theme_labels or industry_hints,
        clients=client_candidates,
    )

    return {
        "regions": region_hints,
        "industries": industry_hints,
        "clients": client_candidates,
        "company_anchors": company_anchors[:4],
        "prefer_company_entities": prefer_company_entities,
        "prefer_head_companies": prefer_head_companies,
        "seed_companies": seed_companies if prefer_company_entities or prefer_head_companies else [],
        "strategy_must_include_terms": strategy_must_include_terms,
        "strategy_exclusion_terms": exclusion_terms,
        "strategy_query_expansions": [],
        "strategy_scope_summary": "",
        "anchor_text": normalize_text(" / ".join(region_hints[:2] + industry_hints[:2] + client_candidates[:2])),
        **methodology_scope_hints,
    }


def infer_scope_hints(
    keyword: str,
    research_focus: str | None,
    sources: list[SourceDocument],
) -> dict[str, object]:
    seed_text = normalize_text(
        " ".join([keyword, sanitize_research_focus_text_bound(research_focus)] + [f"{source.title} {source.snippet}" for source in sources[:10]])
    )
    region_counter: Counter[str] = Counter()
    for label, aliases in REGION_SCOPE_ALIASES.items():
        if any(alias in seed_text for alias in aliases):
            region_counter[label] += 4
    for region in REGION_TOKENS:
        if region in seed_text:
            region_counter[region] += 3
    for source in sources:
        text = source_document_text(source)
        for label, aliases in REGION_SCOPE_ALIASES.items():
            if any(alias in text for alias in aliases):
                region_counter[label] += 1
        for region in REGION_TOKENS:
            if region in text:
                region_counter[region] += 1

    region_hints = [region for region, _ in region_counter.most_common(3)]

    normalized_seed = seed_text.lower()
    industry_hints: list[str] = []
    for label, aliases in INDUSTRY_SCOPE_ALIASES.items():
        if any(alias.lower() in normalized_seed for alias in aliases):
            industry_hints.append(label)
    industry_hints = list(dict.fromkeys(industry_hints))[:3]
    theme_labels = dedupe_strings(
        [*industry_hints, *theme_labels_from_scope_bound({}, keyword=keyword, research_focus=research_focus)],
        3,
    )
    prefer_company_entities, prefer_head_companies = infer_company_query_preferences(
        seed_text,
        theme_labels=theme_labels,
    )

    company_anchors = extract_company_anchor_terms_bound(keyword, research_focus)
    org_candidates = extract_org_candidates(sources, limit=24)
    client_candidates = [
        item
        for item in company_anchors[:3]
        if is_theme_aligned_entity_name(item, role="target", theme_labels=theme_labels)
    ]
    if theme_labels:
        client_candidates.extend(
            item
            for item in org_candidates
            if is_theme_aligned_entity_name(item, role="target", theme_labels=theme_labels)
            and looks_like_target_scope_entity_name(item)
        )
    else:
        client_candidates.extend(
            item
            for item in org_candidates
            if any(
                token in item
                for token in ("政府", "局", "委", "办", "中心", "医院", "大学", "银行", "学校", "集团", "城投", "交投", "水务", "地铁")
            )
        )
    client_candidates = dedupe_strings(client_candidates, 3)
    if not client_candidates:
        keyword_orgs = [
            normalize_text(item)
            for item in ORG_PATTERN.findall(seed_text)
            if is_plausible_entity_name(normalize_text(item)) or is_lightweight_entity_name(normalize_text(item))
        ]
        client_candidates = dedupe_strings(
            [
                item
                for item in keyword_orgs
                if is_theme_aligned_entity_name(item, role="target", theme_labels=theme_labels)
            ],
            3,
        )

    seed_companies = dedupe_strings(
        [
            item
            for label in theme_labels
            for item in THEME_COMPANY_PUBLIC_SOURCE_SEEDS.get(label, ())
        ],
        12,
    )
    methodology_scope_hints = build_industry_methodology_scope_hints(
        keyword=keyword,
        research_focus=research_focus,
        regions=region_hints,
        industries=theme_labels or industry_hints,
        clients=client_candidates,
    )

    return {
        "regions": region_hints,
        "industries": industry_hints,
        "clients": client_candidates,
        "company_anchors": company_anchors[:4],
        "prefer_company_entities": prefer_company_entities,
        "prefer_head_companies": prefer_head_companies,
        "seed_companies": seed_companies if prefer_company_entities or prefer_head_companies else [],
        "anchor_text": normalize_text(" / ".join(region_hints[:2] + industry_hints[:2] + client_candidates[:2])),
        **methodology_scope_hints,
    }


def merge_scope_hints(
    base: dict[str, object],
    refined: dict[str, object],
) -> dict[str, object]:
    base_regions = [normalize_text(str(item)) for item in (base.get("regions", []) or []) if normalize_text(str(item))]
    refined_regions = [normalize_text(str(item)) for item in (refined.get("regions", []) or []) if normalize_text(str(item))]
    if base_regions:
        allowed_terms = {item.lower() for item in expand_region_scope_terms(base_regions)}
        region_candidates = list(base_regions)
        region_candidates.extend(
            item
            for item in refined_regions
            if item.lower() in allowed_terms
            or any(alias.lower() in allowed_terms for alias in REGION_SCOPE_ALIASES.get(item, ()))
        )
        regions = dedupe_strings(region_candidates, 3)
    else:
        regions = dedupe_strings([*refined_regions], 3)
    base_industries = [normalize_text(str(item)) for item in (base.get("industries", []) or []) if normalize_text(str(item))]
    refined_industries = [normalize_text(str(item)) for item in (refined.get("industries", []) or []) if normalize_text(str(item))]
    if base_industries:
        allowed_industry_terms = {
            normalize_text(alias)
            for industry in base_industries
            for alias in (industry, *INDUSTRY_SCOPE_ALIASES.get(industry, ()))
            if normalize_text(alias)
        }
        industry_candidates = list(base_industries)
        industry_candidates.extend(
            item
            for item in refined_industries
            if item in allowed_industry_terms
            or any(normalize_text(alias) in allowed_industry_terms for alias in INDUSTRY_SCOPE_ALIASES.get(item, ()))
        )
        industries = prune_industry_hints(industry_candidates)
    else:
        industries = prune_industry_hints(refined_industries)

    base_clients = [normalize_text(str(item)) for item in (base.get("clients", []) or []) if normalize_text(str(item))]
    refined_clients = [normalize_text(str(item)) for item in (refined.get("clients", []) or []) if normalize_text(str(item))]
    if base_clients:
        clients = dedupe_strings(
            [
                *base_clients,
                *[
                    item
                    for item in refined_clients
                    if any(base_client in item or item in base_client for base_client in base_clients)
                ],
            ],
            3,
        )
    else:
        clients = dedupe_strings(refined_clients, 3)

    base_company_anchors = [
        normalize_text(str(item))
        for item in (base.get("company_anchors", []) or [])
        if normalize_text(str(item))
    ]
    refined_company_anchors = [
        normalize_text(str(item))
        for item in (refined.get("company_anchors", []) or [])
        if normalize_text(str(item))
    ]
    if base_company_anchors:
        company_anchors = dedupe_strings(
            [
                *base_company_anchors,
                *[
                    item
                    for item in refined_company_anchors
                    if any(anchor in item or item in anchor for anchor in base_company_anchors)
                ],
            ],
            4,
        )
    else:
        company_anchors = dedupe_strings(refined_company_anchors, 4)
    clients = clean_scope_entity_names(clients, limit=3, theme_labels=industries)
    company_anchors = clean_scope_entity_names(company_anchors, limit=4, theme_labels=industries)
    strategy_must_include_terms = dedupe_strings(
        [*(base.get("strategy_must_include_terms", []) or []), *(refined.get("strategy_must_include_terms", []) or [])],
        8,
    )
    strategy_exclusion_terms = dedupe_strings(
        [*(base.get("strategy_exclusion_terms", []) or []), *(refined.get("strategy_exclusion_terms", []) or [])],
        8,
    )
    strategy_query_expansions = dedupe_strings(
        [
            item
            for item in [*(base.get("strategy_query_expansions", []) or []), *(refined.get("strategy_query_expansions", []) or [])]
            if normalize_text(str(item))
            and not any(exclusion in normalize_text(str(item)) for exclusion in strategy_exclusion_terms)
        ],
        10,
    )
    strategy_scope_summary = normalize_text(str(refined.get("strategy_scope_summary", ""))) or normalize_text(
        str(base.get("strategy_scope_summary", ""))
    )
    prefer_company_entities = bool(base.get("prefer_company_entities")) or bool(refined.get("prefer_company_entities"))
    prefer_head_companies = bool(base.get("prefer_head_companies")) or bool(refined.get("prefer_head_companies"))
    seed_companies = dedupe_strings(
        [
            normalize_text(str(item))
            for item in [*(base.get("seed_companies", []) or []), *(refined.get("seed_companies", []) or [])]
            if normalize_text(str(item))
        ],
        12,
    )
    industry_methodology_profile = normalize_text(str(refined.get("industry_methodology_profile", ""))) or normalize_text(
        str(base.get("industry_methodology_profile", ""))
    )
    industry_methodology_authority = normalize_text(str(refined.get("industry_methodology_authority", ""))) or normalize_text(
        str(base.get("industry_methodology_authority", ""))
    )
    industry_methodology_framework = normalize_text(str(refined.get("industry_methodology_framework", ""))) or normalize_text(
        str(base.get("industry_methodology_framework", ""))
    )
    industry_methodology_questions = dedupe_strings(
        [*(base.get("industry_methodology_questions", []) or []), *(refined.get("industry_methodology_questions", []) or [])],
        6,
    )
    industry_methodology_source_preferences = dedupe_strings(
        [
            *(base.get("industry_methodology_source_preferences", []) or []),
            *(refined.get("industry_methodology_source_preferences", []) or []),
        ],
        6,
    )
    industry_methodology_solution_lenses = dedupe_strings(
        [
            *(base.get("industry_methodology_solution_lenses", []) or []),
            *(refined.get("industry_methodology_solution_lenses", []) or []),
        ],
        6,
    )
    industry_methodology_sales_lenses = dedupe_strings(
        [
            *(base.get("industry_methodology_sales_lenses", []) or []),
            *(refined.get("industry_methodology_sales_lenses", []) or []),
        ],
        6,
    )
    industry_methodology_bidding_lenses = dedupe_strings(
        [
            *(base.get("industry_methodology_bidding_lenses", []) or []),
            *(refined.get("industry_methodology_bidding_lenses", []) or []),
        ],
        6,
    )
    industry_methodology_outreach_lenses = dedupe_strings(
        [
            *(base.get("industry_methodology_outreach_lenses", []) or []),
            *(refined.get("industry_methodology_outreach_lenses", []) or []),
        ],
        6,
    )
    industry_methodology_ecosystem_lenses = dedupe_strings(
        [
            *(base.get("industry_methodology_ecosystem_lenses", []) or []),
            *(refined.get("industry_methodology_ecosystem_lenses", []) or []),
        ],
        6,
    )
    runtime_strategy_applied_lanes = dedupe_strings(
        [
            *(base.get("runtime_strategy_applied_lanes", []) or []),
            *(refined.get("runtime_strategy_applied_lanes", []) or []),
        ],
        8,
    )
    runtime_strategy_fallback_lanes = dedupe_strings(
        [
            *(base.get("runtime_strategy_fallback_lanes", []) or []),
            *(refined.get("runtime_strategy_fallback_lanes", []) or []),
        ],
        8,
    )
    runtime_strategy_warnings = dedupe_strings(
        [
            *(base.get("runtime_strategy_warnings", []) or []),
            *(refined.get("runtime_strategy_warnings", []) or []),
        ],
        8,
    )
    runtime_strategy_status = normalize_text(str(refined.get("runtime_strategy_status") or base.get("runtime_strategy_status") or ""))
    runtime_query_recovery_enabled = bool(base.get("runtime_query_recovery_enabled")) or bool(
        refined.get("runtime_query_recovery_enabled")
    )
    runtime_source_reranker_enabled = bool(base.get("runtime_source_reranker_enabled")) or bool(
        refined.get("runtime_source_reranker_enabled")
    )
    runtime_corrective_query_limit = safe_int(
        refined.get("runtime_corrective_query_limit") or base.get("runtime_corrective_query_limit"),
        0,
        minimum=0,
        maximum=12,
    )
    runtime_public_expansion_on_watch = bool(base.get("runtime_public_expansion_on_watch")) or bool(
        refined.get("runtime_public_expansion_on_watch")
    )
    runtime_reranker_adapter = normalize_text(str(refined.get("runtime_reranker_adapter") or base.get("runtime_reranker_adapter") or ""))
    runtime_reranker_backend = normalize_text(str(refined.get("runtime_reranker_backend") or base.get("runtime_reranker_backend") or ""))
    runtime_reranker_top_k = safe_int(
        refined.get("runtime_reranker_top_k") or base.get("runtime_reranker_top_k"),
        0,
        minimum=0,
        maximum=20,
    )
    runtime_reranker_fallback_adapter = normalize_text(
        str(refined.get("runtime_reranker_fallback_adapter") or base.get("runtime_reranker_fallback_adapter") or "")
    )
    runtime_official_source_bias = bool(base.get("runtime_official_source_bias")) or bool(
        refined.get("runtime_official_source_bias")
    )
    enable_cross_encoder_rerank = bool(base.get("enable_cross_encoder_rerank")) or bool(
        refined.get("enable_cross_encoder_rerank")
    )
    cross_encoder_rerank = bool(base.get("cross_encoder_rerank")) or bool(refined.get("cross_encoder_rerank"))
    anchor_text = normalize_text(" / ".join(regions[:2] + industries[:2] + clients[:2]))
    if not anchor_text:
        anchor_text = normalize_text(str(refined.get("anchor_text", ""))) or normalize_text(str(base.get("anchor_text", "")))
    return {
        "regions": regions,
        "industries": industries,
        "clients": clients,
        "company_anchors": company_anchors,
        "prefer_company_entities": prefer_company_entities,
        "prefer_head_companies": prefer_head_companies,
        "seed_companies": seed_companies,
        "strategy_must_include_terms": strategy_must_include_terms,
        "strategy_exclusion_terms": strategy_exclusion_terms,
        "strategy_query_expansions": strategy_query_expansions,
        "strategy_scope_summary": strategy_scope_summary,
        "anchor_text": anchor_text,
        "industry_methodology_profile": industry_methodology_profile,
        "industry_methodology_authority": industry_methodology_authority,
        "industry_methodology_framework": industry_methodology_framework,
        "industry_methodology_questions": industry_methodology_questions,
        "industry_methodology_source_preferences": industry_methodology_source_preferences,
        "industry_methodology_solution_lenses": industry_methodology_solution_lenses,
        "industry_methodology_sales_lenses": industry_methodology_sales_lenses,
        "industry_methodology_bidding_lenses": industry_methodology_bidding_lenses,
        "industry_methodology_outreach_lenses": industry_methodology_outreach_lenses,
        "industry_methodology_ecosystem_lenses": industry_methodology_ecosystem_lenses,
        "runtime_strategy_status": runtime_strategy_status,
        "runtime_strategy_applied_lanes": runtime_strategy_applied_lanes,
        "runtime_strategy_fallback_lanes": runtime_strategy_fallback_lanes,
        "runtime_strategy_warnings": runtime_strategy_warnings,
        "runtime_query_recovery_enabled": runtime_query_recovery_enabled,
        "runtime_source_reranker_enabled": runtime_source_reranker_enabled,
        "runtime_corrective_query_limit": runtime_corrective_query_limit,
        "runtime_public_expansion_on_watch": runtime_public_expansion_on_watch,
        "runtime_reranker_adapter": runtime_reranker_adapter,
        "runtime_reranker_backend": runtime_reranker_backend,
        "runtime_reranker_top_k": runtime_reranker_top_k,
        "runtime_reranker_fallback_adapter": runtime_reranker_fallback_adapter,
        "runtime_official_source_bias": runtime_official_source_bias,
        "enable_cross_encoder_rerank": enable_cross_encoder_rerank,
        "cross_encoder_rerank": cross_encoder_rerank,
    }
