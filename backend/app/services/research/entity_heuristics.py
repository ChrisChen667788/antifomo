from __future__ import annotations

from collections import Counter
from collections.abc import Iterable
import re

from app.schemas.research import (
    ResearchEntityEvidenceOut,
    ResearchEntityGraphOut,
    ResearchNormalizedEntityOut,
    ResearchRankedEntityOut,
    ResearchScoreFactorOut,
)
from app.services.content_extractor import extract_domain, normalize_text
from app.services.research.source_documents import SourceDocument, source_document_text


KNOWN_COMPANIES = (
    "爱奇艺",
    "腾讯动漫",
    "快看漫画",
    "哔哩哔哩",
    "百联集团",
    "格科半导体",
    "超硅半导体",
    "Microsoft",
    "OpenAI",
)
ALIAS_TO_CANONICAL = {
    "百联": "百联集团",
    "Open AI": "OpenAI",
    "open ai": "OpenAI",
    "openai": "OpenAI",
    "微软": "Microsoft",
    "microsoft": "Microsoft",
}
AI_COMIC_COMPANY_TOKENS = ("爱奇艺", "腾讯动漫", "快看漫画", "哔哩哔哩", "动漫", "漫画", "IP", "AIGC", "短剧")
COMPANY_SUFFIX_TOKENS = ("集团", "公司", "有限公司", "股份", "科技", "信息", "软件", "智能", "动漫", "漫画", "半导体")
INSTITUTION_TOKENS = ("大学", "学院", "学校", "医院", "政府", "局", "委", "办", "中心", "银行")
FRAGMENT_TOKENS = (
    "新协议",
    "两家公司",
    "任何云服务",
    "现在可以",
    "不用再",
    "内容及服务",
    "围绕预算",
    "进入路径",
    "行业趋势",
    "课程建设",
)
ENTITY_PATTERN = re.compile(
    r"([A-Za-z0-9\u4e00-\u9fa5·（）()]{2,42}"
    r"(?:集团|有限公司|股份有限公司|公司|科技|信息|软件|智能|动漫|漫画|半导体|大学|学院|医院|中心|数据局))"
)
ENGLISH_ORG_PATTERN = re.compile(r"\b(Microsoft|Open\s*AI|OpenAI)\b", re.IGNORECASE)


def dedupe_strings(values: Iterable[object], limit: int) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(str(value or ""))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        rows.append(normalized)
        if len(rows) >= limit:
            break
    return rows


def resolve_known_org_name(value: str, *, scope_hints: dict[str, object] | None = None, source: SourceDocument | None = None) -> str:
    normalized = normalize_text(value)
    if not normalized:
        return ""
    for seed in scope_org_names(scope_hints):
        if normalized == seed or normalized in org_surface_variants(seed):
            return seed
    return ALIAS_TO_CANONICAL.get(normalized, ALIAS_TO_CANONICAL.get(normalized.lower(), normalized))


def scope_org_names(scope_hints: dict[str, object] | None) -> list[str]:
    scope = scope_hints or {}
    return dedupe_strings(
        [
            *(scope.get("seed_companies", []) or []),
            *(scope.get("clients", []) or []),
            *(scope.get("company_anchors", []) or []),
        ],
        12,
    )


def org_surface_variants(value: str) -> tuple[str, ...]:
    canonical = normalize_text(value)
    if canonical == "百联集团":
        return ("百联集团", "百联")
    if canonical == "OpenAI":
        return ("OpenAI", "Open AI")
    if canonical == "Microsoft":
        return ("Microsoft", "微软")
    return (canonical,)


def org_entity_variants(value: str, *, scope_hints: dict[str, object] | None = None) -> list[str]:
    canonical = resolve_known_org_name(value, scope_hints=scope_hints)
    variants = list(org_surface_variants(canonical))
    for seed in scope_org_names(scope_hints):
        if resolve_known_org_name(seed, scope_hints=scope_hints) == canonical:
            variants.extend(org_surface_variants(seed))
    return dedupe_strings(variants, 8)


def entity_canonical_key(value: str) -> str:
    return normalize_text(resolve_known_org_name(value)).lower().replace(" ", "")


def trim_product_spec_from_entity_name(value: str) -> str:
    normalized = normalize_text(value)
    semiconductor_match = re.search(r"([\u4e00-\u9fa5A-Za-z0-9]+半导体)", normalized)
    if semiconductor_match:
        return semiconductor_match.group(1)
    for marker in ("12英寸", "300毫米", "先进逻辑", "全自动", "项目", "产线", "平台", "方案"):
        if marker in normalized:
            return normalize_text(normalized.split(marker, 1)[0])
    return normalized


def looks_like_fragment_entity_name(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return True
    if any(token in normalized for token in FRAGMENT_TOKENS):
        return True
    if normalized.endswith(("路径", "节奏", "策略", "打法", "能力", "场景", "机会", "商机", "窗口", "趋势", "布局", "运营", "建设", "规划", "升级", "协同", "统筹")):
        return True
    return False


def is_lightweight_entity_name(value: str) -> bool:
    normalized = normalize_text(value)
    return normalized in KNOWN_COMPANIES or normalized in ALIAS_TO_CANONICAL


def is_plausible_entity_name(value: str) -> bool:
    normalized = trim_product_spec_from_entity_name(value)
    if not normalized or len(normalized) < 2 or any(char in normalized for char in "，,。；;：:"):
        return False
    if looks_like_fragment_entity_name(normalized):
        return False
    if is_lightweight_entity_name(normalized):
        return True
    if any(token in normalized for token in COMPANY_SUFFIX_TOKENS + INSTITUTION_TOKENS):
        return True
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9 .-]{2,30}", normalized):
        return True
    return False


def extract_rank_entity_candidates(value: str, *, scope_hints: dict[str, object] | None = None) -> list[str]:
    text = normalize_text(value)
    if not text:
        return []
    candidates: list[str] = []
    for seed in scope_org_names(scope_hints):
        if any(variant and variant in text for variant in org_surface_variants(seed)):
            candidates.append(seed)
    for company in KNOWN_COMPANIES:
        if any(variant and variant in text for variant in org_surface_variants(company)):
            candidates.append(company)
    for match in ENGLISH_ORG_PATTERN.findall(text):
        candidates.append(resolve_known_org_name(match))
    for match in re.findall(r"([\u4e00-\u9fa5A-Za-z0-9]+半导体)", text):
        candidates.append(match)
    for match in ENTITY_PATTERN.findall(text):
        candidates.append(match)

    filtered: list[str] = []
    for candidate in candidates:
        normalized = trim_product_spec_from_entity_name(resolve_known_org_name(candidate, scope_hints=scope_hints))
        if not (is_plausible_entity_name(normalized) or is_lightweight_entity_name(normalized)):
            continue
        if looks_like_fragment_entity_name(normalized):
            continue
        filtered.append(normalized)
    return dedupe_strings(filtered, 5)


def extract_rank_entity_name(value: str) -> str:
    candidates = extract_rank_entity_candidates(value)
    return candidates[0] if candidates else ""


def source_text(source: SourceDocument) -> str:
    return source_document_text(source)


def build_entity_evidence(source: SourceDocument) -> ResearchEntityEvidenceOut:
    return ResearchEntityEvidenceOut(
        title=source.title,
        url=source.url,
        source_label=source.source_label,
        source_tier=source.source_tier if source.source_tier in {"official", "media", "aggregate"} else "media",
        excerpt=normalize_text(source.excerpt or source.snippet),
    )


def canonical_org_name_from_domain(domain: str | None) -> str:
    normalized = normalize_text(domain or "").lower().removeprefix("www.")
    if normalized.endswith("bailian.com"):
        return "百联集团"
    if normalized.endswith("iqiyi.com"):
        return "爱奇艺"
    if normalized.endswith("kuaikanmanhua.com"):
        return "快看漫画"
    if normalized.endswith("qq.com") or normalized.endswith("ac.qq.com"):
        return "腾讯动漫"
    return ""


def entity_graph_lookup(graph: ResearchEntityGraphOut) -> dict[str, ResearchNormalizedEntityOut]:
    lookup: dict[str, ResearchNormalizedEntityOut] = {}
    for entity in graph.entities:
        for name in [entity.canonical_name, *entity.aliases]:
            key = entity_canonical_key(name)
            if key:
                lookup.setdefault(key, entity)
    return lookup


def build_entity_graph(sources: list[SourceDocument], *, scope_hints: dict[str, object]) -> ResearchEntityGraphOut:
    states: dict[str, dict[str, object]] = {}
    for source in sources:
        candidates = extract_rank_entity_candidates(source_text(source), scope_hints=scope_hints)
        domain_name = canonical_org_name_from_domain(source.domain or extract_domain(source.url))
        if domain_name:
            candidates.append(domain_name)
        for candidate in dedupe_strings(candidates, 8):
            canonical = resolve_known_org_name(candidate, scope_hints=scope_hints, source=source)
            if not canonical:
                continue
            key = entity_canonical_key(canonical)
            state = states.setdefault(
                key,
                {
                    "canonical_name": canonical,
                    "aliases": set(),
                    "urls": set(),
                    "tier_counts": Counter(),
                    "evidence": [],
                },
            )
            aliases = state["aliases"]
            if isinstance(aliases, set):
                aliases.update(org_entity_variants(canonical, scope_hints=scope_hints))
                aliases.update(org_surface_variants(candidate))
            urls = state["urls"]
            if isinstance(urls, set):
                urls.add(source.url)
            tier_counts = state["tier_counts"]
            if isinstance(tier_counts, Counter):
                tier_counts[source.source_tier or "media"] += 1
            evidence = state["evidence"]
            if isinstance(evidence, list) and not any(item.url == source.url for item in evidence):
                evidence.append(build_entity_evidence(source))

    entities: list[ResearchNormalizedEntityOut] = []
    for state in states.values():
        aliases = sorted([item for item in state["aliases"] if item], key=len, reverse=True)
        tier_counts = state["tier_counts"]
        urls = state["urls"]
        evidence = state["evidence"]
        canonical = normalize_text(str(state["canonical_name"]))
        role = "target" if any(token in canonical for token in INSTITUTION_TOKENS) else "competitor"
        entities.append(
            ResearchNormalizedEntityOut(
                canonical_name=canonical,
                entity_type=role,
                aliases=aliases[:6],
                source_count=len(urls) if isinstance(urls, set) else 0,
                source_tier_counts=dict(tier_counts) if isinstance(tier_counts, Counter) else {},
                evidence_links=list(evidence)[:3] if isinstance(evidence, list) else [],
            )
        )
    entities.sort(key=lambda item: (-item.source_count, -item.source_tier_counts.get("official", 0), item.canonical_name))
    return ResearchEntityGraphOut(
        entities=entities[:24],
        target_entities=[item for item in entities if item.entity_type == "target"][:12],
        competitor_entities=[item for item in entities if item.entity_type == "competitor"][:12],
        partner_entities=[],
    )


def is_theme_aligned_entity_name(value: str, *, role: str, theme_labels: list[str]) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    if not theme_labels:
        return True
    if "AI漫剧" in theme_labels:
        if any(token in normalized for token in ("大学", "学院", "学校", "课程", "内容及服务")):
            return False
        return normalized in KNOWN_COMPANIES or any(token in normalized for token in AI_COMIC_COMPANY_TOKENS)
    return True


def is_company_like_entity_name(value: str, *, role: str, theme_labels: list[str], seed_companies: list[str]) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    if normalized in seed_companies or normalized in KNOWN_COMPANIES:
        return True
    if any(token in normalized for token in INSTITUTION_TOKENS):
        return False
    if any(token in normalized for token in COMPANY_SUFFIX_TOKENS):
        return True
    if "AI漫剧" in theme_labels and any(token in normalized for token in AI_COMIC_COMPANY_TOKENS):
        return True
    return False


def filter_theme_aligned_rows(
    values: Iterable[str],
    *,
    role: str,
    theme_labels: list[str],
    scope_hints: dict[str, object],
) -> list[str]:
    seed_companies = [normalize_text(str(item)) for item in scope_hints.get("seed_companies", []) or [] if normalize_text(str(item))]
    prefer_company_entities = bool(scope_hints.get("prefer_company_entities"))
    filtered: list[str] = []
    for value in values:
        normalized = normalize_text(value)
        if not normalized:
            continue
        entity_name = extract_rank_entity_name(normalized) or normalized.split("：", 1)[0].split(":", 1)[0]
        if not is_theme_aligned_entity_name(entity_name, role=role, theme_labels=theme_labels):
            continue
        if prefer_company_entities and role in {"target", "competitor"} and not is_company_like_entity_name(
            entity_name,
            role=role,
            theme_labels=theme_labels,
            seed_companies=seed_companies,
        ):
            continue
        filtered.append(normalized)
    return dedupe_strings(filtered, 6)


def company_convergence_is_weak(*, scope_hints: dict[str, object], target_rows: list[str], competitor_rows: list[str]) -> bool:
    if not bool(scope_hints.get("prefer_company_entities")):
        return False
    theme_labels = [normalize_text(str(item)) for item in scope_hints.get("industries", []) or [] if normalize_text(str(item))]
    seed_companies = [normalize_text(str(item)) for item in scope_hints.get("seed_companies", []) or [] if normalize_text(str(item))]
    candidates = dedupe_strings([*target_rows, *competitor_rows], 4)
    concrete = [
        item
        for item in candidates
        if is_company_like_entity_name(item, role="target", theme_labels=theme_labels, seed_companies=seed_companies)
    ]
    minimum = 2 if bool(scope_hints.get("prefer_head_companies")) else 1
    return len(concrete) < minimum


def company_intent_summary_needs_override(
    *,
    scope_hints: dict[str, object],
    summary: str,
    accounts: list[str],
    competitors: list[str],
) -> bool:
    if not bool(scope_hints.get("prefer_company_entities")):
        return False
    normalized_summary = normalize_text(summary)
    anchors = dedupe_strings([*accounts, *competitors, *(scope_hints.get("seed_companies", []) or [])], 4)
    if company_convergence_is_weak(scope_hints=scope_hints, target_rows=accounts, competitor_rows=competitors):
        return True
    if not normalized_summary:
        return True
    if anchors and not any(anchor in normalized_summary for anchor in anchors):
        return True
    return any(token in normalized_summary for token in ("课程", "行业趋势", "内容服务", "泛化"))


def source_supports_company_intent(source: SourceDocument, *, theme_labels: list[str], seed_companies: list[str]) -> bool:
    text = source_text(source)
    if any(seed and seed in text for seed in seed_companies):
        return True
    candidates = extract_rank_entity_candidates(text, scope_hints={"seed_companies": seed_companies})
    return any(
        is_theme_aligned_entity_name(candidate, role="target", theme_labels=theme_labels)
        and is_company_like_entity_name(candidate, role="target", theme_labels=theme_labels, seed_companies=seed_companies)
        for candidate in candidates
    )


def filter_sources_by_theme_relevance(
    sources: list[SourceDocument],
    *,
    theme_terms: list[str],
    scope_hints: dict[str, object],
    company_anchor_terms: list[str] | None = None,
) -> list[SourceDocument]:
    if not sources or not theme_terms:
        return sources
    theme_labels = [normalize_text(str(item)) for item in scope_hints.get("industries", []) or [] if normalize_text(str(item))]
    seed_companies = [normalize_text(str(item)) for item in scope_hints.get("seed_companies", []) or [] if normalize_text(str(item))]
    candidate_sources = list(sources)
    if bool(scope_hints.get("prefer_company_entities")):
        company_sources = [
            source
            for source in candidate_sources
            if source_supports_company_intent(source, theme_labels=theme_labels, seed_companies=seed_companies)
        ]
        if company_sources:
            candidate_sources = company_sources
    company_terms = [normalize_text(item).lower() for item in company_anchor_terms or [] if normalize_text(item)]
    matched: list[SourceDocument] = []
    for source in candidate_sources:
        text = source_text(source).lower()
        if company_terms and not any(term in text for term in company_terms):
            continue
        score = sum(4 for term in theme_terms if normalize_text(term).lower() in text)
        if source.source_tier == "official":
            score += 4
        if score >= 4:
            matched.append(source)
    return matched


def source_type_weight(source: SourceDocument) -> int:
    if source.source_tier == "official":
        return 18
    if source.source_tier == "aggregate":
        return 12
    return 8


def rank_top_entities(
    sources: list[SourceDocument],
    *,
    role: str,
    output_language: str,
    scope_hints: dict[str, object],
    theme_terms: list[str],
    entity_graph: ResearchEntityGraphOut | None = None,
    fallback_values: Iterable[str] | None = None,
    limit: int = 3,
) -> tuple[list[ResearchRankedEntityOut], list[ResearchRankedEntityOut]]:
    theme_labels = [normalize_text(str(item)) for item in scope_hints.get("industries", []) or [] if normalize_text(str(item))]
    seed_companies = [normalize_text(str(item)) for item in scope_hints.get("seed_companies", []) or [] if normalize_text(str(item))]
    prefer_company_entities = bool(scope_hints.get("prefer_company_entities"))
    graph_lookup = entity_graph_lookup(entity_graph) if entity_graph else {}
    scored: dict[str, dict[str, object]] = {}

    def add_candidate(name: str, source: SourceDocument | None, base_score: int) -> None:
        canonical = resolve_known_org_name(name, scope_hints=scope_hints, source=source)
        if not canonical or looks_like_fragment_entity_name(canonical):
            return
        if prefer_company_entities and role in {"target", "competitor"} and not is_company_like_entity_name(
            canonical,
            role=role,
            theme_labels=theme_labels,
            seed_companies=seed_companies,
        ):
            return
        if not is_theme_aligned_entity_name(canonical, role=role, theme_labels=theme_labels):
            return
        key = entity_canonical_key(canonical)
        state = scored.setdefault(key, {"name": canonical, "score": 0, "sources": []})
        state["name"] = canonical
        state["score"] = int(state["score"]) + base_score
        if source is not None:
            sources_list = state["sources"]
            if isinstance(sources_list, list) and not any(item.url == source.url for item in sources_list):
                sources_list.append(source)

    for source in sources:
        text = source_text(source)
        source_score = source_type_weight(source)
        if any(normalize_text(term).lower() in text.lower() for term in theme_terms):
            source_score += 12
        for candidate in extract_rank_entity_candidates(text, scope_hints=scope_hints):
            add_candidate(candidate, source, source_score)
        domain_name = canonical_org_name_from_domain(source.domain or extract_domain(source.url))
        if domain_name:
            add_candidate(domain_name, source, source_score + 4)
    for fallback in fallback_values or []:
        candidate = extract_rank_entity_name(fallback) or normalize_text(str(fallback))
        if candidate:
            add_candidate(candidate, None, 8)
    for entity_key, graph_entity in graph_lookup.items():
        if graph_entity.canonical_name:
            add_candidate(graph_entity.canonical_name, None, 6)

    results: list[ResearchRankedEntityOut] = []
    for state in scored.values():
        source_rows = list(state.get("sources", []))
        evidence_links = [build_entity_evidence(source) for source in source_rows[:2]]
        score = min(100, int(state["score"]))
        results.append(
            ResearchRankedEntityOut(
                name=str(state["name"]),
                score=score,
                reasoning=f"基于 {len(source_rows)} 条公开线索和主题匹配得分排序。",
                score_breakdown=[ResearchScoreFactorOut(label="公开线索", score=score, note="测试级实体启发式 owner")],
                evidence_links=evidence_links,
                entity_mode="instance" if source_rows else "pending",
            )
        )
    results.sort(key=lambda item: (-item.score, item.name))
    return results[:limit], results[limit : limit * 2]


def infer_scope_hints(keyword: str, research_focus: str | None, sources: list[SourceDocument]) -> dict[str, object]:
    seed_text = normalize_text(" ".join([keyword, research_focus or "", *[f"{source.title} {source.snippet}" for source in sources[:10]]]))
    industries: list[str] = []
    if any(token.lower() in seed_text.lower() for token in ("ai漫剧", "漫剧", "ai短剧", "aigc动画")):
        industries.append("AI漫剧")
    if any(token.lower() in seed_text.lower() for token in ("大模型", "openai", "人工智能", "ai")):
        industries.append("大模型")
    if any(token in seed_text for token in ("医药", "医疗", "医院")):
        industries.append("医疗")
    regions = [region for region in ("长三角", "上海", "江苏", "南京") if region in seed_text]
    clients = [
        candidate
        for candidate in extract_rank_entity_candidates(seed_text)
        if not looks_like_fragment_entity_name(candidate)
    ]
    prefer_company_entities = any(token in seed_text for token in ("头部公司", "公司", "有价值实体", "高价值实体"))
    seed_companies: list[str] = []
    if "AI漫剧" in industries:
        seed_companies.extend(["爱奇艺", "腾讯动漫", "快看漫画", "哔哩哔哩"])
    return {
        "regions": dedupe_strings(regions, 3),
        "industries": dedupe_strings(industries, 3),
        "clients": dedupe_strings(clients, 3),
        "company_anchors": dedupe_strings(clients, 4),
        "prefer_company_entities": prefer_company_entities,
        "prefer_head_companies": prefer_company_entities and "头部" in seed_text,
        "seed_companies": dedupe_strings(seed_companies, 6) if seed_companies else [],
        "strategy_must_include_terms": [],
        "strategy_exclusion_terms": [],
        "strategy_query_expansions": [],
        "strategy_scope_summary": "",
        "anchor_text": normalize_text(" / ".join(dedupe_strings([*regions, *industries, *clients], 6))),
    }
