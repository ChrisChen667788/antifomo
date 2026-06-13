from __future__ import annotations

from datetime import datetime, timezone
import re
from typing import Any

from app.schemas.research import ResearchActionCardOut, ResearchReportDocument, ResearchReportResponse
from app.services.content_extractor import normalize_text
from app.services.delivery.market_intelligence import build_market_intelligence_pack
from app.services.knowledge_intelligence.commercial_text import (
    _clean_commercial_phrase,
    _clean_commercial_rows,
)
from app.services.knowledge_intelligence.entity_quality import (
    _canonicalize_account_name,
    _clean_entity_name,
    _entity_canonical_name,
    _entity_evidence_links,
    _entity_name,
    _entity_reasoning,
    _entity_score,
    _graph_entities_for_role,
    _graph_entity_quality,
    _is_low_signal_entity_name,
    _looks_like_org_name,
    _slugify,
    _unique_strings,
)
from app.services.research_quality_service import build_research_quality_profile
from app.services.research_solution_intelligence_service import build_solution_delivery_pack


def _confidence_score(report: ResearchReportDocument) -> int:
    diagnostics = report.source_diagnostics
    score = 20
    score += min(30, int(report.source_count * 3))
    score += 18 if report.evidence_density == "high" else 10 if report.evidence_density == "medium" else 0
    score += 18 if report.source_quality == "high" else 10 if report.source_quality == "medium" else 0
    score += min(14, int((diagnostics.official_source_ratio or 0) * 30))
    score += min(8, int((diagnostics.unique_domain_count or 0) * 1.5))
    score -= 12 if len(report.top_target_accounts) == 0 and len(report.target_accounts) == 0 else 0
    score -= 8 if len(report.public_contact_channels) == 0 else 0
    return max(5, min(score, 95))


def _confidence_level(score: int) -> str:
    if score >= 78:
        return "high"
    if score >= 56:
        return "medium"
    return "low"


def _budget_probability(report: ResearchReportDocument, *, boost: int = 0) -> int:
    diagnostics = report.source_diagnostics
    probability = 18
    probability += 18 if report.budget_signals else 0
    probability += 14 if report.tender_timeline else 0
    probability += 10 if report.target_departments else 0
    probability += 10 if report.public_contact_channels else 0
    probability += 8 if diagnostics.official_source_ratio >= 0.25 else 3 if diagnostics.official_source_ratio > 0 else 0
    probability += 8 if report.evidence_density == "high" else 4 if report.evidence_density == "medium" else 0
    probability += 6 if report.source_quality == "high" else 3 if report.source_quality == "medium" else 0
    probability += boost
    return max(10, min(probability, 92))


def _maturity_stage(report: ResearchReportDocument) -> str:
    score = 0
    score += 1 if report.strategic_directions else 0
    score += 1 if report.target_departments else 0
    score += 1 if report.budget_signals else 0
    score += 1 if report.tender_timeline else 0
    score += 1 if report.public_contact_channels else 0
    if score >= 5:
        return "scaling"
    if score >= 3:
        return "piloting"
    if score >= 2:
        return "discovering"
    return "early"


def _maturity_dimensions(report: ResearchReportDocument) -> list[dict[str, str]]:
    return [
        {
            "name": "需求清晰度",
            "level": "high" if report.strategic_directions else "medium" if report.executive_summary else "low",
            "note": report.strategic_directions[0] if report.strategic_directions else "当前仍需进一步确认核心场景与目标。",
        },
        {
            "name": "预算与采购",
            "level": "high" if report.budget_signals and report.tender_timeline else "medium" if (report.budget_signals or report.tender_timeline) else "low",
            "note": (report.budget_signals + report.tender_timeline)[0]
            if (report.budget_signals or report.tender_timeline)
            else "尚未形成明确预算窗口或采购节奏。",
        },
        {
            "name": "组织进入度",
            "level": "high" if report.target_departments and report.public_contact_channels else "medium" if (report.target_departments or report.public_contact_channels) else "low",
            "note": (report.target_departments + report.public_contact_channels)[0]
            if (report.target_departments or report.public_contact_channels)
            else "仍缺少明确部门和公开联系入口。",
        },
        {
            "name": "生态成熟度",
            "level": "high" if report.ecosystem_partners else "medium" if report.benchmark_cases else "low",
            "note": (report.ecosystem_partners + report.benchmark_cases)[0]
            if (report.ecosystem_partners or report.benchmark_cases)
            else "当前生态伙伴与标杆案例仍偏少。",
        },
    ]


def _build_methodology(report: ResearchReportDocument) -> dict[str, Any]:
    diagnostics = report.source_diagnostics
    scope_bits = _unique_strings(
        [
            report.keyword,
            report.research_focus or "",
            diagnostics.strategy_scope_summary or "",
            " / ".join(diagnostics.scope_regions),
            " / ".join(diagnostics.scope_industries),
        ],
        limit=4,
    )
    return {
        "scope_summary": "；".join(scope_bits),
        "pipeline_summary": diagnostics.pipeline_summary
        or "取数 -> 清洗 -> 分析",
        "query_plan": list(report.query_plan[:6]),
        "data_boundary": "仅使用公开网页、公告、政策、新闻、企业官网与公开披露数据；付费库和未授权后台不纳入。",
        "retained_source_count": diagnostics.retained_source_count or report.source_count,
        "unique_domain_count": diagnostics.unique_domain_count or len({item.domain for item in report.sources if item.domain}),
        "matched_source_labels": list(diagnostics.matched_source_labels[:6]),
        "matched_theme_labels": list(diagnostics.matched_theme_labels[:6]),
    }


def _build_confidence(report: ResearchReportDocument) -> dict[str, Any]:
    diagnostics = report.source_diagnostics
    score = _confidence_score(report)
    reasons = _unique_strings(
        [
            f"来源数 {report.source_count}，覆盖 {diagnostics.unique_domain_count or len({item.domain for item in report.sources if item.domain})} 个域名。",
            f"官方源占比 {round((diagnostics.official_source_ratio or 0) * 100)}%。",
            "已有预算/招采线索。" if report.budget_signals else "",
            "已识别部门与公开联系入口。" if report.target_departments or report.public_contact_channels else "",
            diagnostics.pipeline_summary,
        ],
        limit=5,
    )
    concerns = _unique_strings(
        [
            "目标账户仍不足，结果更适合做候选名单而非直接推进。" if not report.top_target_accounts and not report.target_accounts else "",
            "公开联系入口不足，销售落地仍需补采。"
            if not report.public_contact_channels
            else "",
            "官方源占比偏低，建议继续补证。"
            if diagnostics.official_source_ratio < 0.2
            else "",
            "证据密度仍偏弱。"
            if report.evidence_density == "low"
            else "",
        ],
        limit=5,
    )
    return {
        "level": _confidence_level(score),
        "score": score,
        "source_count": report.source_count,
        "official_source_ratio": diagnostics.official_source_ratio,
        "evidence_density": report.evidence_density,
        "source_quality": report.source_quality,
        "reasons": reasons,
        "concerns": concerns,
    }


def _build_coverage_gaps(report: ResearchReportDocument) -> list[dict[str, str]]:
    diagnostics = report.source_diagnostics
    gaps: list[dict[str, str]] = []
    if report.source_count < 4:
        gaps.append(
            {
                "title": "来源覆盖不足",
                "severity": "high",
                "detail": "当前可用来源偏少，报告更适合作为问题定义而非最终判断。",
                "recommended_action": "继续补行业媒体、公告、企业官网和政策源，至少补到 6-8 条有效来源。",
            }
        )
    if diagnostics.official_source_ratio < 0.2:
        gaps.append(
            {
                "title": "官方源偏少",
                "severity": "medium",
                "detail": "当前官方源占比不足，容易让预算和组织判断失真。",
                "recommended_action": "优先补官网、公告、政策、投资者关系或招采来源。",
            }
        )
    if not report.top_target_accounts and not report.target_accounts:
        gaps.append(
            {
                "title": "甲方对象不够具体",
                "severity": "high",
                "detail": "当前还没有稳定的具体甲方对象，商业动作容易泛化。",
                "recommended_action": "先把行业判断拆成具体公司、机构或园区，再生成行动卡。",
            }
        )
    if not report.public_contact_channels:
        gaps.append(
            {
                "title": "缺少公开触达入口",
                "severity": "medium",
                "detail": "即使方向正确，也还不能直接进入外联或建联阶段。",
                "recommended_action": "补官网联系我们、采购联系人、IR 邮箱或公开渠道负责人。",
            }
        )
    if not report.benchmark_cases:
        gaps.append(
            {
                "title": "缺少标杆案例",
                "severity": "low",
                "detail": "缺少可对标案例时，客户教育和方案说服力会下降。",
                "recommended_action": "补同类平台、同区域或同场景的落地案例与生态打法。",
            }
        )
    return gaps[:4]


def _match_action_cards_for_account(
    account_name: str,
    action_cards: list[ResearchActionCardOut],
) -> list[ResearchActionCardOut]:
    normalized_name = normalize_text(account_name)
    direct_matches = [
        card
        for card in action_cards
        if normalized_name and (
            normalized_name in normalize_text(card.title)
            or normalized_name in normalize_text(card.summary)
            or any(normalized_name in normalize_text(step) for step in card.recommended_steps)
        )
    ]
    return direct_matches or action_cards[:2]


def _fallback_entities(values: list[str], role: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    base_score = {"target": 66, "competitor": 61, "partner": 58}.get(role, 56)
    for index, value in enumerate(_unique_strings(values, limit=3)):
        items.append(
            {
                "name": value,
                "score": max(40, base_score - index * 7),
                "reasoning": "当前主要基于显性主题命中与检索候选生成，仍建议继续补更多正式证据。",
                "evidence_links": [],
            }
        )
    return items


def _graph_candidate_entities(report: ResearchReportDocument, role: str) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    for entity in _graph_entities_for_role(report, role):
        canonical_name = _entity_canonical_name(entity)
        if not canonical_name or _is_low_signal_entity_name(canonical_name):
            continue
        source_tier_counts = (entity.get("source_tier_counts") if isinstance(entity, dict) else getattr(entity, "source_tier_counts", {})) or {}
        source_count = int((entity.get("source_count") if isinstance(entity, dict) else getattr(entity, "source_count", 0)) or 0)
        official_hits = int(source_tier_counts.get("official") or 0)
        candidates.append(
            {
                "name": canonical_name,
                "score": max(42, min(98, _graph_entity_quality(entity))),
                "reasoning": f"实体归一后命中 {source_count} 条来源，其中官方源 {official_hits} 条。",
                "evidence_links": [link.model_dump(mode="json") for link in getattr(entity, "evidence_links", [])[:4]],
            }
        )
    candidates.sort(key=lambda item: int(item.get("score") or 0), reverse=True)
    return candidates[:6]


def _build_account_snapshots(
    report: ResearchReportDocument,
    action_cards: list[ResearchActionCardOut],
) -> list[dict[str, Any]]:
    targets = [*_graph_candidate_entities(report, "target"), *(report.top_target_accounts or _fallback_entities(report.target_accounts, "target"))]
    competitors = [*_graph_candidate_entities(report, "competitor"), *(report.top_competitors or _fallback_entities(report.competitor_profiles, "competitor"))]
    partners = [*_graph_candidate_entities(report, "partner"), *(report.top_ecosystem_partners or _fallback_entities(report.ecosystem_partners, "partner"))]
    items: list[dict[str, Any]] = []

    for role, source_entities in (("target", targets), ("competitor", competitors[:2]), ("partner", partners[:2])):
        role_items: dict[str, dict[str, Any]] = {}
        for entity in source_entities[:8]:
            evidence_links = _entity_evidence_links(entity)
            name = _canonicalize_account_name(
                _entity_name(entity),
                report=report,
                role=role,
                evidence_links=evidence_links,
            )
            if _is_low_signal_entity_name(name):
                continue
            entity_score = _entity_score(entity)
            matched_cards = _match_action_cards_for_account(name, action_cards)
            slug = _slugify(name)
            candidate = {
                "slug": slug,
                "name": name,
                "role": role,
                "priority": "high" if entity_score >= 75 else "medium" if entity_score >= 55 else "low",
                "confidence_score": max(35, min(95, entity_score if entity_score else _confidence_score(report))),
                "summary": _entity_reasoning(entity)
                or f"{name} 当前已进入 {report.keyword} 的重点观察名单，适合继续做账户拆解与商机验证。",
                "why_now": _clean_commercial_rows(
                    [
                        *(report.budget_signals[:1] if role == "target" else []),
                        *(report.tender_timeline[:1] if role == "target" else []),
                        *(report.client_peer_moves[:1] if role == "target" else []),
                        _entity_reasoning(entity),
                    ],
                    limit=3,
                ),
                "departments": list(report.target_departments[:4]) if role == "target" else [],
                "contacts": list(report.public_contact_channels[:3]) if role == "target" else [],
                "signals": _clean_commercial_rows(
                    [
                        *(report.account_team_signals[:2] if role == "target" else []),
                        *(report.competition_analysis[:1] if role == "competitor" else []),
                        *(report.ecosystem_partners[:1] if role == "partner" else []),
                    ],
                    limit=3,
                ),
                "benchmark_cases": _clean_commercial_rows(report.benchmark_cases[:3], limit=3, max_length=56),
                "next_best_action": _clean_commercial_phrase(matched_cards[0].recommended_steps[0], max_clauses=1, max_length=68)
                if matched_cards and matched_cards[0].recommended_steps
                else "先补组织、预算与联系人，再决定是否进入深入方案阶段。",
                "maturity_stage": _maturity_stage(report),
                "budget_probability": _budget_probability(report, boost=4 if role == "target" else -8),
                "evidence_links": evidence_links,
            }
            existing = role_items.get(slug)
            if existing is None:
                role_items[slug] = candidate
                continue
            existing["confidence_score"] = max(existing["confidence_score"], candidate["confidence_score"])
            existing["budget_probability"] = max(existing["budget_probability"], candidate["budget_probability"])
            existing["priority"] = "high" if existing["confidence_score"] >= 75 else "medium" if existing["confidence_score"] >= 55 else "low"
            existing["why_now"] = _unique_strings([*existing["why_now"], *candidate["why_now"]], limit=4)
            existing["signals"] = _unique_strings([*existing["signals"], *candidate["signals"]], limit=4)
            existing["benchmark_cases"] = _unique_strings([*existing["benchmark_cases"], *candidate["benchmark_cases"]], limit=4)
            existing["contacts"] = _unique_strings([*existing["contacts"], *candidate["contacts"]], limit=4)
            existing["departments"] = _unique_strings([*existing["departments"], *candidate["departments"]], limit=4)
            existing["evidence_links"] = existing["evidence_links"] or candidate["evidence_links"]
        items.extend(
            sorted(
                role_items.values(),
                key=lambda item: (int(item["confidence_score"]), int(item["budget_probability"])),
                reverse=True,
            )[:3]
        )
    return items


def _opportunity_identity_key(opportunity: dict[str, Any]) -> str:
    account_slug = _slugify(str(opportunity.get("account_slug") or opportunity.get("account_name") or ""))
    title = normalize_text(str(opportunity.get("title") or ""))
    title = re.sub(r"^[^｜|]+[｜|]", "", title)
    title = re.sub(r"20\d{2}年?", "", title)
    title = title.replace("进入窗口", "").strip(" |-")
    action = normalize_text(str(opportunity.get("next_best_action") or ""))
    return "|".join(
        [
            account_slug,
            _slugify(title[:40]),
            _slugify(action[:48] or normalize_text(str(opportunity.get("entry_window") or ""))[:32]),
        ]
    )


def _build_opportunities(
    report: ResearchReportDocument,
    accounts: list[dict[str, Any]],
    action_cards: list[ResearchActionCardOut],
) -> list[dict[str, Any]]:
    opportunities: dict[str, dict[str, Any]] = {}
    entry_window = report.tender_timeline[0] if report.tender_timeline else "未来 1-2 个季度内建议持续观察预算与招采窗口。"
    benchmark_case = report.benchmark_cases[0] if report.benchmark_cases else ""
    risk_flags = _unique_strings(
        [
            "官方源不足" if report.source_diagnostics.official_source_ratio < 0.2 else "",
            "缺少公开联系人" if not report.public_contact_channels else "",
            "预算窗口仍需验证" if not report.budget_signals else "",
        ],
        limit=3,
    )
    for account in [item for item in accounts if item["role"] == "target"][:3]:
        matched_cards = _match_action_cards_for_account(account["name"], action_cards)
        score = max(42, min(96, int(account["confidence_score"] * 0.55 + account["budget_probability"] * 0.45)))
        opportunity = {
            "title": f"{account['name']}｜{report.keyword[:18]} 进入窗口",
            "account_slug": account["slug"],
            "account_name": account["name"],
            "stage": _maturity_stage(report),
            "score": score,
            "confidence_label": "高把握" if score >= 75 else "中等把握" if score >= 55 else "待验证",
            "budget_probability": account["budget_probability"],
            "entry_window": _clean_commercial_phrase(entry_window, max_clauses=1, max_length=64),
            "next_best_action": _clean_commercial_phrase(str(account["next_best_action"] or ""), max_clauses=1, max_length=68),
            "why_now": _clean_commercial_rows(account["why_now"] + report.strategic_directions[:1], limit=3, max_length=64),
            "risk_flags": risk_flags,
            "benchmark_case": _clean_commercial_phrase(benchmark_case, max_clauses=1, max_length=56),
            "related_action_titles": [card.title for card in matched_cards[:2]],
        }
        opportunities[_opportunity_identity_key(opportunity)] = opportunity
    return list(opportunities.values())


def _build_benchmark_card(report: ResearchReportDocument) -> dict[str, Any]:
    cases = _unique_strings(report.benchmark_cases, limit=4)
    comparators = _unique_strings(report.flagship_products + report.winner_peer_moves, limit=4)
    if cases:
        summary = f"当前已抽取 {len(cases)} 条可对标案例，可用于客户教育、方案说服和竞品对照。"
    else:
        summary = "当前标杆案例仍偏少，建议补充同区域、同类型或同采购路径的成功样本。"
    return {
        "summary": summary,
        "cases": cases,
        "comparators": comparators,
    }


def _build_maturity_assessment(report: ResearchReportDocument) -> dict[str, Any]:
    dimensions = _maturity_dimensions(report)
    score = sum(18 if item["level"] == "high" else 11 if item["level"] == "medium" else 5 for item in dimensions)
    return {
        "stage": _maturity_stage(report),
        "score": min(score, 92),
        "summary": "从需求清晰度、预算采购、组织进入度和生态成熟度四个维度评估当前商机成熟度。",
        "dimensions": dimensions,
    }


def build_report_knowledge_intelligence(
    report: ResearchReportDocument,
    *,
    action_cards: list[ResearchActionCardOut] | None = None,
) -> dict[str, Any]:
    cards = list(action_cards or [])
    accounts = _build_account_snapshots(report, cards)
    opportunities = _build_opportunities(report, accounts, cards)
    benchmark = _build_benchmark_card(report)
    maturity = _build_maturity_assessment(report)
    return {
        "schema_version": 10,
        "methodology": _build_methodology(report),
        "confidence": _build_confidence(report),
        "coverage_gaps": _build_coverage_gaps(report),
        "accounts": accounts,
        "opportunities": opportunities,
        "benchmark": benchmark,
        "maturity": maturity,
        "why_now": _unique_strings(
            [
                *(report.budget_signals[:2]),
                *(report.tender_timeline[:1]),
                *(report.client_peer_moves[:1]),
                *(report.strategic_directions[:1]),
            ],
            limit=4,
        ),
        "next_steps": _unique_strings(
            [
                *(cards[0].recommended_steps[:2] if cards else []),
                "把高价值甲方、预算窗口和联系人回写到账户页，形成连续跟踪。",
                "对高风险结论补官方源与标杆案例，再进入方案设计。",
            ],
            limit=4,
        ),
    }


def _coerce_research_report_response(report: ResearchReportDocument) -> ResearchReportResponse:
    if isinstance(report, ResearchReportResponse):
        return report
    payload = report.model_dump(mode="python")
    payload["generated_at"] = payload.get("generated_at") or getattr(report, "generated_at", None) or datetime.now(timezone.utc)
    return ResearchReportResponse.model_validate(payload)


def _enrich_report_for_knowledge_metadata(report: ResearchReportDocument) -> ResearchReportResponse:
    base_report = _coerce_research_report_response(report)
    try:
        return base_report.model_copy(
            update={
                "market_intelligence": build_market_intelligence_pack(base_report),
                "solution_delivery_pack": build_solution_delivery_pack(base_report),
                "quality_profile": build_research_quality_profile(base_report),
            }
        )
    except Exception:
        return base_report


def _clean_backfill_canonical_entity_name(value: str) -> str:
    normalized = _clean_entity_name(value)
    for suffix in ("集团官网", "官网首页", "官网"):
        if normalized.endswith(suffix):
            candidate = _clean_entity_name(normalized[: -len(suffix)])
            if candidate and _looks_like_org_name(candidate) and not _is_low_signal_entity_name(candidate):
                return candidate
    return normalized


def _canonicalized_ranked_entities(
    rows: list[Any],
    *,
    report: ResearchReportDocument,
    role: str,
) -> tuple[list[Any], dict[str, str]]:
    updated: list[Any] = []
    aliases: dict[str, str] = {}
    for row in rows:
        raw_name = _entity_name(row)
        canonical_name = _canonicalize_account_name(
            raw_name,
            report=report,
            role=role,
            evidence_links=_entity_evidence_links(row),
        ) or raw_name
        canonical_name = _clean_backfill_canonical_entity_name(canonical_name)
        if raw_name and canonical_name and raw_name != canonical_name:
            aliases[raw_name] = canonical_name
        if hasattr(row, "model_copy"):
            updated.append(row.model_copy(update={"name": canonical_name}))
        elif isinstance(row, dict):
            next_row = dict(row)
            next_row["name"] = canonical_name
            updated.append(next_row)
        else:
            updated.append(row)
    return updated, aliases


def _canonicalized_entity_names(
    values: list[str],
    *,
    report: ResearchReportDocument,
    role: str,
    aliases: dict[str, str],
    limit: int = 8,
) -> list[str]:
    rows: list[str] = []
    for value in values:
        normalized = normalize_text(value)
        if not normalized:
            continue
        rows.append(
            _clean_backfill_canonical_entity_name(
                aliases.get(normalized)
                or _canonicalize_account_name(normalized, report=report, role=role)
                or normalized
            )
        )
    return _unique_strings(rows, limit=limit)


def _canonicalize_report_for_knowledge_backfill(report: ResearchReportResponse) -> ResearchReportResponse:
    top_targets, target_aliases = _canonicalized_ranked_entities(
        list(report.top_target_accounts),
        report=report,
        role="target",
    )
    pending_targets, pending_target_aliases = _canonicalized_ranked_entities(
        list(report.pending_target_candidates),
        report=report,
        role="target",
    )
    target_aliases.update(pending_target_aliases)
    top_competitors, competitor_aliases = _canonicalized_ranked_entities(
        list(report.top_competitors),
        report=report,
        role="competitor",
    )
    pending_competitors, pending_competitor_aliases = _canonicalized_ranked_entities(
        list(report.pending_competitor_candidates),
        report=report,
        role="competitor",
    )
    competitor_aliases.update(pending_competitor_aliases)
    top_partners, partner_aliases = _canonicalized_ranked_entities(
        list(report.top_ecosystem_partners),
        report=report,
        role="partner",
    )
    pending_partners, pending_partner_aliases = _canonicalized_ranked_entities(
        list(report.pending_partner_candidates),
        report=report,
        role="partner",
    )
    partner_aliases.update(pending_partner_aliases)
    diagnostics = report.source_diagnostics.model_copy(
        update={
            "scope_clients": _canonicalized_entity_names(
                list(report.source_diagnostics.scope_clients),
                report=report,
                role="target",
                aliases=target_aliases,
                limit=6,
            ),
            "candidate_profile_companies": _canonicalized_entity_names(
                list(report.source_diagnostics.candidate_profile_companies),
                report=report,
                role="partner",
                aliases={**target_aliases, **competitor_aliases, **partner_aliases},
                limit=6,
            ),
        }
    )
    return report.model_copy(
        update={
            "target_accounts": _canonicalized_entity_names(
                list(report.target_accounts),
                report=report,
                role="target",
                aliases=target_aliases,
                limit=8,
            ),
            "competitor_profiles": _canonicalized_entity_names(
                list(report.competitor_profiles),
                report=report,
                role="competitor",
                aliases=competitor_aliases,
                limit=8,
            ),
            "ecosystem_partners": _canonicalized_entity_names(
                list(report.ecosystem_partners),
                report=report,
                role="partner",
                aliases=partner_aliases,
                limit=8,
            ),
            "top_target_accounts": top_targets,
            "pending_target_candidates": pending_targets,
            "top_competitors": top_competitors,
            "pending_competitor_candidates": pending_competitors,
            "top_ecosystem_partners": top_partners,
            "pending_partner_candidates": pending_partners,
            "source_diagnostics": diagnostics,
        }
    )


def build_research_report_metadata(
    report: ResearchReportDocument,
    *,
    action_cards: list[ResearchActionCardOut] | None = None,
    tracking_topic_id: str | None = None,
) -> dict[str, Any]:
    cards = list(action_cards or [])
    enriched_report = _enrich_report_for_knowledge_metadata(report)
    payload: dict[str, Any] = {
        "kind": "research_report",
        "report": enriched_report.model_dump(mode="json"),
        "action_cards": [card.model_dump(mode="json") for card in cards],
        "commercial_intelligence": build_report_knowledge_intelligence(enriched_report, action_cards=cards),
    }
    if tracking_topic_id:
        payload["tracking_topic_id"] = tracking_topic_id
    return payload


def _normalize_review_queue_resolutions(payload: dict[str, Any] | None) -> dict[str, dict[str, Any]]:
    if not isinstance(payload, dict):
        return {}
    raw = payload.get("review_queue_resolutions")
    if not isinstance(raw, dict):
        return {}
    normalized: dict[str, dict[str, Any]] = {}
    for review_id, resolution in raw.items():
        if not isinstance(review_id, str) or not isinstance(resolution, dict):
            continue
        status = normalize_text(str(resolution.get("resolution_status") or "open")).lower()
        if status not in {"open", "resolved", "deferred"}:
            status = "open"
        resolved_at = resolution.get("resolved_at")
        normalized[review_id] = {
            "resolution_status": status,
            "resolution_note": normalize_text(str(resolution.get("resolution_note") or "")),
            "resolved_at": resolved_at if isinstance(resolved_at, str) and resolved_at else None,
        }
    return normalized


def apply_review_queue_resolutions(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return payload
    report_payload = payload.get("report")
    if not isinstance(report_payload, dict):
        return payload
    raw_queue = report_payload.get("review_queue")
    if not isinstance(raw_queue, list):
        return payload

    resolutions = _normalize_review_queue_resolutions(payload)
    updated_queue: list[dict[str, Any]] = []
    for raw_item in raw_queue:
        if not isinstance(raw_item, dict):
            continue
        review_id = normalize_text(str(raw_item.get("id") or ""))
        resolution = resolutions.get(review_id, {})
        updated_item = dict(raw_item)
        updated_item["resolution_status"] = resolution.get("resolution_status") or "open"
        updated_item["resolution_note"] = resolution.get("resolution_note") or ""
        updated_item["resolved_at"] = resolution.get("resolved_at")
        updated_queue.append(updated_item)

    cloned_payload = dict(payload)
    cloned_report = dict(report_payload)
    cloned_report["review_queue"] = updated_queue
    cloned_payload["report"] = cloned_report
    return cloned_payload


def update_review_queue_resolution(
    payload: dict[str, Any] | None,
    *,
    review_id: str,
    action: str,
    note: str | None = None,
) -> dict[str, Any]:
    cloned_payload = dict(payload) if isinstance(payload, dict) else {}
    normalized_id = normalize_text(review_id)
    if not normalized_id:
        return cloned_payload

    resolutions = _normalize_review_queue_resolutions(cloned_payload)
    normalized_action = normalize_text(action).lower()
    if normalized_action not in {"open", "resolved", "deferred"}:
        normalized_action = "open"

    if normalized_action == "open":
        resolutions.pop(normalized_id, None)
    else:
        resolutions[normalized_id] = {
            "resolution_status": normalized_action,
            "resolution_note": normalize_text(note or ""),
            "resolved_at": datetime.now(timezone.utc).isoformat() if normalized_action == "resolved" else None,
        }

    if resolutions:
        cloned_payload["review_queue_resolutions"] = resolutions
    else:
        cloned_payload.pop("review_queue_resolutions", None)
    return apply_review_queue_resolutions(cloned_payload) or cloned_payload


def extract_commercial_intelligence(payload: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    intelligence = payload.get("commercial_intelligence")
    if isinstance(intelligence, dict):
        return intelligence
    return None
