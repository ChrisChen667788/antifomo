from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import re
from typing import Any

from app.schemas.research import (
    ResearchEntityEvidenceOut,
    ResearchEntityGraphOut,
    ResearchRankedEntityOut,
    ResearchScoreFactorOut,
)
from app.services.content_extractor import extract_domain, normalize_text
from app.services.language import localized_text
from app.services.llm_parser import ResearchReportResult
from app.services.research.source_documents import SourceDocument


@dataclass(frozen=True, slots=True)
class EntityRankingHeuristicDependencies:
    clean_scope_entity_names: Callable[..., list[str]]
    entity_graph_lookup: Callable[[ResearchEntityGraphOut], dict[str, Any]]
    is_theme_aligned_entity_name: Callable[..., bool]
    is_company_like_entity_name: Callable[..., bool]
    source_text: Callable[[SourceDocument], str]
    extract_rank_entity_candidates: Callable[..., list[str]]
    canonical_org_name_from_domain: Callable[[str], str]
    dedupe_strings: Callable[[list[str], int], list[str]]
    resolve_known_org_name: Callable[..., str]
    source_type_weight: Callable[[SourceDocument], int]
    build_entity_evidence: Callable[[SourceDocument], ResearchEntityEvidenceOut]
    entity_canonical_key: Callable[[str], str]
    extract_rank_entity_name: Callable[[str], str]
    extract_org_candidates: Callable[..., list[str]]
    is_plausible_entity_name: Callable[[str], bool]
    is_lightweight_entity_name: Callable[[str], bool]
    org_entity_variants: Callable[[str], list[str]]
    source_mentions_entity: Callable[[SourceDocument, str], bool]
    source_negates_entity: Callable[[SourceDocument, str], bool]
    known_company_public_source_seeds: dict[str, tuple[tuple[str, str], ...]]
    company_profile_page_tokens: tuple[str, ...]
    theme_entity_allow_tokens: dict[str, dict[str, tuple[str, ...]]]
    generic_company_name_tokens: tuple[str, ...]
    theme_role_archetypes: dict[str, dict[str, tuple[str, ...]]]
    partner_connector_aliases: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResearchEntityRankingSets:
    top_target_accounts: list[ResearchRankedEntityOut]
    pending_target_candidates: list[ResearchRankedEntityOut]
    top_competitors: list[ResearchRankedEntityOut]
    pending_competitor_candidates: list[ResearchRankedEntityOut]
    top_ecosystem_partners: list[ResearchRankedEntityOut]
    pending_partner_candidates: list[ResearchRankedEntityOut]
    candidate_public_profile_names: list[str]

    def contact_entity_names(
        self,
        *,
        scope_clients: list[object],
        dedupe_strings: Callable[[list[str], int], list[str]],
    ) -> list[str]:
        return dedupe_strings(
            [
                *(normalize_text(item.name) for item in self.top_target_accounts if normalize_text(item.name)),
                *(normalize_text(item.name) for item in self.top_ecosystem_partners if normalize_text(item.name)),
                *(normalize_text(str(item)) for item in scope_clients if normalize_text(str(item))),
            ],
            6,
        )

    def team_entity_names(
        self,
        *,
        scope_clients: list[object],
        dedupe_strings: Callable[[list[str], int], list[str]],
    ) -> list[str]:
        return dedupe_strings(
            [
                *(normalize_text(item.name) for item in self.top_target_accounts if normalize_text(item.name)),
                *(normalize_text(item.name) for item in self.pending_target_candidates if normalize_text(item.name)),
                *(normalize_text(item.name) for item in self.top_ecosystem_partners if normalize_text(item.name)),
                *(normalize_text(item.name) for item in self.pending_partner_candidates if normalize_text(item.name)),
                *(normalize_text(str(item)) for item in scope_clients if normalize_text(str(item))),
            ],
            6,
        )


def rank_report_entities(
    *,
    sources: list[SourceDocument],
    parsed: ResearchReportResult,
    output_language: str,
    scope_hints: dict[str, object],
    theme_terms: list[str],
    entity_graph: ResearchEntityGraphOut,
    rank_top_entities: Callable[..., tuple[list[ResearchRankedEntityOut], list[ResearchRankedEntityOut]]],
    filtered_rank_fallback_values: Callable[..., list[str]],
    dedupe_strings: Callable[[list[str], int], list[str]],
    limit: int = 3,
) -> ResearchEntityRankingSets:
    top_target_accounts, pending_target_candidates = rank_top_entities(
        sources,
        role="target",
        output_language=output_language,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        entity_graph=entity_graph,
        fallback_values=filtered_rank_fallback_values(parsed.target_accounts, role="target", scope_hints=scope_hints),
        limit=limit,
    )
    top_competitors, pending_competitor_candidates = rank_top_entities(
        sources,
        role="competitor",
        output_language=output_language,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        entity_graph=entity_graph,
        fallback_values=filtered_rank_fallback_values(
            [*parsed.competitor_profiles, *parsed.winner_peer_moves],
            role="competitor",
            scope_hints=scope_hints,
        ),
        limit=limit,
    )
    top_ecosystem_partners, pending_partner_candidates = rank_top_entities(
        sources,
        role="partner",
        output_language=output_language,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        entity_graph=entity_graph,
        fallback_values=filtered_rank_fallback_values(
            parsed.ecosystem_partners,
            role="partner",
            scope_hints=scope_hints,
        ),
        limit=limit,
    )
    candidate_public_profile_names = dedupe_strings(
        [
            *(normalize_text(item.name) for item in top_target_accounts if normalize_text(item.name)),
            *(normalize_text(item.name) for item in pending_target_candidates if normalize_text(item.name)),
            *(normalize_text(item.name) for item in top_ecosystem_partners if normalize_text(item.name)),
            *(normalize_text(item.name) for item in pending_partner_candidates if normalize_text(item.name)),
            *(normalize_text(item.name) for item in top_competitors if normalize_text(item.name)),
            *(normalize_text(item.name) for item in pending_competitor_candidates if normalize_text(item.name)),
        ],
        6,
    )
    return ResearchEntityRankingSets(
        top_target_accounts=top_target_accounts,
        pending_target_candidates=pending_target_candidates,
        top_competitors=top_competitors,
        pending_competitor_candidates=pending_competitor_candidates,
        top_ecosystem_partners=top_ecosystem_partners,
        pending_partner_candidates=pending_partner_candidates,
        candidate_public_profile_names=candidate_public_profile_names,
    )


def promote_ranked_entities_with_candidate_profiles(
    rankings: ResearchEntityRankingSets,
    *,
    candidate_profile_sources: list[SourceDocument],
    candidate_profile_companies: list[str],
    build_candidate_profile_support: Callable[[list[SourceDocument], list[str]], Any],
    promote_pending_entities_with_candidate_profiles: Callable[..., tuple[list[ResearchRankedEntityOut], list[ResearchRankedEntityOut]]],
    limit: int = 3,
) -> ResearchEntityRankingSets:
    if not candidate_profile_sources:
        return rankings
    candidate_profile_support = build_candidate_profile_support(
        candidate_profile_sources,
        candidate_profile_companies,
    )
    top_target_accounts, pending_target_candidates = promote_pending_entities_with_candidate_profiles(
        rankings.top_target_accounts,
        rankings.pending_target_candidates,
        candidate_profile_support=candidate_profile_support,
        limit=limit,
    )
    top_competitors, pending_competitor_candidates = promote_pending_entities_with_candidate_profiles(
        rankings.top_competitors,
        rankings.pending_competitor_candidates,
        candidate_profile_support=candidate_profile_support,
        limit=limit,
    )
    top_ecosystem_partners, pending_partner_candidates = promote_pending_entities_with_candidate_profiles(
        rankings.top_ecosystem_partners,
        rankings.pending_partner_candidates,
        candidate_profile_support=candidate_profile_support,
        limit=limit,
    )
    return ResearchEntityRankingSets(
        top_target_accounts=top_target_accounts,
        pending_target_candidates=pending_target_candidates,
        top_competitors=top_competitors,
        pending_competitor_candidates=pending_competitor_candidates,
        top_ecosystem_partners=top_ecosystem_partners,
        pending_partner_candidates=pending_partner_candidates,
        candidate_public_profile_names=rankings.candidate_public_profile_names,
    )

def _build_ranked_entity_reasoning(
    *,
    output_language: str,
    role: str,
    official_hits: int,
    matched_signals: list[str],
    scope_regions: list[str],
    scope_industries: list[str],
    evidence_count: int,
) -> str:
    signal_text = "、".join(matched_signals[:3]) or localized_text(
        output_language,
        {"zh-CN": "公开线索", "zh-TW": "公開線索", "en": "public evidence"},
        "公开线索",
    )
    scope_bits = [item for item in [*(scope_regions[:1] or []), *(scope_industries[:1] or [])] if item]
    scope_text = " / ".join(scope_bits) if scope_bits else localized_text(
        output_language,
        {"zh-CN": "当前关键词范围", "zh-TW": "目前關鍵詞範圍", "en": "the current keyword scope"},
        "当前关键词范围",
    )
    if role == "target":
        return localized_text(
            output_language,
            {
                "zh-CN": f"高价值甲方候选：在 {scope_text} 范围内命中 {evidence_count} 条相关线索，包含 {official_hits} 条官方/招采证据，且与 {signal_text} 高度相关。",
                "zh-TW": f"高價值甲方候選：在 {scope_text} 範圍內命中 {evidence_count} 條相關線索，包含 {official_hits} 條官方/招採證據，且與 {signal_text} 高度相關。",
                "en": f"High-value buyer candidate: {evidence_count} matching signals within {scope_text}, including {official_hits} official or tender sources, with strong relevance to {signal_text}.",
            },
            f"高价值甲方候选：在 {scope_text} 范围内命中 {evidence_count} 条相关线索，包含 {official_hits} 条官方/招采证据，且与 {signal_text} 高度相关。",
        )
    if role == "competitor":
        return localized_text(
            output_language,
            {
                "zh-CN": f"高威胁竞品候选：在 {scope_text} 范围内命中 {evidence_count} 条中标/方案/平台相关线索，包含 {official_hits} 条较高可信证据，显示其对 {signal_text} 有较强覆盖。",
                "zh-TW": f"高威脅競品候選：在 {scope_text} 範圍內命中 {evidence_count} 條中標/方案/平台相關線索，包含 {official_hits} 條較高可信證據，顯示其對 {signal_text} 有較強覆蓋。",
                "en": f"High-threat competitor candidate: {evidence_count} bid/solution/platform signals within {scope_text}, including {official_hits} stronger sources, indicating solid coverage around {signal_text}.",
            },
            f"高威胁竞品候选：在 {scope_text} 范围内命中 {evidence_count} 条中标/方案/平台相关线索，包含 {official_hits} 条较高可信证据，显示其对 {signal_text} 有较强覆盖。",
        )
    return localized_text(
        output_language,
        {
            "zh-CN": f"高影响力生态伙伴候选：在 {scope_text} 范围内命中 {evidence_count} 条合作/联合/渠道相关线索，包含 {official_hits} 条高可信证据，更偏牵线、集成或生态协同，而非单纯自研产品输出。",
            "zh-TW": f"高影響力生態夥伴候選：在 {scope_text} 範圍內命中 {evidence_count} 條合作/聯合/渠道相關線索，包含 {official_hits} 條高可信證據，更偏牽線、整合或生態協同，而非單純自研產品輸出。",
            "en": f"High-influence ecosystem partner candidate: {evidence_count} collaboration/channel signals within {scope_text}, including {official_hits} stronger sources, indicating connector, integrator, or ecosystem-building roles rather than pure product output.",
        },
        f"高影响力生态伙伴候选：在 {scope_text} 范围内命中 {evidence_count} 条合作/联合/渠道相关线索，包含 {official_hits} 条高可信证据，更偏牵线、集成或生态协同，而非单纯自研产品输出。",
    )


def _build_fallback_entity_reasoning(
    *,
    output_language: str,
    role: str,
    evidence_count: int,
    scope_regions: list[str],
    scope_industries: list[str],
) -> str:
    scope_bits = [item for item in [*(scope_regions[:1] or []), *(scope_industries[:1] or [])] if item]
    scope_text = " / ".join(scope_bits) if scope_bits else localized_text(
        output_language,
        {"zh-CN": "当前关键词范围", "zh-TW": "目前關鍵詞範圍", "en": "the current keyword scope"},
        "当前关键词范围",
    )
    if role == "target":
        return localized_text(
            output_language,
            {
                "zh-CN": f"基于 {scope_text} 范围内的公开线索交叉归纳得出，当前直接证据相对有限，但该主体在预算、采购或项目语境中的出现频次较高，建议继续作为高价值甲方候选跟踪。",
                "zh-TW": f"基於 {scope_text} 範圍內的公開線索交叉歸納得出，目前直接證據相對有限，但該主體在預算、採購或專案語境中的出現頻次較高，建議持續作為高價值甲方候選追蹤。",
                "en": f"Derived from cross-reading public signals within {scope_text}. Direct evidence is still limited, but the entity appears frequently in budget, procurement, or project contexts and should remain on the buyer watchlist.",
            },
            f"基于 {scope_text} 范围内的公开线索交叉归纳得出，当前直接证据相对有限，但该主体在预算、采购或项目语境中的出现频次较高，建议继续作为高价值甲方候选跟踪。",
        )
    if role == "competitor":
        return localized_text(
            output_language,
            {
                "zh-CN": f"基于 {scope_text} 范围内的公开线索交叉归纳得出，当前直接中标证据有限，但该主体在方案、平台、交付或竞对语境中的出现频次较高，建议作为高威胁竞品持续观察。",
                "zh-TW": f"基於 {scope_text} 範圍內的公開線索交叉歸納得出，目前直接中標證據有限，但該主體在方案、平台、交付或競對語境中的出現頻次較高，建議作為高威脅競品持續觀察。",
                "en": f"Derived from cross-reading public signals within {scope_text}. Direct winning evidence is limited, but the entity appears frequently in solution, platform, delivery, or rivalry contexts and should remain on the competitor watchlist.",
            },
            f"基于 {scope_text} 范围内的公开线索交叉归纳得出，当前直接中标证据有限，但该主体在方案、平台、交付或竞对语境中的出现频次较高，建议作为高威胁竞品持续观察。",
        )
    return localized_text(
        output_language,
        {
            "zh-CN": f"基于 {scope_text} 范围内的公开线索交叉归纳得出，当前直接合作证据有限，但该主体在咨询、集成、渠道或联盟语境中的出现频次较高，更适合作为潜在牵线或生态协同伙伴。",
            "zh-TW": f"基於 {scope_text} 範圍內的公開線索交叉歸納得出，目前直接合作證據有限，但該主體在諮詢、整合、渠道或聯盟語境中的出現頻次較高，更適合作為潛在牽線或生態協同夥伴。",
            "en": f"Derived from cross-reading public signals within {scope_text}. Direct collaboration evidence is limited, but the entity appears repeatedly in consulting, integration, channel, or alliance contexts and is better treated as a potential connector or ecosystem partner.",
        },
        f"基于 {scope_text} 范围内的公开线索交叉归纳得出，当前直接合作证据有限，但该主体在咨询、集成、渠道或联盟语境中的出现频次较高，更适合作为潜在牵线或生态协同伙伴。",
    )


def _build_score_factor(
    *,
    label: str,
    score: int,
    note: str,
) -> ResearchScoreFactorOut:
    return ResearchScoreFactorOut(label=label, score=score, note=note)


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
    deps: EntityRankingHeuristicDependencies,
) -> tuple[list[ResearchRankedEntityOut], list[ResearchRankedEntityOut]]:
    _clean_scope_entity_names = deps.clean_scope_entity_names
    _entity_graph_lookup = deps.entity_graph_lookup
    _is_theme_aligned_entity_name = deps.is_theme_aligned_entity_name
    _is_company_like_entity_name = deps.is_company_like_entity_name
    _source_text = deps.source_text
    _extract_rank_entity_candidates = deps.extract_rank_entity_candidates
    _canonical_org_name_from_domain = deps.canonical_org_name_from_domain
    _dedupe_strings = deps.dedupe_strings
    _resolve_known_org_name = deps.resolve_known_org_name
    _source_type_weight = deps.source_type_weight
    _build_entity_evidence = deps.build_entity_evidence
    _entity_canonical_key = deps.entity_canonical_key
    _extract_rank_entity_name = deps.extract_rank_entity_name
    _extract_org_candidates = deps.extract_org_candidates
    _is_plausible_entity_name = deps.is_plausible_entity_name
    _is_lightweight_entity_name = deps.is_lightweight_entity_name
    _org_entity_variants = deps.org_entity_variants
    THEME_ENTITY_ALLOW_TOKENS = deps.theme_entity_allow_tokens
    GENERIC_COMPANY_NAME_TOKENS = deps.generic_company_name_tokens
    THEME_ROLE_ARCHETYPES = deps.theme_role_archetypes
    PARTNER_CONNECTOR_ALIASES = deps.partner_connector_aliases

    role_context_map = {
        "target": ("招标", "采购", "预算", "项目", "建设", "规划", "部署", "业主", "甲方"),
        "competitor": ("中标", "平台", "产品", "解决方案", "厂商", "交付", "案例", "集成商"),
        "partner": ("合作", "伙伴", "联合", "生态", "咨询", "集成商", "渠道", "联盟", "运营"),
    }
    positive_name_tokens_map = {
        "target": ("政府", "局", "委", "办", "中心", "医院", "大学", "银行", "学校", "集团", "城投", "交投"),
        "competitor": ("科技", "信息", "软件", "智能", "云", "数据", "通信", "股份", "有限公司"),
        "partner": ("咨询", "顾问", "集成", "渠道", "联盟", "协会", "研究院", "研究所", "运营", "服务"),
    }
    preferred_source_types_map = {
        "target": {"procurement", "policy", "filing", "official_tender_feed", "official_policy_speech", "compliant_procurement_aggregate"},
        "competitor": {"tender_feed", "web", "tech_media_feed", "filing", "official_tender_feed"},
        "partner": {"web", "tech_media_feed", "procurement", "policy", "official_tender_feed"},
    }
    partner_penalty_tokens = ("产品", "平台", "芯片", "模型", "自研", "算法", "大模型")
    institution_tokens = ("政府", "数据局", "局", "委", "办", "中心", "医院", "大学", "学校", "银行", "城投", "交投", "水务", "地铁")
    vendor_tokens = ("科技", "软件", "云", "数码", "智能", "信息", "平台", "模型", "算法", "芯片")
    scope_regions = [normalize_text(item) for item in scope_hints.get("regions", []) if normalize_text(str(item))]
    scope_industries = [normalize_text(item) for item in scope_hints.get("industries", []) if normalize_text(str(item))]
    scope_clients = _clean_scope_entity_names(
        [normalize_text(item) for item in scope_hints.get("clients", []) if normalize_text(str(item))],
        limit=3,
        theme_labels=scope_industries,
    )
    seed_companies = [
        normalize_text(str(item))
        for item in (scope_hints.get("seed_companies", []) or [])
        if normalize_text(str(item))
    ]
    prefer_company_entities = bool(scope_hints.get("prefer_company_entities"))
    prefer_head_companies = bool(scope_hints.get("prefer_head_companies"))
    theme_labels = [label for label in scope_industries if normalize_text(label)]
    context_keywords = role_context_map.get(role, ())
    if prefer_company_entities and role in {"target", "competitor"}:
        themed_company_tokens = [
            token
            for label in theme_labels
            for token in THEME_ENTITY_ALLOW_TOKENS.get(label, {}).get(role, ())
            if normalize_text(token) and token not in {"内容", "运营", "服务"}
        ]
        positive_tokens = tuple(
            dict.fromkeys(
                [
                    *themed_company_tokens,
                    *GENERIC_COMPANY_NAME_TOKENS,
                    "版权",
                    "发行",
                    "商业化",
                ]
            )
        )
    else:
        positive_tokens = positive_name_tokens_map.get(role, ())
    preferred_source_types = preferred_source_types_map.get(role, set())
    graph_lookup = _entity_graph_lookup(entity_graph) if entity_graph else {}

    role_relation_patterns = {
        "target": (
            r"(?:采购人|招标人|业主单位|建设单位|需求方|甲方|出资方|投资方|主管部门)\s*[:：]?\s*{name}",
            r"(?:由|联合)\s*{name}\s*(?:指导|主办|牵头|负责|统筹|建设|采购)",
            r"{name}\s*(?:拟|将|计划|启动|牵头|负责|统筹|建设|采购|招标|投资|出资)",
        ),
        "competitor": (
            r"(?:中标人|中标单位|成交供应商|供应商|承建方|运营方|厂商)\s*[:：]?\s*{name}",
            r"{name}.{0,48}(?:中标|成交|承建|交付|提供|推出|发布|运营|解决方案|平台|产品|案例)",
        ),
        "partner": (
            r"(?:合作伙伴|生态伙伴|联合体成员|集成商|咨询方|渠道方)\s*[:：]?\s*{name}",
            r"{name}.{0,36}(?:合作|联合|生态|咨询|集成|渠道|联盟|承办)",
            r"(?:与|联合)\s*{name}.{0,24}(?:合作|共建|签约|联合)",
        ),
    }

    def candidate_local_context(name: str, text: str, *, radius: int = 72) -> str:
        windows: list[str] = []
        variants = _dedupe_strings([name, *_org_entity_variants(name)], 6)
        for variant in variants:
            if not variant:
                continue
            start = 0
            while (index := text.find(variant, start)) >= 0:
                windows.append(text[max(0, index - radius) : min(len(text), index + len(variant) + radius)])
                start = index + len(variant)
                if len(windows) >= 4:
                    break
            if len(windows) >= 4:
                break
        return normalize_text(" ".join(windows))

    def has_explicit_role_relation(name: str, text: str) -> bool:
        variants = _dedupe_strings([name, *_org_entity_variants(name)], 6)
        for variant in variants:
            if not variant or variant not in text:
                continue
            escaped = re.escape(variant)
            if any(
                re.search(pattern.replace("{name}", escaped), text, flags=re.IGNORECASE)
                for pattern in role_relation_patterns.get(role, ())
            ):
                return True
        return False

    def build_entity_result(
        *,
        name: str,
        score: int,
        reasoning: str,
        score_breakdown: list[ResearchScoreFactorOut],
        evidence_links: list[ResearchEntityEvidenceOut],
        entity_mode: Literal["instance", "pending"] = "instance",
    ) -> ResearchRankedEntityOut:
        return ResearchRankedEntityOut(
            name=name,
            score=score,
            reasoning=reasoning,
            entity_mode=entity_mode,
            score_breakdown=score_breakdown,
            evidence_links=evidence_links,
        )

    def build_archetype_results() -> list[ResearchRankedEntityOut]:
        if role == "target" and scope_clients:
            return [
                build_entity_result(
                    name=name,
                    score=max(52, 68 - index * 6),
                    reasoning=localized_text(
                        output_language,
                        {
                            "zh-CN": f"关键词已经直接收敛到 {name}，当前主要缺的是更高置信的项目、预算与官网联络证据，因此先将其保留为重点甲方候选并继续补证。",
                            "zh-TW": f"關鍵詞已直接收斂到 {name}，目前主要缺的是更高置信的專案、預算與官網聯絡證據，因此先將其保留為重點甲方候選並持續補證。",
                            "en": f"The query already converges on {name}. What is missing is higher-confidence project, budget, and official-contact evidence, so it remains on the buyer shortlist pending further verification.",
                        },
                        f"关键词已经直接收敛到 {name}，当前主要缺的是更高置信的项目、预算与官网联络证据，因此先将其保留为重点甲方候选并继续补证。",
                    ),
                    score_breakdown=[
                        _build_score_factor(
                            label="公司锚点命中",
                            score=28,
                            note=name,
                        ),
                        _build_score_factor(
                            label="公开证据待补",
                            score=18,
                            note="优先补官网联系页、采购公告联系人和投资者关系入口",
                        ),
                    ],
                    evidence_links=[],
                    entity_mode="pending",
                )
                for index, name in enumerate(scope_clients[:limit])
            ]
        theme_label = next((label for label in scope_industries if label in THEME_ROLE_ARCHETYPES), "")
        archetypes = THEME_ROLE_ARCHETYPES.get(theme_label, {}).get(role, ())
        if not archetypes:
            return []
        role_label = {
            "target": localized_text(output_language, {"zh-CN": "高价值甲方", "zh-TW": "高價值甲方", "en": "buyer target"}, "高价值甲方"),
            "competitor": localized_text(output_language, {"zh-CN": "高威胁竞品", "zh-TW": "高威脅競品", "en": "competitor threat"}, "高威胁竞品"),
            "partner": localized_text(output_language, {"zh-CN": "高影响力生态伙伴", "zh-TW": "高影響力生態夥伴", "en": "ecosystem partner"}, "高影响力生态伙伴"),
        }.get(role, localized_text(output_language, {"zh-CN": "候选对象", "zh-TW": "候選對象", "en": "candidate"}, "候选对象"))
        return [
            build_entity_result(
                name=name,
                score=max(24, 36 - index * 2),
                reasoning=localized_text(
                    output_language,
                    {
                        "zh-CN": f"当前公开证据还不足以锁定具体公司名，这里先按 {theme_label or '当前主题'} 的 {role_label} 角色给出高价值候选补位，建议补充区域、客户类型或项目词后再确认公司名。",
                        "zh-TW": f"目前公開證據仍不足以鎖定具體公司名，先按 {theme_label or '目前主題'} 的 {role_label} 角色給出高價值候選補位，建議補充區域、客戶類型或專案詞後再確認公司名。",
                        "en": f"Public evidence is still insufficient to lock a concrete company. This is a role-based placeholder for {theme_label or 'the current theme'} and should be refined with more region, client-type, or project keywords.",
                    },
                    f"当前公开证据还不足以锁定具体公司名，这里先按 {theme_label or '当前主题'} 的 {role_label} 角色给出高价值候选补位，建议补充区域、客户类型或项目词后再确认公司名。",
                ),
                score_breakdown=[
                    _build_score_factor(
                        label="主题收敛",
                        score=18,
                        note=theme_label or "当前关键词主题",
                    ),
                    _build_score_factor(
                        label="角色化兜底",
                        score=12,
                        note="当前缺少高置信实体证据",
                    ),
                ],
                evidence_links=[],
                entity_mode="pending",
            )
            for index, name in enumerate(archetypes[:limit])
        ]

    def allow_role_candidate(name: str, text: str, *, require_role_relation: bool = True) -> bool:
        if not (
            _is_plausible_entity_name(name)
            or _is_lightweight_entity_name(name)
            or name in seed_companies
            or name in scope_clients
        ):
            return False
        if theme_labels and not _is_theme_aligned_entity_name(name, role=role, theme_labels=theme_labels):
            return False
        if prefer_company_entities and role in {"target", "competitor"} and not _is_company_like_entity_name(
            name,
            role=role,
            theme_labels=theme_labels,
            seed_companies=seed_companies,
        ):
            return False
        if any(client and (client in name or name in client) for client in scope_clients):
            return role == "target"
        if require_role_relation and not has_explicit_role_relation(name, text):
            return False
        if role == "target":
            if prefer_company_entities:
                return (
                    any(token in name for token in positive_tokens)
                    or any(
                        token in text
                        for token in ("合作", "版权", "发行", "平台", "内容", "动画", "短剧", "AIGC", "商业化", "团队", "生态", "案例")
                    )
                )
            return (
                any(token in name for token in positive_tokens)
                or any(token in text for token in ("预算", "采购", "招标", "建设", "立项", "扩容"))
            )
        if role == "competitor":
            if any(token in name for token in institution_tokens):
                return False
            return (
                any(token in name for token in positive_tokens)
                or any(token in text for token in ("中标", "成交", "方案", "平台", "交付", "厂商", "案例"))
            )
        if any(token in name for token in institution_tokens) or any(token in name for token in partner_penalty_tokens):
            return False
        if any(token in name for token in vendor_tokens) and not any(alias in name for alias in PARTNER_CONNECTOR_ALIASES):
            return False
        return (
            any(alias in name for alias in PARTNER_CONNECTOR_ALIASES)
            or
            any(token in name for token in positive_tokens)
            or any(token in text for token in ("合作", "伙伴", "联合", "联盟", "咨询", "顾问", "渠道", "集成"))
        )

    def is_duplicate_name(name: str) -> bool:
        for existing in used_names:
            if name == existing:
                return True
            if len(name) >= 5 and len(existing) >= 5 and (name in existing or existing in name):
                return True
        return False

    def has_instance_support(name: str, state: dict[str, object]) -> bool:
        if theme_labels and not _is_theme_aligned_entity_name(name, role=role, theme_labels=theme_labels):
            return False
        if prefer_company_entities and role in {"target", "competitor"} and not _is_company_like_entity_name(
            name,
            role=role,
            theme_labels=theme_labels,
            seed_companies=seed_companies,
        ):
            return False
        graph_entity = graph_lookup.get(_entity_canonical_key(name))
        evidence_count = int(state.get("evidence_count", 0) or 0)
        official_hits = int(state.get("official_hits", 0) or 0)
        evidence_links = [item for item in list(state.get("links", [])) if getattr(item, "url", "")]
        graph_source_count = int(getattr(graph_entity, "source_count", 0) or 0) if graph_entity is not None else 0
        graph_official_count = int(getattr(graph_entity, "source_tier_counts", {}).get("official", 0) or 0) if graph_entity is not None else 0
        support_count = max(evidence_count, len(evidence_links), graph_source_count)
        has_official_support = official_hits > 0 or graph_official_count > 0
        if any(client and (client in name or name in client) for client in scope_clients):
            return has_official_support or support_count >= 1
        if prefer_head_companies and role in {"target", "competitor"}:
            return has_official_support or support_count >= 2
        return has_official_support or support_count >= 2

    scored: dict[str, dict[str, object]] = {}
    for source in sources:
        text = _source_text(source)
        lowered = text.lower()
        if theme_terms and not any(term in lowered for term in theme_terms):
            continue
        official_hit = 1 if source.source_tier == "official" else 0
        extracted_names = _extract_rank_entity_candidates(text, scope_hints=scope_hints)
        domain_canonical = _canonical_org_name_from_domain(source.domain or extract_domain(source.url))
        if domain_canonical:
            extracted_names.append(domain_canonical)
        for name in _dedupe_strings(extracted_names, 8):
            name = _resolve_known_org_name(name, scope_hints=scope_hints, source=source)
            if len(name) < 3:
                continue
            if not allow_role_candidate(name, text):
                continue
            local_text = candidate_local_context(name, text) or text
            matched_signals = [token for token in context_keywords if token in local_text]
            graph_entity = graph_lookup.get(_entity_canonical_key(name))
            if graph_entity is not None:
                graph_role = normalize_text(graph_entity.entity_type)
                if graph_role not in {role, "generic"}:
                    continue
                canonical_name = normalize_text(graph_entity.canonical_name)
                if canonical_name:
                    name = canonical_name
            if theme_labels and not _is_theme_aligned_entity_name(name, role=role, theme_labels=theme_labels):
                continue
            if prefer_company_entities and role in {"target", "competitor"} and not _is_company_like_entity_name(
                name,
                role=role,
                theme_labels=theme_labels,
                seed_companies=seed_companies,
            ):
                continue
            score = _source_type_weight(source)
            score_breakdown = [
                _build_score_factor(
                    label="来源层级",
                    score=_source_type_weight(source),
                    note=f"{source.source_tier or 'media'} / {source.source_type}",
                )
            ]
            score += min(len(matched_signals), 3) * 6
            if matched_signals:
                score_breakdown.append(
                    _build_score_factor(
                        label="角色信号",
                        score=min(len(matched_signals), 3) * 6,
                        note="、".join(matched_signals[:3]),
                    )
                )
            score += sum(1 for token in positive_tokens if token in name) * 4
            if any(token in name for token in positive_tokens):
                score_breakdown.append(
                    _build_score_factor(
                        label="实体匹配",
                        score=sum(1 for token in positive_tokens if token in name) * 4,
                        note=name,
                    )
                )
            if source.source_type in preferred_source_types:
                score += 8
                score_breakdown.append(
                    _build_score_factor(
                        label="优先来源类型",
                        score=8,
                        note=source.source_type,
                    )
                )
            if any(region and region in text for region in scope_regions):
                score += 5
                score_breakdown.append(
                    _build_score_factor(
                        label="区域收敛",
                        score=5,
                        note=" / ".join(scope_regions[:2]) or "命中区域",
                    )
                )
            if any(client and client in name for client in scope_clients):
                score += 10
                score_breakdown.append(
                    _build_score_factor(
                        label="甲方范围贴合",
                        score=10,
                        note=" / ".join(scope_clients[:2]) or "命中甲方范围",
                    )
                )
            if prefer_company_entities and role in {"target", "competitor"} and (
                name in seed_companies or _is_lightweight_entity_name(name)
            ):
                score += 8
                score_breakdown.append(
                    _build_score_factor(
                        label="公司名单命中",
                        score=8,
                        note=name,
                    )
                )
            if role == "target" and any(token in name for token in vendor_tokens) and not any(client and client in name for client in scope_clients):
                score -= 10
                score_breakdown.append(
                    _build_score_factor(
                        label="业主角色惩罚",
                        score=-10,
                        note="更像厂商或平台方",
                    )
                )
            if role == "partner":
                if any(token in text for token in ("联合体", "合作伙伴", "咨询", "渠道", "集成", "联盟")):
                    score += 10
                    score_breakdown.append(
                        _build_score_factor(
                            label="生态协同信号",
                            score=10,
                            note="合作 / 渠道 / 咨询 / 集成",
                        )
                    )
                if any(token in text for token in partner_penalty_tokens):
                    score -= 8
                    score_breakdown.append(
                        _build_score_factor(
                            label="产品型惩罚",
                            score=-8,
                            note="更像自研产品或平台输出",
                        )
                    )
            if role == "competitor" and any(token in text for token in ("中标", "成交", "落地", "案例")):
                score += 8
                score_breakdown.append(
                    _build_score_factor(
                        label="竞标活跃度",
                        score=8,
                        note="中标 / 成交 / 落地 / 案例",
                    )
                )
            if role == "target" and any(token in text for token in ("预算", "采购", "项目", "建设")):
                score += 8
                score_breakdown.append(
                    _build_score_factor(
                        label="预算与项目信号",
                        score=8,
                        note="预算 / 采购 / 项目 / 建设",
                    )
                )
            if graph_entity is not None:
                graph_source_count = int(graph_entity.source_count)
                graph_official_count = int(graph_entity.source_tier_counts.get("official", 0))
                graph_bonus = min(graph_source_count, 4) * 2 + min(graph_official_count, 2) * 3
                if graph_bonus:
                    score += graph_bonus
                    score_breakdown.append(
                        _build_score_factor(
                            label="实体归一化覆盖",
                            score=graph_bonus,
                            note=f"归一后命中 {graph_source_count} 个来源，官方源 {graph_official_count} 个",
                        )
                    )

            state = scored.setdefault(
                name,
                {
                    "score": 0,
                    "evidence_count": 0,
                    "official_hits": 0,
                    "signals": [],
                    "links": [],
                    "score_breakdown": [],
                },
            )
            state["score"] = int(state["score"]) + score
            state["evidence_count"] = int(state["evidence_count"]) + 1
            state["official_hits"] = int(state["official_hits"]) + official_hit
            state["signals"] = _dedupe_strings([*state["signals"], *matched_signals], 4)
            existing_breakdown = list(state["score_breakdown"])
            for factor in score_breakdown:
                index = next((idx for idx, current in enumerate(existing_breakdown) if current.label == factor.label and current.note == factor.note), -1)
                if index >= 0:
                    merged = existing_breakdown[index]
                    existing_breakdown[index] = ResearchScoreFactorOut(
                        label=merged.label,
                        score=merged.score + factor.score,
                        note=merged.note,
                    )
                else:
                    existing_breakdown.append(factor)
            state["score_breakdown"] = existing_breakdown[:8]
            links = list(state["links"])
            evidence = _build_entity_evidence(source)
            if evidence.url and not any(item.url == evidence.url for item in links):
                links.append(evidence)
            state["links"] = links[:3]

    ranked = sorted(scored.items(), key=lambda item: (-int(item[1]["score"]), -int(item[1]["official_hits"]), item[0]))
    results: list[ResearchRankedEntityOut] = []
    pending: list[ResearchRankedEntityOut] = []
    used_names: set[str] = set()
    for name, state in ranked:
        if is_duplicate_name(name):
            continue
        reasoning = _build_ranked_entity_reasoning(
            output_language=output_language,
            role=role,
            official_hits=int(state["official_hits"]),
            matched_signals=list(state["signals"]),
            scope_regions=scope_regions,
            scope_industries=scope_industries,
            evidence_count=int(state["evidence_count"]),
        )
        entity = build_entity_result(
            name=name,
            score=min(100, int(state["score"])),
            reasoning=reasoning,
            score_breakdown=sorted(
                list(state["score_breakdown"]),
                key=lambda item: abs(int(item.score)),
                reverse=True,
            )[:5],
            evidence_links=list(state["links"]),
            entity_mode="instance" if has_instance_support(name, state) else "pending",
        )
        if entity.entity_mode == "instance" and len(results) < limit:
            used_names.add(name)
            results.append(entity)
            continue
        if len(pending) < limit:
            pending.append(entity)

    def is_valid_fallback_name(name: str) -> bool:
        if not name or len(name) < 3 or is_duplicate_name(name):
            return False
        if not _is_plausible_entity_name(name):
            return False
        if theme_labels and not _is_theme_aligned_entity_name(name, role=role, theme_labels=theme_labels):
            return False
        if prefer_company_entities and role in {"target", "competitor"} and not _is_company_like_entity_name(
            name,
            role=role,
            theme_labels=theme_labels,
            seed_companies=seed_companies,
        ):
            return False
        return allow_role_candidate(name, name, require_role_relation=False)

    fallback_pool: list[str] = []
    if sources:
        fallback_pool.extend(seed_companies)
        for raw in fallback_values or []:
            name = _extract_rank_entity_name(str(raw))
            if name:
                graph_entity = graph_lookup.get(_entity_canonical_key(name))
                if graph_entity is not None and normalize_text(graph_entity.canonical_name):
                    name = normalize_text(graph_entity.canonical_name)
                fallback_pool.append(_resolve_known_org_name(name, scope_hints=scope_hints))
        fallback_pool.extend(_extract_org_candidates(sources, limit=48, scope_hints=scope_hints))
        if entity_graph is not None:
            fallback_pool.extend(entity.canonical_name for entity in entity_graph.entities if normalize_text(entity.canonical_name))
        fallback_pool.extend(scope_clients)
    for name in _dedupe_strings(fallback_pool, 18):
        name = _resolve_known_org_name(name, scope_hints=scope_hints)
        if len(pending) >= limit:
            break
        if not is_valid_fallback_name(name):
            continue
        related_sources = [source for source in sources if name in _source_text(source)][:3]
        graph_entity = graph_lookup.get(_entity_canonical_key(name))
        graph_source_count = int(getattr(graph_entity, "source_count", 0) or 0) if graph_entity is not None else 0
        graph_official_hits = (
            int((getattr(graph_entity, "source_tier_counts", {}) or {}).get("official", 0) or 0)
            if graph_entity is not None
            else 0
        )
        has_scope_anchor = any(client and (client in name or name in client) for client in scope_clients)
        if not related_sources and not has_scope_anchor and graph_source_count == 0:
            continue
        if not has_scope_anchor and not any(
            has_explicit_role_relation(name, _source_text(source))
            for source in related_sources
        ):
            continue
        official_hits = max(sum(1 for source in related_sources if source.source_tier == "official"), graph_official_hits)
        evidence_links = [_build_entity_evidence(source) for source in related_sources]
        signals: list[str] = []
        for source in related_sources:
            text = _source_text(source)
            local_text = candidate_local_context(name, text)
            signals.extend([token for token in context_keywords if token in local_text])
        evidence_count = max(1, len(related_sources), graph_source_count)
        base_score = 34 + min(evidence_count, 3) * 9 + official_hits * 8
        if role == "target" and any(client and client in name for client in scope_clients):
            base_score += 8
        if role == "partner" and any(token in name for token in ("咨询", "顾问", "集成", "渠道", "联盟", "研究院", "协会")):
            base_score += 8
        if role == "competitor" and any(token in name for token in ("科技", "信息", "软件", "智能", "数据", "云")):
            base_score += 6
        if prefer_head_companies and name in seed_companies:
            base_score += 8
        pending.append(
            build_entity_result(
                name=name,
                score=min(92, base_score),
                reasoning=(
                    _build_ranked_entity_reasoning(
                        output_language=output_language,
                        role=role,
                        official_hits=official_hits,
                        matched_signals=_dedupe_strings(signals, 4),
                        scope_regions=scope_regions,
                        scope_industries=scope_industries,
                        evidence_count=evidence_count,
                    )
                    if signals
                    else _build_fallback_entity_reasoning(
                        output_language=output_language,
                        role=role,
                        evidence_count=evidence_count,
                        scope_regions=scope_regions,
                        scope_industries=scope_industries,
                    )
                ),
                score_breakdown=[
                    _build_score_factor(
                        label="范围收敛",
                        score=18,
                        note=" / ".join(scope_regions[:1] + scope_industries[:1]) or "当前关键词范围",
                    ),
                    _build_score_factor(
                        label="公开证据覆盖",
                        score=min(evidence_count, 3) * 8,
                        note=f"命中 {evidence_count} 条可用线索",
                    ),
                    _build_score_factor(
                        label="官方/招采可信度",
                        score=official_hits * 8,
                        note=f"官方或招采证据 {official_hits} 条",
                    ),
                ],
                evidence_links=evidence_links[:3],
                entity_mode="pending",
            )
        )
    if len(pending) < limit and sources:
        relaxed_pool = _dedupe_strings(
            [*seed_companies, *_extract_org_candidates(sources, limit=64, scope_hints=scope_hints), *scope_clients],
            24,
        )
        for name in relaxed_pool:
            name = _resolve_known_org_name(name, scope_hints=scope_hints)
            if len(pending) >= limit or not name or is_duplicate_name(name):
                continue
            if not allow_role_candidate(name, name, require_role_relation=False):
                continue
            related_sources = [source for source in sources if name in _source_text(source)][:2]
            graph_entity = graph_lookup.get(_entity_canonical_key(name))
            graph_source_count = int(getattr(graph_entity, "source_count", 0) or 0) if graph_entity is not None else 0
            has_scope_anchor = any(client and (client in name or name in client) for client in scope_clients)
            if not related_sources and not has_scope_anchor and graph_source_count == 0:
                continue
            if not has_scope_anchor and not any(
                has_explicit_role_relation(name, _source_text(source))
                for source in related_sources
            ):
                continue
            pending.append(
                build_entity_result(
                    name=name,
                    score=28 + min(len(related_sources), 2) * 7,
                    reasoning=_build_fallback_entity_reasoning(
                        output_language=output_language,
                        role=role,
                        evidence_count=max(1, len(related_sources)),
                        scope_regions=scope_regions,
                        scope_industries=scope_industries,
                    ),
                    score_breakdown=[
                        _build_score_factor(
                            label="弱证据补位",
                            score=18,
                            note="仅作为待补证候选，不代表高置信结论",
                        ),
                        _build_score_factor(
                            label="公开线索命中",
                            score=min(len(related_sources), 2) * 7,
                            note=f"命中 {len(related_sources)} 条相关来源",
                        ),
                    ],
                    evidence_links=[_build_entity_evidence(source) for source in related_sources][:2],
                    entity_mode="pending",
                )
            )
    if not results and not pending:
        pending.extend(build_archetype_results()[:limit])
    return results, pending


def build_candidate_profile_support(
    profile_sources: list[SourceDocument],
    candidate_names: Iterable[str],
    *,
    deps: EntityRankingHeuristicDependencies,
) -> dict[str, dict[str, object]]:
    _org_entity_variants = deps.org_entity_variants
    _extract_rank_entity_name = deps.extract_rank_entity_name
    _entity_canonical_key = deps.entity_canonical_key
    _dedupe_strings = deps.dedupe_strings
    _source_mentions_entity = deps.source_mentions_entity
    _source_negates_entity = deps.source_negates_entity
    _build_entity_evidence = deps.build_entity_evidence
    KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS = deps.known_company_public_source_seeds
    COMPANY_PROFILE_PAGE_TOKENS = deps.company_profile_page_tokens

    def company_variants(value: str) -> list[str]:
        normalized = normalize_text(value)
        if not normalized:
            return []
        variants = _org_entity_variants(normalized)
        extracted = _extract_rank_entity_name(normalized)
        if extracted and extracted not in variants:
            variants.extend(_org_entity_variants(extracted))
        canonical = _entity_canonical_key(normalized)
        if canonical and canonical not in variants:
            variants.append(canonical)
        return _dedupe_strings(variants, 6)

    def known_seed_domains(value: str) -> set[str]:
        domains: set[str] = set()
        for variant in company_variants(value):
            for url, _label in KNOWN_COMPANY_PUBLIC_SOURCE_SEEDS.get(variant, ()):
                domain = normalize_text(extract_domain(url) or "").lower()
                if domain:
                    domains.add(domain)
        return domains

    def source_supports_candidate_profile(source: SourceDocument, entity_name: str) -> bool:
        variants = company_variants(entity_name)
        if not variants:
            return False
        for variant in variants:
            if _source_mentions_entity(source, variant) and not _source_negates_entity(source, variant):
                return True
        if source.source_tier != "official":
            return False
        metadata_text = normalize_text(
            " ".join(
                [
                    source.title,
                    source.url,
                    source.source_label or "",
                    source.search_query,
                ]
            )
        ).lower()
        query_text = normalize_text(source.search_query).lower()
        domain = normalize_text(source.domain or "").lower()
        profile_like = any(token in metadata_text for token in COMPANY_PROFILE_PAGE_TOKENS)
        return bool(
            (profile_like or (domain and domain in known_seed_domains(entity_name)))
            and any(variant.lower() in query_text for variant in variants)
        )

    support: dict[str, dict[str, object]] = {}
    normalized_names = [normalize_text(name) for name in candidate_names if normalize_text(name)]
    for name in normalized_names:
        support[name] = {
            "hit_count": 0,
            "official_hit_count": 0,
            "source_labels": [],
            "evidence_links": [],
        }

    for source in profile_sources:
        evidence = _build_entity_evidence(source)
        for name in normalized_names:
            if not source_supports_candidate_profile(source, name):
                continue
            state = support[name]
            state["hit_count"] = int(state["hit_count"]) + 1
            if source.source_tier == "official":
                state["official_hit_count"] = int(state["official_hit_count"]) + 1
            labels = list(state["source_labels"])
            label = normalize_text(source.source_label or source.title or source.domain or "")
            if label and label not in labels:
                labels.append(label)
            state["source_labels"] = labels[:6]
            links = list(state["evidence_links"])
            if evidence.url and not any(item.url == evidence.url for item in links):
                links.append(evidence)
            state["evidence_links"] = links[:3]
    return support


def promote_pending_entities_with_candidate_profiles(
    results: list[ResearchRankedEntityOut],
    pending: list[ResearchRankedEntityOut],
    *,
    candidate_profile_support: dict[str, dict[str, object]],
    limit: int = 3,
) -> tuple[list[ResearchRankedEntityOut], list[ResearchRankedEntityOut]]:
    if not candidate_profile_support:
        return results, pending

    promoted_results = list(results)
    remaining_pending: list[ResearchRankedEntityOut] = []
    used_names = {normalize_text(item.name) for item in promoted_results if normalize_text(item.name)}

    for entity in pending:
        key = normalize_text(entity.name)
        support = candidate_profile_support.get(key)
        hit_count = int((support or {}).get("hit_count", 0) or 0)
        official_hit_count = int((support or {}).get("official_hit_count", 0) or 0)
        if (
            len(promoted_results) < limit
            and support
            and (official_hit_count > 0 or hit_count >= 2)
            and key
            and key not in used_names
        ):
            existing_labels = {
                f"{factor.label}::{factor.note}": factor for factor in entity.score_breakdown
            }
            boost_factor = _build_score_factor(
                label="候选补证命中",
                score=min(18, 8 + official_hit_count * 6 + min(hit_count, 3) * 3),
                note=f"补证公开源 {hit_count} 条，官方源 {official_hit_count} 条",
            )
            existing_labels[f"{boost_factor.label}::{boost_factor.note}"] = boost_factor
            evidence_links = list(entity.evidence_links)
            for evidence in list(support.get("evidence_links", [])):
                if evidence.url and not any(item.url == evidence.url for item in evidence_links):
                    evidence_links.append(evidence)
            promoted_results.append(
                entity.model_copy(
                    update={
                        "entity_mode": "instance",
                        "score": min(100, max(int(entity.score), 58) + int(boost_factor.score)),
                        "reasoning": f"{entity.reasoning} 已补充官网/联系页/团队页公开线索，当前可升级为实例级候选。",
                        "score_breakdown": sorted(
                            existing_labels.values(),
                            key=lambda item: abs(int(item.score)),
                            reverse=True,
                        )[:5],
                        "evidence_links": evidence_links[:3],
                    }
                )
            )
            used_names.add(key)
            continue
        remaining_pending.append(entity)
    return promoted_results[:limit], remaining_pending[:limit]
