from __future__ import annotations

from collections.abc import Iterable
import re

from app.schemas.research import (
    ResearchEntityEvidenceOut,
    ResearchEntityGraphOut,
    ResearchNormalizedEntityOut,
    ResearchRankedEntityOut,
)
from app.services.content_extractor import extract_domain, normalize_text
from app.services.language import localized_text
from app.services.research.entity_graph_builder import (
    EntityGraphBuilderDependencies,
    build_entity_graph,
    entity_graph_lookup,
)
from app.services.research.entity_heuristics import source_type_weight
from app.services.research.entity_policy import (
    CONTACT_PAGE_TOKENS,
    EMAIL_PATTERN,
    GENERIC_CONTENT_DOMAINS,
    PARTNER_CONNECTOR_ALIASES,
    PHONE_PATTERN,
    SPECIAL_ENTITY_ALIASES,
    THEME_ENTITY_ALLOW_TOKENS,
    contains_low_value_entity_token,
    extract_rank_entity_name,
    fallback_entity_name_from_row,
    is_lightweight_entity_name,
    is_plausible_entity_name,
    is_theme_aligned_entity_name,
    looks_like_fragment_entity_name,
    looks_like_placeholder_entity_name,
    strip_entity_leading_noise,
)
from app.services.research.entity_ranking import EntityRankingHeuristicDependencies, rank_top_entities
from app.services.research.organization_identity import (
    KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS,
    canonical_org_name_from_domain,
    entity_canonical_key,
    extract_rank_entity_candidates,
    org_entity_variants,
    org_surface_variants,
    resolve_known_org_name,
    source_mentions_entity,
)
from app.services.research.report_common import dedupe_strings
from app.services.research.report_field_sanitization import is_useful_public_contact_row
from app.services.research.report_row_quality import FIELD_ROW_NOISE_TOKENS, looks_like_insufficient
from app.services.research.scope_entity_runtime_dependencies import (
    report_field_sanitization_dependencies,
    scope_term_dependencies,
)
from app.services.research.scope_hints import (
    REGION_SCOPE_ALIASES,
    clean_scope_entity_names,
    expand_region_scope_terms,
    extract_org_candidates,
    source_theme_match_score,
)
from app.services.research.scope_terms import looks_like_scope_prompt_noise
from app.services.research.source_documents import (
    SourceDocument,
    clean_source_text_for_analysis,
    looks_like_source_artifact_text,
    source_document_text,
)


THEME_ROLE_ARCHETYPES: dict[str, dict[str, tuple[str, ...]]] = {
    "AI漫剧": {
        "target": (
            "短剧内容平台运营方（待验证）",
            "动漫 IP 版权运营机构（待验证）",
            "文旅/教育数字内容运营主体（待验证）",
        ),
        "competitor": (
            "AIGC 短剧生成平台服务商（待验证）",
            "动漫内容工业化制作团队（待验证）",
            "AI 视频分镜与角色生成厂商（待验证）",
        ),
        "partner": (
            "动漫 IP 咨询与发行伙伴（待验证）",
            "区域内容集成与渠道分发伙伴（待验证）",
            "文旅/教育场景牵线伙伴（待验证）",
        ),
    },
    "政务云": {
        "target": (
            "省级数据局/政务服务管理局（待验证）",
            "地市级大数据中心或信息中心（待验证）",
            "政务云运营平台公司或城投平台（待验证）",
        ),
        "competitor": (
            "政务云总集厂商（待验证）",
            "政务一体化平台交付厂商（待验证）",
            "本地云资源与集成服务商（待验证）",
        ),
        "partner": (
            "区域总包与咨询伙伴（待验证）",
            "本地政务集成与运维伙伴（待验证）",
            "有政府关系的生态牵线方（待验证）",
        ),
    },
}
GENERIC_COMPANY_NAME_TOKENS = (
    "集团", "公司", "有限公司", "股份有限公司", "科技", "智能", "信息", "传媒", "影业", "视频",
    "动漫", "漫画", "平台", "工作室", "网络", "数据", "云", "软件", "娱乐", "文化",
)
COMPANY_PROFILE_PAGE_TOKENS = (
    *CONTACT_PAGE_TOKENS,
    "官网", "官方", "公开入口", "关于我们", "公司简介", "企业简介", "品牌介绍", "aboutus", "about-us",
    "official", "profile", "company", "business", "solution", "brand", "investor relations",
)
PROCUREMENT_DOMAINS = {
    "ccgp.gov.cn", "www.ccgp.gov.cn", "ggzy.gov.cn", "www.ggzy.gov.cn", "chinabidding.com", "www.chinabidding.com",
}
POLICY_DOMAINS = {"gov.cn", "www.gov.cn"}
EXCHANGE_DOMAINS = {
    "cninfo.com.cn", "www.cninfo.com.cn", "hkexnews.hk", "www.hkexnews.hk", "sec.gov", "www.sec.gov",
}


def truncate_text(value: str, limit: int) -> str:
    text = normalize_text(value)
    if len(text) <= limit:
        return text
    cut = text[: limit - 1].rstrip(" ，,：:；;")
    return f"{cut}…"


def looks_like_scope_prompt_noise_bound(value: str) -> bool:
    return looks_like_scope_prompt_noise(value, deps=scope_term_dependencies())


def is_useful_public_contact_row_bound(value: str) -> bool:
    return is_useful_public_contact_row(value, deps=report_field_sanitization_dependencies())


def is_company_like_entity_name(
    value: str,
    *,
    role: str,
    theme_labels: list[str],
    seed_companies: list[str],
) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    if normalized in seed_companies or is_lightweight_entity_name(normalized) or normalized in SPECIAL_ENTITY_ALIASES:
        return True
    if any(
        token in normalized
        for token in ("政府", "市委", "市政府", "局", "委", "办", "中心", "大学", "学院", "学校", "医院", "银行", "证券")
    ):
        return False
    theme_company_tokens = [
        token
        for label in theme_labels
        for token in THEME_ENTITY_ALLOW_TOKENS.get(label, {}).get(role, ())
        if normalize_text(token) and token not in {"内容", "运营", "服务"}
    ]
    return any(token in normalized for token in [*GENERIC_COMPANY_NAME_TOKENS, *theme_company_tokens])


def text_has_region_conflict(text: str, *, scope_hints: dict[str, object]) -> bool:
    scope_regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    if not scope_regions:
        return False
    allowed_regions = [item.lower() for item in expand_region_scope_terms(scope_regions)]
    normalized_text = normalize_text(text).lower()
    if not normalized_text:
        return False
    from app.services.research.entity_policy import REGION_TOKENS

    explicit_region_hits = [region for region in REGION_TOKENS if region.lower() in normalized_text]
    explicit_region_hits.extend(label for label in REGION_SCOPE_ALIASES if label.lower() in normalized_text)
    explicit_region_hits = list(dict.fromkeys(explicit_region_hits))
    if not explicit_region_hits:
        return False
    if any(hit.lower() in allowed_regions for hit in explicit_region_hits):
        return False
    return not any(term in normalized_text for term in allowed_regions)


def source_negates_entity(source: SourceDocument, entity_name: str) -> bool:
    normalized_name = normalize_text(entity_name)
    if not normalized_name:
        return False
    negative_tokens = ("未提及", "未出现", "未涉及", "未覆盖", "没有提及", "并未提及", "并未出现", "不涉及", "未见")
    for sentence in re.split(r"[。！？!?；;\n]", source_document_text(source)):
        normalized_sentence = normalize_text(sentence)
        if normalized_name in normalized_sentence and any(token in normalized_sentence for token in negative_tokens):
            return True
    return False


def build_entity_evidence(source: SourceDocument) -> ResearchEntityEvidenceOut:
    return ResearchEntityEvidenceOut(
        title=source.title,
        url=source.url,
        source_label=source.source_label,
        source_tier=source.source_tier if source.source_tier in {"official", "media", "aggregate"} else "media",
        excerpt=clean_source_text_for_analysis(source.excerpt or source.snippet),
    )


def entity_graph_builder_dependencies() -> EntityGraphBuilderDependencies:
    return EntityGraphBuilderDependencies(
        source_text=source_document_text,
        extract_rank_entity_candidates=extract_rank_entity_candidates,
        canonical_org_name_from_domain=canonical_org_name_from_domain,
        extract_domain=extract_domain,
        resolve_known_org_name=resolve_known_org_name,
        is_plausible_entity_name=is_plausible_entity_name,
        entity_canonical_key=entity_canonical_key,
        org_entity_variants=org_entity_variants,
        org_surface_variants=org_surface_variants,
        build_entity_evidence=build_entity_evidence,
    )


def build_runtime_entity_graph(
    sources: list[SourceDocument],
    *,
    scope_hints: dict[str, object],
) -> ResearchEntityGraphOut:
    return build_entity_graph(sources, scope_hints=scope_hints, deps=entity_graph_builder_dependencies())


def runtime_entity_graph_lookup(graph: ResearchEntityGraphOut) -> dict[str, ResearchNormalizedEntityOut]:
    return entity_graph_lookup(graph, entity_canonical_key=entity_canonical_key)


def entity_ranking_dependencies() -> EntityRankingHeuristicDependencies:
    return EntityRankingHeuristicDependencies(
        clean_scope_entity_names=clean_scope_entity_names,
        entity_graph_lookup=runtime_entity_graph_lookup,
        is_theme_aligned_entity_name=is_theme_aligned_entity_name,
        is_company_like_entity_name=is_company_like_entity_name,
        source_text=source_document_text,
        extract_rank_entity_candidates=extract_rank_entity_candidates,
        canonical_org_name_from_domain=canonical_org_name_from_domain,
        dedupe_strings=dedupe_strings,
        resolve_known_org_name=resolve_known_org_name,
        source_type_weight=source_type_weight,
        build_entity_evidence=build_entity_evidence,
        entity_canonical_key=entity_canonical_key,
        extract_rank_entity_name=extract_rank_entity_name,
        extract_org_candidates=extract_org_candidates,
        is_plausible_entity_name=is_plausible_entity_name,
        is_lightweight_entity_name=is_lightweight_entity_name,
        org_entity_variants=org_entity_variants,
        source_mentions_entity=source_mentions_entity,
        source_negates_entity=source_negates_entity,
        known_company_public_source_seeds=KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS,
        company_profile_page_tokens=COMPANY_PROFILE_PAGE_TOKENS,
        theme_entity_allow_tokens=THEME_ENTITY_ALLOW_TOKENS,
        generic_company_name_tokens=GENERIC_COMPANY_NAME_TOKENS,
        theme_role_archetypes=THEME_ROLE_ARCHETYPES,
        partner_connector_aliases=PARTNER_CONNECTOR_ALIASES,
    )


def rank_runtime_top_entities(
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
    return rank_top_entities(
        sources,
        role=role,
        output_language=output_language,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        entity_graph=entity_graph,
        fallback_values=fallback_values,
        limit=limit,
        deps=entity_ranking_dependencies(),
    )


def stored_source_is_low_signal(
    source: SourceDocument,
    *,
    theme_terms: list[str],
    scope_hints: dict[str, object],
) -> bool:
    text = source_document_text(source)
    if not text:
        return True
    lowered = text.lower()
    domain = normalize_text(source.domain or "").lower()
    title_lower = normalize_text(source.title).lower()
    client_terms = [normalize_text(str(item)).lower() for item in scope_hints.get("clients", []) or [] if normalize_text(str(item))]
    if any(token in text for token in FIELD_ROW_NOISE_TOKENS):
        return True
    if any(token in lowered for token in ("header_", "[source", "javascript:", "返回顶部", "跳转到主要内容区域")):
        return True
    if looks_like_insufficient(text):
        return True
    theme_score = source_theme_match_score(source, theme_terms=theme_terms, scope_hints=scope_hints)
    procurement_aggregate_like = any(token in domain for token in ("cecbid", "cebpubservice", "chinabidding", "china-cpp", "jianyu"))
    tech_media_like = source.source_type == "tech_media_feed" or "yuntoutiao" in domain
    client_hit = any(term in lowered or term in title_lower for term in client_terms)
    if procurement_aggregate_like and not client_hit and theme_score < 14:
        return True
    if tech_media_like and not client_hit and theme_score < 16:
        return True
    if theme_terms and theme_score < 6 and source.source_tier != "official":
        return True
    return source.source_tier == "aggregate" and source.content_status == "snippet_only" and theme_score < 8


def source_supports_target_account(
    source: SourceDocument,
    entity_name: str,
    *,
    theme_terms: list[str],
    scope_hints: dict[str, object],
) -> bool:
    return (
        source_mentions_entity(source, entity_name)
        and not source_negates_entity(source, entity_name)
        and not stored_source_is_low_signal(source, theme_terms=theme_terms, scope_hints=scope_hints)
    )

def filtered_rank_fallback_values(
    values: Iterable[str],
    *,
    role: str,
    scope_hints: dict[str, object],
) -> list[str]:
    theme_labels = [
        normalize_text(str(item))
        for item in scope_hints.get("industries", []) or []
        if normalize_text(str(item))
    ]
    seed_companies = [
        normalize_text(str(item))
        for item in scope_hints.get("seed_companies", []) or []
        if normalize_text(str(item))
    ]
    prefer_company_entities = bool(scope_hints.get("prefer_company_entities"))
    candidates: list[str] = []
    for value in values:
        normalized = normalize_text(str(value))
        if (
            not normalized
            or looks_like_insufficient(normalized)
            or looks_like_source_artifact_text(normalized)
            or looks_like_scope_prompt_noise_bound(normalized)
        ):
            continue
        extracted = extract_rank_entity_candidates(normalized, scope_hints=scope_hints)
        fallback = fallback_entity_name_from_row(normalized)
        for candidate in [*extracted, *([fallback] if fallback else [])]:
            compact = resolve_known_org_name(candidate, scope_hints=scope_hints)
            compact = strip_entity_leading_noise(compact)
            if (
                not compact
                or looks_like_fragment_entity_name(compact)
                or contains_low_value_entity_token(compact)
                or looks_like_placeholder_entity_name(compact)
                or looks_like_scope_prompt_noise_bound(compact)
            ):
                continue
            if theme_labels and not is_theme_aligned_entity_name(compact, role=role, theme_labels=theme_labels):
                continue
            if prefer_company_entities and role in {"target", "competitor"} and not is_company_like_entity_name(
                compact,
                role=role,
                theme_labels=theme_labels,
                seed_companies=seed_companies,
            ):
                continue
            candidates.append(compact)
    return dedupe_strings(candidates, 12)

def build_entity_specific_contact_rows(
    sources: list[SourceDocument],
    *,
    entity_names: list[str],
    output_language: str,
    limit: int,
) -> list[str]:
    if not entity_names:
        return []

    normalized_entities = [
        normalize_text(name)
        for name in entity_names
        if normalize_text(name) and "待验证" not in normalize_text(name) and "待驗證" not in normalize_text(name)
        and (is_plausible_entity_name(normalize_text(name)) or is_lightweight_entity_name(normalize_text(name)))
    ]
    if not normalized_entities:
        return []

    contact_person_pattern = re.compile(
        r"(联系人|联络人|联系人姓名|项目联系人|采购人联系人|代理机构联系人)[:：]?\s*([A-Za-z\u4e00-\u9fa5]{2,24})"
    )
    line_contact_pattern = re.compile(
        r"([A-Za-z0-9\u4e00-\u9fa5·（）()]{2,36})(联系人|联系电话|联系邮箱|服务热线|咨询电话)[:：]?\s*([A-Za-z0-9@\-.+\u4e00-\u9fa5]{2,48})"
    )
    procurement_like_source_types = {
        "procurement",
        "official_tender_feed",
        "compliant_procurement_aggregate",
        "tender_feed",
    }
    official_contact_source_types = {
        "policy",
        "filing",
        "official_policy_speech",
    }

    def is_valid_contact_value(value: str) -> bool:
        normalized = normalize_text(value)
        lowered = normalized.lower()
        if not normalized:
            return False
        if any(lowered.endswith(ext) for ext in (".webp", ".jpg", ".jpeg", ".png", ".gif", ".svg", ".bmp")):
            return False
        if lowered.startswith("http") and any(domain in lowered for domain in GENERIC_CONTENT_DOMAINS):
            return False
        return True

    def looks_like_company_domain(domain: str) -> bool:
        lowered = normalize_text(domain).lower()
        if not lowered:
            return False
        if lowered in GENERIC_CONTENT_DOMAINS or lowered in PROCUREMENT_DOMAINS or lowered in POLICY_DOMAINS or lowered in EXCHANGE_DOMAINS:
            return False
        if lowered.endswith(".gov.cn") or lowered.endswith(".edu.cn"):
            return False
        return "." in lowered

    scored_rows: dict[str, int] = {}

    def add_row(row: str, score: int) -> None:
        normalized = normalize_text(row)
        if not normalized or not is_useful_public_contact_row_bound(normalized):
            return
        current = scored_rows.get(normalized)
        if current is None or score > current:
            scored_rows[normalized] = score

    for entity in dedupe_strings(normalized_entities, 6):
        for source in sources:
            if not source_mentions_entity(source, entity):
                continue
            text = source_document_text(source)
            domain = normalize_text(source.domain or "")
            title_or_url = f"{source.title or ''} {source.url or ''}".lower()
            label = normalize_text(source.source_label or source.title or domain or entity)
            contact_page = any(token in title_or_url for token in CONTACT_PAGE_TOKENS)
            official_like = source.source_tier == "official" or source.source_type in official_contact_source_types
            procurement_like = source.source_type in procurement_like_source_types

            if looks_like_company_domain(domain) and official_like:
                add_row(f"{entity}：官方公开入口 https://{domain}", 92)

            if contact_page and source.url and is_valid_contact_value(source.url):
                add_row(f"{entity}：高概率公开联系页 {source.url}", 96 if official_like else 82)

            for _, person in contact_person_pattern.findall(text)[:2]:
                normalized_person = normalize_text(person)
                if not normalized_person:
                    continue
                prefix = "采购/项目联系人" if procurement_like else "公开联系人"
                add_row(
                    f"{entity}：{prefix} {normalized_person}（{label}）",
                    94 if procurement_like else 84,
                )

            for owner, field_name, value in line_contact_pattern.findall(text)[:3]:
                normalized_owner = normalize_text(owner)
                normalized_value = normalize_text(value)
                if not normalized_value or not is_valid_contact_value(normalized_value):
                    continue
                owner_text = normalized_owner if normalized_owner and normalized_owner != entity else ""
                add_row(
                    f"{entity}：{owner_text}{field_name} {normalized_value}（{label}）",
                    98 if procurement_like else (90 if official_like else 80),
                )

            for email in EMAIL_PATTERN.findall(text)[:2]:
                if not is_valid_contact_value(email):
                    continue
                add_row(
                    f"{entity}：公开邮箱 {email}（{label}）",
                    96 if official_like else (92 if procurement_like else 78),
                )

            for phone in PHONE_PATTERN.findall(text)[:2]:
                normalized_phone = normalize_text(phone)
                if not is_valid_contact_value(normalized_phone):
                    continue
                add_row(
                    f"{entity}：公开电话 {normalized_phone}（{label}）",
                    95 if procurement_like else (88 if official_like else 76),
                )

    ordered = [
        row
        for row, _ in sorted(
            scored_rows.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    if ordered:
        return ordered[:limit]
    return []


def build_entity_specific_team_rows(
    sources: list[SourceDocument],
    *,
    entity_names: list[str],
    scope_hints: dict[str, object],
    output_language: str,
    limit: int,
) -> list[str]:
    if not entity_names:
        return []

    normalized_entities = [
        normalize_text(name)
        for name in entity_names
        if normalize_text(name) and "待验证" not in normalize_text(name) and "待驗證" not in normalize_text(name)
        and (is_plausible_entity_name(normalize_text(name)) or is_lightweight_entity_name(normalize_text(name)))
    ]
    if not normalized_entities:
        return []

    team_keywords = (
        "团队",
        "事业群",
        "事业部",
        "业务线",
        "业务部",
        "行业线",
        "政企",
        "政务",
        "行业解决方案",
        "行业方案",
        "区域公司",
        "区域团队",
        "创新中心",
        "研究院",
        "交付中心",
        "运营团队",
        "商务合作",
        "合作团队",
        "内容生态",
        "生态合作",
        "大客户部",
        "客户成功",
        "公共事务",
        "投资者关系",
    )
    scope_regions = [normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    scope_region_terms = expand_region_scope_terms(scope_regions)
    scope_industries = [normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    scored_rows: dict[str, int] = {}

    def add_row(row: str, score: int) -> None:
        normalized = normalize_text(row)
        if not normalized:
            return
        current = scored_rows.get(normalized)
        if current is None or score > current:
            scored_rows[normalized] = score

    for entity in dedupe_strings(normalized_entities, 6):
        for source in sources:
            if not source_mentions_entity(source, entity):
                continue
            text = source_document_text(source)
            chunks = re.split(r"[。！？!?；;\n]", text)
            label = normalize_text(source.source_label or source.title or source.domain or entity)
            for chunk in chunks:
                sentence = normalize_text(chunk)
                if not sentence or entity not in sentence:
                    continue
                if text_has_region_conflict(sentence, scope_hints=scope_hints):
                    continue
                if not any(token in sentence for token in team_keywords):
                    continue
                score = 72
                if source.source_tier == "official":
                    score += 12
                elif source.source_tier == "aggregate":
                    score += 6
                if any(region and region in sentence for region in scope_region_terms):
                    score += 8
                if any(industry and industry in sentence for industry in scope_industries):
                    score += 6
                if any(token in sentence for token in ("负责", "牵头", "落地", "推进", "合作", "运营", "交付")):
                    score += 6
                add_row(f"{entity}：{truncate_text(sentence, 108)}（{label}）", score)

    ordered = [
        row
        for row, _ in sorted(
            scored_rows.items(),
            key=lambda item: (-item[1], item[0]),
        )
    ]
    if ordered:
        return ordered[:limit]

    scope_text = " / ".join(dedupe_strings([*scope_regions[:2], *scope_industries[:2]], 3)) or normalize_text(
        str(scope_hints.get("anchor_text", ""))
    ) or localized_text(
        output_language,
        {
            "zh-CN": "当前范围",
            "zh-TW": "目前範圍",
            "en": "the current scope",
        },
        "当前范围",
    )
    return dedupe_strings(
        [
            localized_text(
                output_language,
                {
                    "zh-CN": f"当前已收敛到具体公司，建议优先核验其在 {scope_text} 下的政企/行业方案团队、区域交付团队与商务合作团队公开线索。",
                    "zh-TW": f"目前已收斂到具體公司，建議優先核驗其在 {scope_text} 下的政企/產業方案團隊、區域交付團隊與商務合作團隊公開線索。",
                    "en": f"The report converged to specific companies. Next verify public signals for their regional delivery, industry solution, and business partnership teams within {scope_text}.",
                },
                f"当前已收敛到具体公司，建议优先核验其在 {scope_text} 下的政企/行业方案团队、区域交付团队与商务合作团队公开线索。",
            ),
        ],
        limit,
    )
