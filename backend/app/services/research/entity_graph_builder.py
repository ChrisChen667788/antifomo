from __future__ import annotations

from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from app.schemas.research import (
    ResearchEntityEvidenceOut,
    ResearchEntityGraphOut,
    ResearchNormalizedEntityOut,
)
from app.services.content_extractor import normalize_text
from app.services.research.source_documents import SourceDocument


@dataclass(frozen=True, slots=True)
class EntityGraphBuilderDependencies:
    source_text: Callable[[SourceDocument], str]
    extract_rank_entity_candidates: Callable[..., list[str]]
    canonical_org_name_from_domain: Callable[[str | None], str]
    extract_domain: Callable[[str], str | None]
    resolve_known_org_name: Callable[..., str]
    is_plausible_entity_name: Callable[[str], bool]
    entity_canonical_key: Callable[[str], str]
    org_entity_variants: Callable[..., list[str]]
    org_surface_variants: Callable[[str], tuple[str, ...]]
    build_entity_evidence: Callable[[SourceDocument], ResearchEntityEvidenceOut]


def infer_entity_graph_type(
    name: str,
    text: str,
    *,
    scope_hints: dict[str, object],
) -> str:
    lowered_name = normalize_text(name).lower()
    lowered_text = normalize_text(text).lower()
    scope_clients = [normalize_text(str(item)).lower() for item in scope_hints.get("clients", []) if normalize_text(str(item))]
    target_markers = ("政府", "局", "委", "办", "中心", "医院", "大学", "银行", "学校", "城投", "交投")
    partner_markers = ("咨询", "顾问", "集成", "渠道", "联盟", "研究院", "研究所", "运营商", "总包")
    competitor_markers = ("科技", "信息", "软件", "智能", "数据", "云", "系统", "平台", "通信")

    if any(client and client in lowered_name for client in scope_clients):
        return "target"
    if any(token in lowered_name for token in target_markers) or any(token in lowered_text for token in ("采购", "预算", "招标", "业主", "甲方")):
        return "target"
    if any(token in lowered_name for token in partner_markers) or any(token in lowered_text for token in ("合作伙伴", "联合体", "咨询", "渠道", "生态伙伴", "集成商")):
        return "partner"
    if any(token in lowered_name for token in competitor_markers) or any(token in lowered_text for token in ("中标", "成交", "竞品", "厂商", "平台", "产品", "解决方案")):
        return "competitor"
    return "generic"


def pick_entity_graph_type(existing: str, incoming: str) -> str:
    priority = {"target": 4, "competitor": 3, "partner": 2, "generic": 1}
    return incoming if priority.get(incoming, 0) > priority.get(existing, 0) else existing


def build_entity_graph(
    sources: list[SourceDocument],
    *,
    scope_hints: dict[str, object],
    deps: EntityGraphBuilderDependencies,
) -> ResearchEntityGraphOut:
    graph_state: dict[str, dict[str, object]] = {}
    for source in sources:
        text = deps.source_text(source)
        if not text:
            continue
        candidates = deps.extract_rank_entity_candidates(text, scope_hints=scope_hints)
        domain_canonical = deps.canonical_org_name_from_domain(source.domain or deps.extract_domain(source.url))
        if domain_canonical:
            candidates.append(deps.resolve_known_org_name(domain_canonical, scope_hints=scope_hints, source=source))
        for candidate in candidates:
            raw_name = normalize_text(candidate)
            name = deps.resolve_known_org_name(candidate, scope_hints=scope_hints, source=source)
            if not name or not deps.is_plausible_entity_name(name):
                continue
            key = deps.entity_canonical_key(name)
            role = infer_entity_graph_type(name, text, scope_hints=scope_hints)
            state = graph_state.setdefault(
                key,
                {
                    "canonical_name": name,
                    "entity_type": role,
                    "aliases": set(),
                    "source_urls": set(),
                    "source_tier_counts": Counter(),
                    "evidence_links": [],
                },
            )
            state["entity_type"] = pick_entity_graph_type(str(state["entity_type"]), role)
            aliases = state["aliases"]
            if isinstance(aliases, set):
                aliases.update(deps.org_entity_variants(name, scope_hints=scope_hints))
                if raw_name:
                    aliases.update(deps.org_surface_variants(raw_name))
            canonical_name = normalize_text(str(state["canonical_name"]))
            if len(name) > len(canonical_name):
                state["canonical_name"] = name
            source_urls = state["source_urls"]
            if isinstance(source_urls, set):
                source_urls.add(source.url)
            tier_counts = state["source_tier_counts"]
            if isinstance(tier_counts, Counter):
                tier_counts[source.source_tier or "media"] += 1
            evidence_links = state["evidence_links"]
            if isinstance(evidence_links, list):
                evidence = deps.build_entity_evidence(source)
                if evidence.url and not any(getattr(item, "url", "") == evidence.url for item in evidence_links):
                    evidence_links.append(evidence)

    def materialize(entity_type: str | None = None) -> list[ResearchNormalizedEntityOut]:
        nodes: list[ResearchNormalizedEntityOut] = []
        for state in graph_state.values():
            role = str(state["entity_type"])
            if entity_type and role != entity_type:
                continue
            aliases = sorted(
                [normalize_text(item) for item in state["aliases"] if normalize_text(item)],
                key=len,
                reverse=True,
            )
            canonical = normalize_text(str(state["canonical_name"])) or (aliases[0] if aliases else "")
            if not canonical:
                continue
            urls = state["source_urls"]
            tier_counts = state["source_tier_counts"]
            links = state["evidence_links"]
            nodes.append(
                ResearchNormalizedEntityOut(
                    canonical_name=canonical,
                    entity_type=role if role in {"target", "competitor", "partner", "generic"} else "generic",
                    aliases=aliases[:6],
                    source_count=len(urls) if isinstance(urls, set) else 0,
                    source_tier_counts=dict(tier_counts) if isinstance(tier_counts, Counter) else {},
                    evidence_links=list(links)[:3] if isinstance(links, list) else [],
                )
            )
        return sorted(
            nodes,
            key=lambda item: (-int(item.source_count), -int(item.source_tier_counts.get("official", 0)), item.canonical_name),
        )

    return ResearchEntityGraphOut(
        entities=materialize()[:24],
        target_entities=materialize("target")[:12],
        competitor_entities=materialize("competitor")[:12],
        partner_entities=materialize("partner")[:12],
    )


def entity_graph_lookup(
    graph: ResearchEntityGraphOut,
    *,
    entity_canonical_key: Callable[[str], str],
) -> dict[str, ResearchNormalizedEntityOut]:
    lookup: dict[str, ResearchNormalizedEntityOut] = {}
    for entity in graph.entities:
        keys = [entity.canonical_name, *entity.aliases]
        for key in keys:
            normalized = entity_canonical_key(key)
            if normalized and normalized not in lookup:
                lookup[normalized] = entity
    return lookup
