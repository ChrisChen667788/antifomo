from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.schemas.research import ResearchReportDocument, ResearchReportResponse, ResearchSourceDiagnosticsOut
from app.services.content_extractor import normalize_text
from app.services.research.entity_ranking import rank_report_entities
from app.services.research.source_documents import SourceDocument
from app.services.research.web_search import SearchHit


@dataclass(frozen=True, slots=True)
class QualityExpansionDependencies:
    get_settings: Callable[[], Any]
    dedupe_strings: Callable[..., list[str]]
    infer_input_scope_hints: Callable[[str, str | None], dict[str, object]]
    infer_scope_hints: Callable[[str, str | None, list[SourceDocument]], dict[str, object]]
    merge_scope_hints: Callable[[dict[str, object], dict[str, object]], dict[str, object]]
    build_corrective_query_plan: Callable[..., list[str]]
    build_expanded_query_plan: Callable[..., list[str]]
    curated_wechat_channels: tuple[str, ...]
    build_company_seed_hits: Callable[..., list[SearchHit]]
    search_public_web: Callable[..., list[SearchHit]]
    hybrid_rank_hits: Callable[..., list[SearchHit]]
    select_hits_with_source_balance: Callable[..., list[SearchHit]]
    dedupe_hits: Callable[[list[SearchHit]], list[SearchHit]]
    extract_source_document_best_effort: Callable[..., SourceDocument | None]
    filter_recent_sources: Callable[[list[SourceDocument]], list[SourceDocument]]
    build_theme_terms: Callable[[str, str | None, dict[str, object]], list[str]]
    resolved_company_anchor_terms: Callable[[str, str | None, dict[str, object]], list[str]]
    refine_sources_for_report: Callable[..., list[SourceDocument]]
    stored_report_to_result: Callable[[ResearchReportResponse], Any]
    build_entity_graph: Callable[..., Any]
    rank_top_entities: Callable[..., Any]
    filtered_rank_fallback_values: Callable[..., list[str]]
    build_entity_specific_contact_rows: Callable[..., list[str]]
    build_entity_specific_team_rows: Callable[..., list[str]]
    extract_topic_anchor_terms: Callable[[str, str | None], list[str]]
    collect_matched_theme_labels: Callable[..., list[str]]
    build_source_diagnostics: Callable[..., ResearchSourceDiagnosticsOut]
    source_max_age_years: int
    evidence_density_level: Callable[[list[SourceDocument], Any], str]
    source_quality_level: Callable[[list[SourceDocument]], str]
    source_documents_to_outputs: Callable[[list[SourceDocument]], list[Any]]
    build_sections: Callable[..., list[Any]]
    enrich_report_for_delivery: Callable[[ResearchReportResponse], ResearchReportResponse]
    report_sources_to_source_documents: Callable[[list[Any]], list[SourceDocument]]
    dedupe_sources: Callable[[list[SourceDocument]], list[SourceDocument]]
    review_generation_grounding: Callable[..., Any]
    evaluate_and_improve_research_report: Callable[..., ResearchReportResponse]
    emit_research_progress: Callable[..., None]
    build_progress_message: Callable[..., str]


def quality_expansion_score(report: ResearchReportDocument) -> int:
    evaluation = report.evaluation_profile if getattr(report, "evaluation_profile", None) else None
    if evaluation and int(evaluation.overall_score or 0) > 0:
        return int(evaluation.overall_score or 0)
    diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
    if int(diagnostics.response_quality_score or 0) > 0:
        return int(diagnostics.response_quality_score or 0)
    return int(getattr(report.quality_profile, "overall_score", 0) or 0)


def report_needs_public_quality_expansion(
    report: ResearchReportResponse,
    *,
    deps: QualityExpansionDependencies,
) -> bool:
    evidence_gate = getattr(report, "research_evidence_gate", None)
    if evidence_gate and evidence_gate.enforced:
        # Evidence-governed reports already run question-specific correction before drafting.
        # Post-draft expansion would bypass the admission and claim ledgers.
        return False
    app_settings = deps.get_settings()
    if not bool(app_settings.research_quality_expansion_enabled):
        return False
    evaluation = report.evaluation_profile if getattr(report, "evaluation_profile", None) else None
    diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
    min_score = max(1, min(int(app_settings.research_quality_expansion_min_score or 82), 100))
    score = quality_expansion_score(report)
    if evaluation and evaluation.status == "fail":
        return True
    if evaluation and evaluation.status == "watch":
        return True
    if score and score < min_score:
        return True
    if diagnostics.retrieval_quality == "low" or diagnostics.evidence_mode == "fallback":
        return True
    if report.solution_delivery_pack.source_support_score and report.solution_delivery_pack.source_support_score < 70:
        return True
    return report.quality_profile.status == "needs_evidence"


def quality_expansion_scope_hints(
    report: ResearchReportResponse,
    sources: list[SourceDocument],
    *,
    deps: QualityExpansionDependencies,
) -> dict[str, object]:
    diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
    base_scope_hints = deps.infer_input_scope_hints(report.keyword, report.research_focus)
    persisted_scope_hints = {
        "regions": list(diagnostics.scope_regions or []),
        "industries": list(diagnostics.scope_industries or []),
        "clients": deps.dedupe_strings(
            [
                *diagnostics.scope_clients,
                *(item.name for item in report.top_target_accounts),
                *report.target_accounts,
                report.solution_delivery_pack.target_customer,
            ],
            6,
        ),
        "company_anchors": deps.dedupe_strings(
            [
                *diagnostics.candidate_profile_companies,
                *(item.name for item in report.top_target_accounts),
                *(item.name for item in report.top_ecosystem_partners),
                *(item.name for item in report.top_competitors),
                *report.target_accounts,
                report.solution_delivery_pack.target_customer,
            ],
            8,
        ),
        "strategy_query_expansions": [],
        "strategy_exclusion_terms": list(diagnostics.strategy_exclusion_terms or []),
        "strategy_scope_summary": diagnostics.strategy_scope_summary,
    }
    inferred = deps.infer_scope_hints(report.keyword, report.research_focus, sources) if sources else {}
    return deps.merge_scope_hints(deps.merge_scope_hints(base_scope_hints, persisted_scope_hints), inferred)


def build_material_quality_expansion_query_plan(
    report: ResearchReportResponse,
    *,
    scope_hints: dict[str, object],
    limit: int,
    deps: QualityExpansionDependencies,
) -> list[str]:
    diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
    evaluation = report.evaluation_profile if getattr(report, "evaluation_profile", None) else None
    delivery_pack = report.solution_delivery_pack
    scope_terms = deps.dedupe_strings(
        [
            report.keyword,
            report.research_focus or "",
            delivery_pack.scenario,
            delivery_pack.target_customer,
            delivery_pack.vertical_scene,
            *report.target_accounts[:3],
            *(item.name for item in report.top_target_accounts[:3]),
            *report.flagship_products[:3],
        ],
        10,
    )
    scope = normalize_text(" ".join(scope_terms)) or report.keyword
    client_terms = deps.dedupe_strings(
        [
            delivery_pack.target_customer,
            *(str(item) for item in scope_hints.get("clients", []) or []),
            *report.target_accounts[:2],
            *(item.name for item in report.top_target_accounts[:2]),
        ],
        4,
    )
    queries: list[str] = [
        f"site:ccgp.gov.cn {scope} 采购意向 招标 中标 预算 技术参数",
        f"site:ggzy.gov.cn {scope} 招标 中标 项目 投标人 招标代理",
        f"site:cecbid.org.cn {scope} 招标 中标 采购 技术要求",
        f"site:cebpubservice.com {scope} 招标 中标 项目",
        f"site:gov.cn {scope} 政策 试点 建设方案 领导 讲话",
        f"site:mp.weixin.qq.com {scope} 方案 项目 招标 预算",
        f"{scope} 可行性研究 项目建议书 解决方案 技术参数",
        f"{scope} 客户 brief 投标准备 memo 执行材料 交付清单",
    ]
    if evaluation:
        queries.extend(evaluation.corrective_queries)
        queries.extend(evaluation.self_improvement.corrective_queries)
    queries.extend(diagnostics.corrective_query_plan)
    queries.extend(report.market_intelligence.external_source_queries)
    queries.extend(
        deps.build_corrective_query_plan(
            keyword=report.keyword,
            research_focus=report.research_focus,
            scope_hints=scope_hints,
            include_wechat=True,
            preferred_wechat_accounts=deps.curated_wechat_channels,
            limit=max(6, limit),
        )
    )
    queries.extend(
        deps.build_expanded_query_plan(
            report.keyword,
            report.research_focus,
            scope_hints=scope_hints,
            include_wechat=True,
            preferred_wechat_accounts=deps.curated_wechat_channels,
            limit=max(6, limit),
        )
    )
    for client in client_terms:
        queries.extend(
            [
                f"\"{client}\" {report.keyword} 官网 联系方式 商务合作",
                f"\"{client}\" {report.keyword} 采购 招标 中标 预算",
                f"\"{client}\" {report.keyword} 方案 项目建议书 可行性研究",
            ]
        )
    return deps.dedupe_strings(queries, max(1, limit))


def collect_public_quality_expansion_sources(
    *,
    report: ResearchReportResponse,
    existing_sources: list[SourceDocument],
    query_plan: list[str],
    scope_hints: dict[str, object],
    runtime: dict[str, int | str | bool],
    deps: QualityExpansionDependencies,
) -> list[SourceDocument]:
    if not query_plan:
        return []
    app_settings = deps.get_settings()
    existing_urls = {normalize_text(source.url) for source in existing_sources if normalize_text(source.url)}
    hits: list[SearchHit] = []
    seed_names = deps.dedupe_strings(
        [
            *(str(item) for item in scope_hints.get("clients", []) or []),
            *(str(item) for item in scope_hints.get("company_anchors", []) or []),
            *(item.name for item in report.top_target_accounts),
            *(item.name for item in report.top_ecosystem_partners),
            *(item.name for item in report.top_competitors),
        ],
        8,
    )
    hits.extend(deps.build_company_seed_hits(seed_names, keyword=report.keyword))
    timeout_seconds = max(6, int(runtime.get("search_timeout_seconds", app_settings.research_search_timeout_seconds) or 6))
    search_limit = max(3, int(runtime.get("search_result_limit", app_settings.research_max_search_results) or 3))
    for query in query_plan:
        try:
            hits.extend(deps.search_public_web(query, timeout_seconds=timeout_seconds, limit=search_limit))
        except Exception:
            continue
    if not hits:
        return []
    ranked_hits = deps.hybrid_rank_hits(
        hits,
        keyword=report.keyword,
        research_focus=report.research_focus,
        scope_hints=scope_hints,
    )
    selected_hits = deps.select_hits_with_source_balance(
        ranked_hits,
        limit=max(
            4,
            min(
                int(runtime.get("expanded_selected_limit", app_settings.research_max_sources) or app_settings.research_max_sources),
                app_settings.research_max_sources,
            ),
        ),
    )
    if not selected_hits:
        selected_hits = deps.dedupe_hits(hits)[:4]
    fetched_sources = [
        source
        for source in (
            deps.extract_source_document_best_effort(
                hit,
                timeout_seconds=max(8, int(runtime.get("url_timeout_seconds", app_settings.url_fetch_timeout_seconds) or 8)),
                excerpt_chars=app_settings.research_source_excerpt_chars,
            )
            for hit in selected_hits
        )
        if source is not None
    ]
    fetched_sources = deps.filter_recent_sources(fetched_sources)
    new_sources = [
        source
        for source in fetched_sources
        if normalize_text(source.url) and normalize_text(source.url) not in existing_urls
    ]
    if not new_sources:
        return []
    theme_terms = deps.build_theme_terms(report.keyword, report.research_focus, scope_hints)
    company_anchor_terms = deps.resolved_company_anchor_terms(report.keyword, report.research_focus, scope_hints)
    refined = deps.refine_sources_for_report(
        [*existing_sources, *new_sources],
        keyword=report.keyword,
        research_focus=report.research_focus,
        scope_hints=scope_hints,
        company_anchor_terms=company_anchor_terms,
        theme_terms=theme_terms,
    )
    refined_urls = {normalize_text(source.url) for source in refined if normalize_text(source.url)}
    return [source for source in new_sources if normalize_text(source.url) in refined_urls] or new_sources


def rebuild_report_with_quality_expansion_sources(
    report: ResearchReportResponse,
    *,
    sources: list[SourceDocument],
    query_plan: list[str],
    added_source_count: int,
    round_count: int,
    before_score: int,
    deps: QualityExpansionDependencies,
) -> ResearchReportResponse:
    scope_hints = quality_expansion_scope_hints(report, sources, deps=deps)
    result = deps.stored_report_to_result(report)
    theme_terms = deps.build_theme_terms(report.keyword, report.research_focus, scope_hints)
    entity_graph = deps.build_entity_graph(sources, scope_hints=scope_hints)
    rankings = rank_report_entities(
        sources=sources,
        parsed=result,
        output_language=report.output_language,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        entity_graph=entity_graph,
        rank_top_entities=deps.rank_top_entities,
        filtered_rank_fallback_values=deps.filtered_rank_fallback_values,
        dedupe_strings=deps.dedupe_strings,
        limit=3,
    )
    entity_names = deps.dedupe_strings(
        [
            *(item.name for item in rankings.top_target_accounts),
            *(item.name for item in rankings.top_ecosystem_partners),
            *(str(item) for item in scope_hints.get("clients", []) or []),
        ],
        6,
    )
    merged_public_contact_channels = deps.dedupe_strings(
        [
            *deps.build_entity_specific_contact_rows(
                sources,
                entity_names=entity_names,
                output_language=report.output_language,
                limit=5,
                scope_hints=scope_hints,
            ),
            *report.public_contact_channels,
        ],
        5,
    )
    merged_account_team_signals = deps.dedupe_strings(
        [
            *deps.build_entity_specific_team_rows(
                sources,
                entity_names=entity_names,
                scope_hints=scope_hints,
                output_language=report.output_language,
                limit=5,
            ),
            *report.account_team_signals,
        ],
        5,
    )
    topic_anchor_terms = deps.extract_topic_anchor_terms(report.keyword, report.research_focus)
    matched_theme_labels = deps.collect_matched_theme_labels(
        sources,
        scope_hints=scope_hints,
        topic_anchor_terms=topic_anchor_terms,
    )
    diagnostics = deps.build_source_diagnostics(
        sources,
        enabled_source_labels=deps.dedupe_strings(
            [*report.source_diagnostics.enabled_source_labels, "public_web_quality_expansion"],
            10,
        ),
        scope_hints=scope_hints,
        recency_window_years=deps.source_max_age_years,
        filtered_old_source_count=int(report.source_diagnostics.filtered_old_source_count or 0),
        filtered_region_conflict_count=int(report.source_diagnostics.filtered_region_conflict_count or 0),
        retained_source_count=len(sources),
        strict_topic_source_count=max(len(sources), int(report.source_diagnostics.strict_topic_source_count or 0)),
        topic_anchor_terms=topic_anchor_terms,
        matched_theme_labels=matched_theme_labels,
        entity_graph=entity_graph,
        expansion_triggered=True,
        corrective_triggered=True,
        candidate_profile_companies=deps.dedupe_strings(
            [
                *report.source_diagnostics.candidate_profile_companies,
                *(item.name for item in rankings.top_target_accounts),
                *(item.name for item in rankings.top_ecosystem_partners),
                *(item.name for item in rankings.top_competitors),
            ],
            6,
        ),
        candidate_profile_hit_count=int(report.source_diagnostics.candidate_profile_hit_count or 0),
        candidate_profile_official_hit_count=int(report.source_diagnostics.candidate_profile_official_hit_count or 0),
        candidate_profile_source_labels=report.source_diagnostics.candidate_profile_source_labels,
    )
    diagnostics = diagnostics.model_copy(
        update={
            "quality_expansion_triggered": True,
            "quality_expansion_rounds": round_count,
            "quality_expansion_before_score": before_score,
            "quality_expansion_added_source_count": added_source_count,
            "quality_expansion_query_plan": deps.dedupe_strings(query_plan, 12),
            "quality_expansion_notes": deps.dedupe_strings(
                [
                    "自评未达到高质量门槛，已自动扩大公开搜索途径并合并新来源。",
                    "扩源不受当前 source settings 限制，优先覆盖政府采购、公共资源交易、官网、公开披露页和公开公众号。",
                    "交付材料已基于合并后的来源重新生成情报包和证据口径。",
                ],
                5,
            ),
        }
    )
    rebuilt = report.model_copy(
        update={
            "top_target_accounts": rankings.top_target_accounts,
            "pending_target_candidates": rankings.pending_target_candidates,
            "top_competitors": rankings.top_competitors,
            "pending_competitor_candidates": rankings.pending_competitor_candidates,
            "top_ecosystem_partners": rankings.top_ecosystem_partners,
            "pending_partner_candidates": rankings.pending_partner_candidates,
            "public_contact_channels": merged_public_contact_channels,
            "account_team_signals": merged_account_team_signals,
            "source_count": len(sources),
            "evidence_density": deps.evidence_density_level(sources, result),
            "source_quality": deps.source_quality_level(sources),
            "query_plan": deps.dedupe_strings([*report.query_plan, *query_plan], 24),
            "sources": deps.source_documents_to_outputs(sources),
            "source_diagnostics": diagnostics,
            "entity_graph": entity_graph,
            "sections": deps.build_sections(result, report.output_language, sources),
        }
    )
    return deps.enrich_report_for_delivery(rebuilt)


def expand_report_public_sources_until_quality_improves(
    report: ResearchReportResponse,
    *,
    source_documents: list[SourceDocument],
    runtime: dict[str, int | str | bool] | None = None,
    progress_callback: Any | None = None,
    deps: QualityExpansionDependencies,
) -> ResearchReportResponse:
    if not report_needs_public_quality_expansion(report, deps=deps):
        return report
    app_settings = deps.get_settings()
    max_rounds = max(1, min(int(app_settings.research_quality_expansion_max_rounds or 1), 3))
    query_limit = max(3, min(int(app_settings.research_quality_expansion_query_limit or 8), 16))
    runtime_values = runtime or {}
    best_report = report
    best_score = quality_expansion_score(report)
    before_score = best_score
    current_sources = deps.dedupe_sources(source_documents or deps.report_sources_to_source_documents(report.sources))
    query_history: list[str] = []
    added_source_count = 0
    for round_index in range(1, max_rounds + 1):
        scope_hints = quality_expansion_scope_hints(best_report, current_sources, deps=deps)
        query_plan = build_material_quality_expansion_query_plan(
            best_report,
            scope_hints=scope_hints,
            limit=query_limit,
            deps=deps,
        )
        query_history = deps.dedupe_strings([*query_history, *query_plan], 16)
        deps.emit_research_progress(
            progress_callback,
            "quality_expansion",
            min(98, 92 + round_index),
            deps.build_progress_message(
                "自评质量一般，正在扩大公开搜索途径补证",
                keyword=best_report.keyword,
                research_focus=best_report.research_focus,
                mode=best_report.research_mode,
            ),
        )
        new_sources = collect_public_quality_expansion_sources(
            report=best_report,
            existing_sources=current_sources,
            query_plan=query_plan,
            scope_hints=scope_hints,
            runtime=runtime_values,
            deps=deps,
        )
        if not new_sources:
            diagnostics = best_report.source_diagnostics.model_copy(
                update={
                    "quality_expansion_triggered": True,
                    "quality_expansion_rounds": round_index,
                    "quality_expansion_before_score": before_score,
                    "quality_expansion_after_score": best_score,
                    "quality_expansion_added_source_count": added_source_count,
                    "quality_expansion_query_plan": query_history[:12],
                    "quality_expansion_notes": deps.dedupe_strings(
                        [
                            *best_report.source_diagnostics.quality_expansion_notes,
                            "已尝试公开扩源，但当前轮未获得新的可用来源。",
                        ],
                        5,
                    ),
                }
            )
            best_report = best_report.model_copy(update={"source_diagnostics": diagnostics})
            break
        added_source_count += len(new_sources)
        current_sources = deps.dedupe_sources([*current_sources, *new_sources])
        candidate = rebuild_report_with_quality_expansion_sources(
            best_report,
            sources=current_sources,
            query_plan=query_history,
            added_source_count=added_source_count,
            round_count=round_index,
            before_score=before_score,
            deps=deps,
        )
        generation_review = deps.review_generation_grounding(candidate, current_sources)
        candidate = candidate.model_copy(
            update={
                "source_diagnostics": candidate.source_diagnostics.model_copy(
                    update=generation_review.to_diagnostics_update()
                )
            }
        )
        candidate = deps.evaluate_and_improve_research_report(candidate, source_documents=current_sources)
        candidate_score = quality_expansion_score(candidate)
        diagnostics = candidate.source_diagnostics.model_copy(
            update={
                "quality_expansion_triggered": True,
                "quality_expansion_rounds": round_index,
                "quality_expansion_before_score": before_score,
                "quality_expansion_after_score": candidate_score,
                "quality_expansion_added_source_count": added_source_count,
                "quality_expansion_query_plan": query_history[:12],
            }
        )
        candidate = candidate.model_copy(update={"source_diagnostics": diagnostics})
        if candidate_score >= best_score or len(candidate.sources) > len(best_report.sources):
            best_report = candidate
            best_score = candidate_score
        if candidate_score >= int(app_settings.research_quality_expansion_min_score or 82) and candidate.evaluation_profile.status == "pass":
            break
    return best_report
