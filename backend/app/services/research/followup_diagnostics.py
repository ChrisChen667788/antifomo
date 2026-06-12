from __future__ import annotations

from collections.abc import Callable, Collection, Iterable
from dataclasses import dataclass
import re
from typing import Pattern

from app.schemas.research import (
    ResearchFollowupContextOut,
    ResearchFollowupDiagnosticsOut,
    ResearchFollowupSectionImpactOut,
    ResearchReportDocument,
    ResearchReportRequest,
    ResearchReportResponse,
)
from app.services.content_extractor import normalize_text


@dataclass(frozen=True, slots=True)
class FollowupDiagnosticsDependencies:
    truncate_text: Callable[[str, int], str]
    sanitize_research_focus_text: Callable[[str | None], str]
    looks_like_source_noise_segment: Callable[..., bool]
    merge_scope_hints: Callable[[dict[str, object], dict[str, object]], dict[str, object]]
    dedupe_strings: Callable[[Iterable[str], int], list[str]]
    prune_industry_hints: Callable[[list[str]], list[str]]
    infer_input_scope_hints: Callable[..., dict[str, object]]
    theme_labels_from_scope: Callable[..., list[str]]
    clean_scope_entity_names: Callable[..., list[str]]
    build_query_plan: Callable[..., list[str]]
    extract_topic_anchor_terms: Callable[[str, str | None], list[str]]
    tokenize_for_match: Callable[..., list[str]]
    generic_focus_tokens: Collection[str]
    org_pattern: Pattern[str]


@dataclass(frozen=True, slots=True)
class FollowupImpactDependencies:
    looks_like_source_noise_segment: Callable[..., bool]
    dedupe_strings: Callable[[Iterable[str], int], list[str]]
    tokenize_for_match: Callable[..., list[str]]
    generic_focus_tokens: Collection[str]


def build_followup_context(payload: ResearchReportRequest, *, deps: FollowupDiagnosticsDependencies) -> ResearchFollowupContextOut:
    return ResearchFollowupContextOut(
        followup_report_title=normalize_text(payload.followup_report_title or ""),
        followup_report_summary=deps.truncate_text(normalize_text(payload.followup_report_summary or ""), 1200),
        supplemental_context=deps.truncate_text(normalize_text(payload.supplemental_context or ""), 1800),
        supplemental_evidence=deps.truncate_text(normalize_text(payload.supplemental_evidence or ""), 2200),
        supplemental_requirements=deps.truncate_text(normalize_text(payload.supplemental_requirements or ""), 1600),
    )


def build_followup_planning_focus(
    research_focus: str | None,
    *,
    followup_context: ResearchFollowupContextOut,
    deps: FollowupDiagnosticsDependencies,
) -> str | None:
    parts = [
        normalize_text(research_focus or ""),
        normalize_text(followup_context.supplemental_requirements or ""),
        normalize_text(followup_context.supplemental_context or ""),
        deps.truncate_text(normalize_text(followup_context.supplemental_evidence or ""), 240),
    ]
    merged = "；".join(part for part in parts if part)
    return deps.sanitize_research_focus_text(merged) or None


def followup_context_sections(followup_context: ResearchFollowupContextOut) -> list[tuple[str, str]]:
    sections = [
        ("上一版执行摘要", normalize_text(followup_context.followup_report_summary or "")),
        ("人工补充新需求", normalize_text(followup_context.supplemental_requirements or "")),
        ("人工补充新信息", normalize_text(followup_context.supplemental_context or "")),
        ("人工补充新证据/待核验线索", normalize_text(followup_context.supplemental_evidence or "")),
    ]
    return [(label, value) for label, value in sections if value]


def split_followup_research_segments(
    value: str,
    *,
    limit: int,
    deps: FollowupDiagnosticsDependencies,
) -> list[str]:
    segments: list[str] = []
    for raw in re.split(r"[；;。！？!?、\n]+", value):
        normalized = normalize_text(raw.strip("：:，, "))
        if not normalized or len(normalized) < 4:
            continue
        if deps.looks_like_source_noise_segment(normalized, raw_value=raw):
            continue
        if normalized in segments:
            continue
        segments.append(normalized)
        if len(segments) >= limit:
            break
    return segments


def merge_scope_hints_with_followup_context(
    base: dict[str, object],
    followup: dict[str, object],
    *,
    deps: FollowupDiagnosticsDependencies,
) -> dict[str, object]:
    if not followup:
        return dict(base)
    merged = deps.merge_scope_hints(base, followup)
    followup_regions = [normalize_text(str(item)) for item in followup.get("regions", []) or [] if normalize_text(str(item))]
    followup_industries = [normalize_text(str(item)) for item in followup.get("industries", []) or [] if normalize_text(str(item))]
    followup_clients = [normalize_text(str(item)) for item in followup.get("clients", []) or [] if normalize_text(str(item))]
    followup_company_anchors = [
        normalize_text(str(item))
        for item in followup.get("company_anchors", []) or []
        if normalize_text(str(item))
    ]
    if followup_regions:
        merged["regions"] = deps.dedupe_strings([*followup_regions, *(merged.get("regions", []) or [])], 4)
    if followup_industries:
        merged["industries"] = deps.prune_industry_hints([*followup_industries, *(merged.get("industries", []) or [])])
    if followup_clients:
        merged["clients"] = deps.dedupe_strings([*followup_clients, *(merged.get("clients", []) or [])], 4)
    if followup_company_anchors:
        merged["company_anchors"] = deps.dedupe_strings([*followup_company_anchors, *(merged.get("company_anchors", []) or [])], 6)
    merged["strategy_must_include_terms"] = deps.dedupe_strings(
        [
            *(followup.get("strategy_must_include_terms", []) or []),
            *(merged.get("strategy_must_include_terms", []) or []),
        ],
        10,
    )
    merged["strategy_exclusion_terms"] = deps.dedupe_strings(
        [
            *(followup.get("strategy_exclusion_terms", []) or []),
            *(merged.get("strategy_exclusion_terms", []) or []),
        ],
        10,
    )
    merged["strategy_query_expansions"] = deps.dedupe_strings(
        [
            *(followup.get("strategy_query_expansions", []) or []),
            *(merged.get("strategy_query_expansions", []) or []),
        ],
        12,
    )
    anchor_segments = [
        *[normalize_text(str(item)) for item in merged.get("regions", []) or [] if normalize_text(str(item))][:2],
        *[normalize_text(str(item)) for item in merged.get("industries", []) or [] if normalize_text(str(item))][:2],
        *[normalize_text(str(item)) for item in merged.get("clients", []) or [] if normalize_text(str(item))][:2],
    ]
    merged["anchor_text"] = normalize_text(" / ".join(anchor_segments)) or normalize_text(
        str(followup.get("anchor_text", ""))
    ) or normalize_text(str(base.get("anchor_text", "")))
    if normalize_text(str(followup.get("strategy_scope_summary", ""))):
        merged["strategy_scope_summary"] = normalize_text(str(followup.get("strategy_scope_summary", "")))
    return merged


def build_followup_research_diagnostics(
    *,
    keyword: str,
    report_research_focus: str | None,
    followup_context: ResearchFollowupContextOut,
    include_wechat: bool,
    base_scope_hints: dict[str, object],
    deps: FollowupDiagnosticsDependencies,
) -> tuple[dict[str, object], ResearchFollowupDiagnosticsOut]:
    sections = followup_context_sections(followup_context)
    if not sections:
        return {}, ResearchFollowupDiagnosticsOut()

    planning_focus = build_followup_planning_focus(
        report_research_focus,
        followup_context=followup_context,
        deps=deps,
    ) or normalize_text(report_research_focus or "")
    signal_text = "；".join(
        value
        for value in [
            normalize_text(followup_context.supplemental_requirements or ""),
            normalize_text(followup_context.supplemental_context or ""),
            deps.truncate_text(normalize_text(followup_context.supplemental_evidence or ""), 900),
        ]
        if value
    )
    inferred_scope_hints = deps.infer_input_scope_hints(keyword, signal_text or planning_focus)
    theme_labels = deps.theme_labels_from_scope(
        base_scope_hints,
        keyword=keyword,
        research_focus=planning_focus or report_research_focus,
    )
    cleaned_entities = deps.clean_scope_entity_names(
        [
            *(normalize_text(str(item)) for item in inferred_scope_hints.get("clients", []) or [] if normalize_text(str(item))),
            *(normalize_text(str(item)) for item in inferred_scope_hints.get("company_anchors", []) or [] if normalize_text(str(item))),
            *(normalize_text(match) for match in deps.org_pattern.findall(signal_text) if normalize_text(match)),
        ],
        limit=6,
        theme_labels=theme_labels,
    )
    if cleaned_entities:
        inferred_scope_hints["clients"] = deps.dedupe_strings(cleaned_entities, 4)
        inferred_scope_hints["company_anchors"] = deps.dedupe_strings(
            [
                *cleaned_entities,
                *(normalize_text(str(item)) for item in inferred_scope_hints.get("company_anchors", []) or [] if normalize_text(str(item))),
            ],
            6,
        )

    segment_candidates: list[str] = []
    for label, value in sections:
        per_section_limit = 2 if "证据" in label or "需求" in label else 1
        segment_candidates.extend(split_followup_research_segments(value, limit=per_section_limit, deps=deps))
    segment_candidates = deps.dedupe_strings(segment_candidates, 5)

    rebuilt_scope_hints = merge_scope_hints_with_followup_context(base_scope_hints, inferred_scope_hints, deps=deps)

    decomposition_queries: list[str] = []
    if planning_focus:
        decomposition_queries.extend(
            deps.build_query_plan(
                keyword,
                planning_focus,
                include_wechat=False,
                scope_hints=rebuilt_scope_hints,
                limit=4,
            )[:3]
        )
    for segment in segment_candidates:
        segment_scope_hints = merge_scope_hints_with_followup_context(
            rebuilt_scope_hints,
            deps.infer_input_scope_hints(keyword, segment),
            deps=deps,
        )
        decomposition_queries.extend(
            deps.build_query_plan(
                keyword,
                segment,
                include_wechat=False,
                scope_hints=segment_scope_hints,
                limit=4,
            )[:2]
        )
    if include_wechat and rebuilt_scope_hints.get("clients"):
        primary_client = normalize_text(str((rebuilt_scope_hints.get("clients") or [""])[0]))
        if primary_client:
            decomposition_queries.append(f'site:mp.weixin.qq.com "{primary_client}" {keyword}')
    decomposition_queries = deps.dedupe_strings(decomposition_queries, 8)

    rebuilt_scope_hints = merge_scope_hints_with_followup_context(
        rebuilt_scope_hints,
        {
            "strategy_query_expansions": decomposition_queries,
            "strategy_must_include_terms": deps.dedupe_strings(
                [
                    *(
                        normalize_text(term)
                        for segment in segment_candidates[:4]
                        for term in deps.extract_topic_anchor_terms(keyword, segment)[:3]
                        if normalize_text(term)
                    ),
                    *(normalize_text(str(item)) for item in inferred_scope_hints.get("strategy_must_include_terms", []) or [] if normalize_text(str(item))),
                ],
                10,
            ),
        },
        deps=deps,
    )
    summary_parts: list[str] = [f"已根据 {len(sections)} 组追问/补证输入重建二次检索范围"]
    rebuilt_filters: list[str] = []
    if rebuilt_scope_hints.get("regions"):
        rebuilt_filters.append(f"区域 { '/'.join(list(rebuilt_scope_hints.get('regions', []) or [])[:2]) }")
    if rebuilt_scope_hints.get("industries"):
        rebuilt_filters.append(f"行业 { '/'.join(list(rebuilt_scope_hints.get('industries', []) or [])[:2]) }")
    if rebuilt_scope_hints.get("clients"):
        rebuilt_filters.append(f"账户 { '/'.join(list(rebuilt_scope_hints.get('clients', []) or [])[:2]) }")
    if rebuilt_filters:
        summary_parts.append("，".join(rebuilt_filters))
    if decomposition_queries:
        summary_parts.append(f"并拆出 {len(decomposition_queries)} 条优先补证子查询")
    summary = "；".join(part for part in summary_parts if part)

    diagnostics = ResearchFollowupDiagnosticsOut(
        enabled=True,
        input_sections=[label for label, _ in sections],
        planning_focus=planning_focus,
        summary=summary,
        scope_rebuilt=bool(
            rebuilt_scope_hints.get("regions")
            or rebuilt_scope_hints.get("industries")
            or rebuilt_scope_hints.get("clients")
            or rebuilt_scope_hints.get("company_anchors")
        ),
        query_decomposition_applied=bool(decomposition_queries),
        decomposition_queries=decomposition_queries,
        rebuilt_regions=[normalize_text(str(item)) for item in rebuilt_scope_hints.get("regions", []) or [] if normalize_text(str(item))],
        rebuilt_industries=[normalize_text(str(item)) for item in rebuilt_scope_hints.get("industries", []) or [] if normalize_text(str(item))],
        rebuilt_clients=[normalize_text(str(item)) for item in rebuilt_scope_hints.get("clients", []) or [] if normalize_text(str(item))],
        rebuilt_company_anchors=[
            normalize_text(str(item))
            for item in rebuilt_scope_hints.get("company_anchors", []) or []
            if normalize_text(str(item))
        ],
        rebuilt_must_include_terms=[
            normalize_text(str(item))
            for item in rebuilt_scope_hints.get("strategy_must_include_terms", []) or []
            if normalize_text(str(item))
        ],
        rebuilt_exclusion_terms=[
            normalize_text(str(item))
            for item in rebuilt_scope_hints.get("strategy_exclusion_terms", []) or []
            if normalize_text(str(item))
        ],
    )
    return rebuilt_scope_hints, diagnostics


def render_followup_diagnostics_prompt_context(followup_diagnostics: ResearchFollowupDiagnosticsOut) -> str:
    if not followup_diagnostics.enabled:
        return "无"
    lines = [f"- 二次检索摘要: {normalize_text(followup_diagnostics.summary)}"]
    if followup_diagnostics.rebuilt_regions:
        lines.append(f"- 重建区域过滤: {' / '.join(followup_diagnostics.rebuilt_regions[:3])}")
    if followup_diagnostics.rebuilt_industries:
        lines.append(f"- 重建行业过滤: {' / '.join(followup_diagnostics.rebuilt_industries[:3])}")
    if followup_diagnostics.rebuilt_clients:
        lines.append(f"- 重建目标账户过滤: {' / '.join(followup_diagnostics.rebuilt_clients[:3])}")
    if followup_diagnostics.rebuilt_must_include_terms:
        lines.append(f"- 强制命中词: {' / '.join(followup_diagnostics.rebuilt_must_include_terms[:5])}")
    if followup_diagnostics.decomposition_queries:
        lines.append("- 优先子查询:")
        lines.extend(f"  - {query}" for query in followup_diagnostics.decomposition_queries[:6])
    if followup_diagnostics.impacted_sections:
        lines.append("- 重点影响章节:")
        lines.extend(
            f"  - {item.section_title} | {item.impact_label}/{item.impact_score} | {item.reason}"
            for item in followup_diagnostics.impacted_sections[:5]
        )
    return "\n".join(lines)


def render_followup_prompt_context(followup_context: ResearchFollowupContextOut) -> str:
    sections = [
        ("上一版研报标题", followup_context.followup_report_title),
        ("上一版执行摘要", followup_context.followup_report_summary),
        ("人工补充新信息", followup_context.supplemental_context),
        ("人工补充新证据/待核验线索", followup_context.supplemental_evidence),
        ("人工补充新需求", followup_context.supplemental_requirements),
    ]
    lines = [f"- {label}: {value}" for label, value in sections if normalize_text(value)]
    return "\n".join(lines) if lines else "无"


def followup_resolution_status(*, previous_text: str, current_text: str, enabled: bool) -> str:
    if not enabled or not normalize_text(previous_text):
        return "baseline"
    return "reused" if normalize_text(previous_text) == normalize_text(current_text) else "corrected"


def build_followup_impact_terms(
    followup_context: ResearchFollowupContextOut,
    followup_diagnostics: ResearchFollowupDiagnosticsOut,
    *,
    deps: FollowupImpactDependencies,
) -> list[str]:
    candidates: list[str] = []
    candidates.extend(
        [
            *followup_diagnostics.rebuilt_clients,
            *followup_diagnostics.rebuilt_company_anchors,
            *followup_diagnostics.rebuilt_must_include_terms[:6],
            followup_diagnostics.planning_focus,
            *followup_diagnostics.rebuilt_industries,
            *followup_diagnostics.rebuilt_regions,
        ]
    )
    for value in (
        followup_context.supplemental_requirements,
        followup_context.supplemental_context,
        followup_context.supplemental_evidence,
    ):
        normalized = normalize_text(value)
        if not normalized:
            continue
        candidates.extend(split_followup_research_segments(normalized, limit=4, deps=deps))
        candidates.extend(deps.tokenize_for_match(normalized))
    cleaned: list[str] = []
    generic_tokens = {token.lower() for token in deps.generic_focus_tokens}
    for candidate in candidates:
        normalized = normalize_text(str(candidate))
        if not normalized:
            continue
        lowered = normalized.lower()
        if lowered in generic_tokens:
            continue
        if deps.looks_like_source_noise_segment(normalized, raw_value=str(candidate)):
            continue
        if len(normalized) <= 1:
            continue
        cleaned.append(normalized)
    return deps.dedupe_strings(cleaned, 20)


def build_followup_section_impacts(
    report: ResearchReportDocument,
    *,
    deps: FollowupImpactDependencies,
) -> list[ResearchFollowupSectionImpactOut]:
    diagnostics = getattr(report, "followup_diagnostics", None)
    followup_context = getattr(report, "followup_context", None)
    if not diagnostics or not diagnostics.enabled or not followup_context:
        return []

    impact_terms = build_followup_impact_terms(followup_context, diagnostics, deps=deps)
    if not impact_terms:
        return []

    pack_map = {
        normalize_text(pack.section_title): pack
        for pack in getattr(getattr(report, "quality_profile", None), "section_retrieval_packs", []) or []
        if normalize_text(getattr(pack, "section_title", ""))
    }
    impacts: list[ResearchFollowupSectionImpactOut] = []
    for section in report.sections:
        normalized_title = normalize_text(section.title)
        section_text = normalize_text(
            "；".join(
                [
                    section.title,
                    *section.items,
                    section.evidence_note,
                    section.insufficiency_summary,
                    *section.next_verification_steps,
                ]
            )
        ).lower()
        pack = pack_map.get(normalized_title)
        pack_text = normalize_text(
            "；".join(
                [
                    pack.query if pack else "",
                    *(
                        normalize_text(f"{hit.title} {hit.snippet}")
                        for hit in (pack.hits[:3] if pack else [])
                    ),
                ]
            )
        ).lower()
        matched_inputs: list[str] = []
        for term in impact_terms:
            normalized_term = normalize_text(term).lower()
            if not normalized_term:
                continue
            if normalized_term in section_text or normalized_term in pack_text:
                matched_inputs.append(term)
        matched_inputs = deps.dedupe_strings(matched_inputs, 6)
        has_followup_match = bool(matched_inputs)
        pack_needs_attention = bool(pack) and pack.status != "ready" and (has_followup_match or pack.official_hit_count > 0)
        section_needs_attention = section.status != "ready" and has_followup_match
        if not has_followup_match and not pack_needs_attention and not section_needs_attention:
            continue

        impact_score = min(len(matched_inputs), 4) * 14
        if pack:
            impact_score += min(int(pack.support_score / 5), 20)
            impact_score += min(pack.official_hit_count, 2) * 8
            if pack.status != "ready":
                impact_score += 8
        if section.status != "ready":
            impact_score += 6
        impact_score = min(impact_score, 100)
        if impact_score >= 64:
            impact_label = "high"
        elif impact_score >= 36:
            impact_label = "medium"
        else:
            impact_label = "low"

        if pack and pack.status == "needs_evidence":
            reason = "追问输入已命中该章节，但公开证据仍不足，需先补证再升级结论。"
        elif pack and pack.official_hit_count > 0:
            reason = "追问输入直接命中该章节，且已有官方来源支撑，适合优先重写。"
        elif has_followup_match:
            reason = "追问输入与该章节主题直接相关，本轮应优先更新这部分判断。"
        else:
            reason = "该章节与二次检索重建范围相关，建议优先复核。"

        impacts.append(
            ResearchFollowupSectionImpactOut(
                section_title=section.title,
                status=section.status,
                impact_score=impact_score,
                impact_label=impact_label,
                reason=reason,
                matched_inputs=matched_inputs,
                retrieval_support_score=getattr(pack, "support_score", 0) if pack else 0,
                retrieval_hit_count=getattr(pack, "hit_count", 0) if pack else 0,
                official_hit_count=getattr(pack, "official_hit_count", 0) if pack else 0,
                next_action=(
                    (pack.next_steps[0] if pack and pack.next_steps else "")
                    or (section.next_verification_steps[0] if section.next_verification_steps else "")
                    or "继续补官方源、组织入口与采购时间窗。"
                ),
            )
        )
    severity_order = {"high": 0, "medium": 1, "low": 2}
    impacts.sort(
        key=lambda item: (
            severity_order.get(item.impact_label, 3),
            -item.impact_score,
            -item.official_hit_count,
            item.section_title,
        )
    )
    return impacts[:5]


def render_followup_section_focus_prompt_context(
    report: ResearchReportDocument,
    *,
    deps: FollowupImpactDependencies,
) -> str:
    impacts = build_followup_section_impacts(report, deps=deps)
    if not impacts:
        return "无"
    lines = []
    for impact in impacts:
        lines.append(
            " | ".join(
                [
                    impact.section_title,
                    f"impact={impact.impact_label}/{impact.impact_score}",
                    f"status={impact.status}",
                    f"matched={ ' / '.join(impact.matched_inputs[:3]) if impact.matched_inputs else 'none' }",
                    f"support={impact.retrieval_support_score}",
                    f"next={impact.next_action}",
                ]
            )
        )
    return "\n".join(f"- {line}" for line in lines)


def enrich_followup_diagnostics(
    report: ResearchReportResponse,
    *,
    deps: FollowupImpactDependencies,
) -> ResearchReportResponse:
    diagnostics = getattr(report, "followup_diagnostics", None)
    followup_context = getattr(report, "followup_context", None)
    if not diagnostics or not diagnostics.enabled or not followup_context:
        return report
    impacted_sections = build_followup_section_impacts(report, deps=deps)
    updated_summary = normalize_text(diagnostics.summary)
    if impacted_sections:
        impact_note = f"重点影响 {len(impacted_sections)} 个章节"
        if impact_note not in updated_summary:
            updated_summary = "；".join(part for part in [updated_summary, impact_note] if part)
    return report.model_copy(
        update={
            "followup_diagnostics": diagnostics.model_copy(
                update={
                    "summary": updated_summary,
                    "title_resolution": followup_resolution_status(
                        previous_text=followup_context.followup_report_title,
                        current_text=report.report_title,
                        enabled=diagnostics.enabled,
                    ),
                    "summary_resolution": followup_resolution_status(
                        previous_text=followup_context.followup_report_summary,
                        current_text=report.executive_summary,
                        enabled=diagnostics.enabled,
                    ),
                    "impacted_sections": impacted_sections,
                }
            )
        }
    )
