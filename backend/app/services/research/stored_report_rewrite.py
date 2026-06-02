from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Any

from app.schemas.research import (
    ResearchReportResponse,
    ResearchEntityGraphOut,
    ResearchReportReadinessOut,
    ResearchSourceDiagnosticsOut,
)
from app.services.content_extractor import normalize_text
from app.services.language import localized_text
from app.services.llm_parser import ResearchReportResult
from app.services.research.source_documents import SourceDocument


@dataclass(frozen=True, slots=True)
class StoredReportRewriteDependencies:
    source_text: Callable[[SourceDocument], str]
    source_theme_match_score: Callable[..., int]
    looks_like_insufficient: Callable[[str], bool]
    dedupe_strings: Callable[[Iterable[str], int], list[str]]
    sanitize_entity_row: Callable[[str, str], str]
    build_theme_terms: Callable[[str, str | None, dict[str, object]], list[str]]
    source_supports_target_account: Callable[..., bool]
    resolved_report_readiness: Callable[[ResearchReportResponse], ResearchReportReadinessOut]
    is_actionable_budget_row: Callable[[str], bool]
    is_summary_fact_row: Callable[[str], bool]
    looks_like_bad_executive_summary: Callable[[str], bool]
    compress_title_segments: Callable[..., list[str]]
    field_row_noise_tokens: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class StoredReportRewriteOrchestrationDependencies:
    report_sources_to_source_documents: Callable[[list[Any]], list[SourceDocument]]
    infer_input_scope_hints: Callable[..., dict[str, object]]
    canonicalize_stored_report_entities: Callable[..., ResearchReportResponse]
    dedupe_strings: Callable[[Iterable[str], int], list[str]]
    canonicalize_stored_entity_name: Callable[..., str]
    merge_scope_hints: Callable[[dict[str, object], dict[str, object]], dict[str, object]]
    infer_scope_hints: Callable[..., dict[str, object]]
    prune_industry_hints: Callable[[list[str]], list[str]]
    sanitize_entity_row: Callable[[str, str], str]
    build_entity_graph: Callable[..., ResearchEntityGraphOut]
    extract_topic_anchor_terms: Callable[[str, str | None], list[str]]
    collect_matched_theme_labels: Callable[..., list[str]]
    clean_candidate_profile_company_names: Callable[[Iterable[str]], list[str]]
    build_source_diagnostics: Callable[..., ResearchSourceDiagnosticsOut]
    resolve_stored_report_target_support: Callable[..., tuple[list[str], list[str], list[str]]]
    apply_guarded_rewrite_diagnostics: Callable[..., ResearchSourceDiagnosticsOut]
    assess_stored_report_rewrite_mode: Callable[..., tuple[str, list[str], dict[str, float]]]
    stored_report_to_result: Callable[[ResearchReportResponse], ResearchReportResult]
    report_intelligence_from_result: Callable[[ResearchReportResponse, ResearchReportResult], dict[str, list[str]]]
    build_source_intelligence: Callable[..., dict[str, list[str]]]
    sanitize_report_field_rows: Callable[[str, Iterable[str]], list[str]]
    merge_result_with_intelligence: Callable[[ResearchReportResult, dict[str, list[str]]], ResearchReportResult]
    apply_topic_specific_overrides: Callable[..., ResearchReportResult]
    canonicalize_stored_result_entities: Callable[..., ResearchReportResult]
    build_theme_terms: Callable[[str, str | None, dict[str, object]], list[str]]
    rank_report_entities: Callable[..., Any]
    rank_top_entities: Callable[..., Any]
    filtered_rank_fallback_values: Callable[..., list[str]]
    build_entity_specific_contact_rows: Callable[..., list[str]]
    build_entity_specific_team_rows: Callable[..., list[str]]
    build_sections: Callable[[ResearchReportResult, str, list[SourceDocument]], list[Any]]
    evidence_density_level: Callable[[list[SourceDocument], ResearchReportResult], str]
    source_quality_level: Callable[[list[SourceDocument]], str]
    source_documents_to_research_source_outputs: Callable[[list[SourceDocument]], list[Any]]
    enrich_report_for_delivery: Callable[[ResearchReportResponse], ResearchReportResponse]
    is_low_signal_execution_report: Callable[[ResearchReportResponse], bool]
    theme_labels_from_scope: Callable[..., list[str]]
    source_supports_target_account: Callable[..., bool]
    summary_fact_rows: Callable[..., list[str]]
    compress_title_segments: Callable[..., list[str]]
    scope_anchor_text_segments: Callable[[str | None], list[str]]
    build_guarded_rewrite_title: Callable[..., str]
    source_max_age_years: int


def stored_source_is_low_signal(
    source: SourceDocument,
    *,
    theme_terms: list[str],
    scope_hints: dict[str, object],
    deps: StoredReportRewriteDependencies,
) -> bool:
    text = deps.source_text(source)
    if not text:
        return True
    lowered = text.lower()
    domain = normalize_text(source.domain or "").lower()
    title_lower = normalize_text(source.title).lower()
    client_terms = [
        normalize_text(str(item)).lower()
        for item in scope_hints.get("clients", []) or []
        if normalize_text(str(item))
    ]
    if any(token in text for token in deps.field_row_noise_tokens):
        return True
    if any(token in lowered for token in ("header_", "[source", "javascript:", "返回顶部", "跳转到主要内容区域")):
        return True
    if deps.looks_like_insufficient(text):
        return True
    theme_score = deps.source_theme_match_score(source, theme_terms=theme_terms, scope_hints=scope_hints)
    procurement_aggregate_like = any(token in domain for token in ("cecbid", "cebpubservice", "chinabidding", "china-cpp", "jianyu"))
    tech_media_like = source.source_type == "tech_media_feed" or "yuntoutiao" in domain
    client_hit = any(term in lowered or term in title_lower for term in client_terms)
    if procurement_aggregate_like and not client_hit and theme_score < 14:
        return True
    if tech_media_like and not client_hit and theme_score < 16:
        return True
    if theme_terms and theme_score < 6 and source.source_tier != "official":
        return True
    if source.source_tier == "aggregate" and source.content_status == "snippet_only" and theme_score < 8:
        return True
    return False


def stored_report_concrete_targets(
    report: ResearchReportResponse,
    *,
    deps: StoredReportRewriteDependencies,
) -> list[str]:
    return deps.dedupe_strings(
        [
            deps.sanitize_entity_row("target_accounts", normalize_text(name))
            for name in [
                *(normalize_text(item.name) for item in report.top_target_accounts if normalize_text(item.name)),
                *(normalize_text(item.name) for item in report.pending_target_candidates if normalize_text(item.name)),
                *(normalize_text(item) for item in report.target_accounts if normalize_text(item)),
            ]
            if normalize_text(name)
        ],
        4,
    )


def resolve_stored_report_target_support(
    report: ResearchReportResponse,
    *,
    source_documents: list[SourceDocument],
    scope_hints: dict[str, object],
    deps: StoredReportRewriteDependencies,
) -> tuple[list[str], list[str], list[str]]:
    theme_terms = deps.build_theme_terms(report.keyword, report.research_focus, scope_hints)
    concrete_targets = stored_report_concrete_targets(report, deps=deps)
    supported_targets = [
        target
        for target in concrete_targets
        if any(
            deps.source_supports_target_account(
                source,
                target,
                theme_terms=theme_terms,
                scope_hints=scope_hints,
            )
            for source in source_documents
        )
    ]
    supported_target_set = {target for target in supported_targets}
    unsupported_targets = [target for target in concrete_targets if target not in supported_target_set]
    return concrete_targets, supported_targets, unsupported_targets


def guarded_rewrite_reason_label(reason: str, output_language: str) -> str:
    reason_map = {
        "single_source_nonready": {
            "zh-CN": "来源过少，当前报告还没达到可推进门槛。",
            "zh-TW": "來源過少，目前報告還沒達到可推進門檻。",
            "en": "Too few sources to treat this report as execution-ready.",
        },
        "no_sources": {
            "zh-CN": "没有保留到可用来源。",
            "zh-TW": "沒有保留到可用來源。",
            "en": "No usable sources were retained.",
        },
        "fallback_low_support": {
            "zh-CN": "当前仍是兜底候选，严格命中或官方源支撑不足。",
            "zh-TW": "目前仍是兜底候選，嚴格命中或官方源支撐不足。",
            "en": "The result is still fallback-grade and lacks strong strict-match or official-source support.",
        },
        "low_retrieval_low_official": {
            "zh-CN": "检索质量偏低，且官方源覆盖不足。",
            "zh-TW": "檢索品質偏低，且官方源覆蓋不足。",
            "en": "Retrieval quality is low and official-source coverage is too weak.",
        },
        "source_noise_majority": {
            "zh-CN": "保留来源里噪声占比过高。",
            "zh-TW": "保留來源裡噪聲佔比過高。",
            "en": "Too much of the retained source set is low-signal noise.",
        },
        "no_target_source_support": {
            "zh-CN": "目标账户没有被来源正文支撑。",
            "zh-TW": "目標帳戶沒有被來源正文支撐。",
            "en": "The named target accounts are not supported by source text.",
        },
        "unsupported_targets": {
            "zh-CN": "目标账户只有推断，没有形成预算、官方源或正文共同支撑。",
            "zh-TW": "目標帳戶只有推斷，沒有形成預算、官方源或正文共同支撐。",
            "en": "The target accounts are inferred only and lack budget, official-source, or source-text support.",
        },
        "no_concrete_targets": {
            "zh-CN": "当前还没有收敛到可验证的具体账户。",
            "zh-TW": "目前還沒有收斂到可驗證的具體帳戶。",
            "en": "The report has not converged on concrete accounts that can be verified.",
        },
        "post_rewrite_low_signal_guard": {
            "zh-CN": "重写后仍然低信号，继续保留在待核验 backlog。",
            "zh-TW": "重寫後仍然低訊號，繼續保留在待核驗 backlog。",
            "en": "The rewritten result is still low-signal and remains in the verification backlog.",
        },
    }
    template = reason_map.get(reason)
    if template:
        return localized_text(output_language, template, template.get("zh-CN", reason))
    return normalize_text(reason.replace("_", " ")) or reason


def apply_guarded_rewrite_diagnostics(
    source_diagnostics: ResearchSourceDiagnosticsOut,
    *,
    output_language: str,
    guarded_backlog: bool,
    guarded_rewrite_reasons: Iterable[str],
    supported_target_accounts: Iterable[str],
    unsupported_target_accounts: Iterable[str],
    deps: StoredReportRewriteDependencies,
) -> ResearchSourceDiagnosticsOut:
    reason_codes = deps.dedupe_strings(
        [normalize_text(str(reason)) for reason in guarded_rewrite_reasons if normalize_text(str(reason))],
        8,
    )
    supported_accounts = deps.dedupe_strings(
        [normalize_text(str(item)) for item in supported_target_accounts if normalize_text(str(item))],
        4,
    )
    unsupported_accounts = deps.dedupe_strings(
        [
            normalize_text(str(item))
            for item in unsupported_target_accounts
            if normalize_text(str(item)) and normalize_text(str(item)) not in supported_accounts
        ],
        4,
    )
    return source_diagnostics.model_copy(
        update={
            "guarded_backlog": guarded_backlog,
            "guarded_rewrite_reasons": reason_codes,
            "guarded_rewrite_reason_labels": [guarded_rewrite_reason_label(reason, output_language) for reason in reason_codes],
            "supported_target_accounts": supported_accounts,
            "unsupported_target_accounts": unsupported_accounts,
        }
    )


def assess_stored_report_rewrite_mode(
    report: ResearchReportResponse,
    *,
    source_documents: list[SourceDocument],
    scope_hints: dict[str, object],
    deps: StoredReportRewriteDependencies,
) -> tuple[str, list[str], dict[str, float]]:
    diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
    retained_source_count = len(source_documents)
    official_ratio = float(diagnostics.official_source_ratio or 0.0)
    strict_match_ratio = float(diagnostics.strict_match_ratio or 0.0)
    unique_domain_count = int(
        diagnostics.unique_domain_count
        or len({normalize_text(source.domain or "") for source in source_documents if normalize_text(source.domain or "")})
    )
    theme_terms = deps.build_theme_terms(report.keyword, report.research_focus, scope_hints)
    readiness = deps.resolved_report_readiness(report)
    actionable_budget_rows = [row for row in report.budget_signals if deps.is_actionable_budget_row(row)]
    actionable_timeline_rows = [row for row in report.tender_timeline if deps.is_summary_fact_row(row)]
    prefer_company_entities = bool(scope_hints.get("prefer_company_entities"))
    bad_executive_summary = deps.looks_like_bad_executive_summary(report.executive_summary)
    concrete_targets, supported_targets, _unsupported_targets = resolve_stored_report_target_support(
        report,
        source_documents=source_documents,
        scope_hints=scope_hints,
        deps=deps,
    )
    supported_target_count = len(supported_targets)
    low_signal_source_count = sum(
        1
        for source in source_documents
        if stored_source_is_low_signal(
            source,
            theme_terms=theme_terms,
            scope_hints=scope_hints,
            deps=deps,
        )
    )
    reasons: list[str] = []
    if retained_source_count <= 1 and readiness.status != "ready" and (
        not concrete_targets or not (actionable_budget_rows or actionable_timeline_rows)
    ):
        reasons.append("single_source_nonready")
    if retained_source_count == 0:
        reasons.append("no_sources")
    if diagnostics.evidence_mode == "fallback" and (official_ratio < 0.12 or strict_match_ratio < 0.25):
        reasons.append("fallback_low_support")
    if diagnostics.retrieval_quality == "low" and official_ratio < 0.15 and unique_domain_count < 3:
        reasons.append("low_retrieval_low_official")
    if retained_source_count and low_signal_source_count >= max(2, (retained_source_count + 1) // 2):
        reasons.append("source_noise_majority")
    if concrete_targets and supported_target_count == 0:
        reasons.append("no_target_source_support")
    if concrete_targets and supported_target_count == 0 and readiness.status != "ready" and (
        low_signal_source_count >= max(1, retained_source_count // 2)
        or not actionable_budget_rows
        or official_ratio < 0.55
    ):
        reasons.append("unsupported_targets")
    if not concrete_targets and (
        official_ratio < 0.1
        or (readiness.status != "ready" and retained_source_count < 4)
        or (readiness.status != "ready" and prefer_company_entities)
        or (readiness.status != "ready" and not actionable_budget_rows and low_signal_source_count >= max(1, retained_source_count // 2))
        or (readiness.status != "ready" and bad_executive_summary)
    ):
        reasons.append("no_concrete_targets")
    return (
        "guarded" if reasons else "rewrite",
        reasons,
        {
            "retained_source_count": float(retained_source_count),
            "official_ratio": official_ratio,
            "strict_match_ratio": strict_match_ratio,
            "unique_domain_count": float(unique_domain_count),
            "low_signal_source_count": float(low_signal_source_count),
            "concrete_target_count": float(len(concrete_targets)),
            "supported_target_count": float(supported_target_count),
        },
    )


def build_guarded_rewrite_title(
    *,
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    output_language: str,
    deps: StoredReportRewriteDependencies,
) -> str:
    scope_segments = deps.compress_title_segments(
        [
            *[normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))][:1],
            *[normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))][:1],
            *[normalize_text(str(item)) for item in scope_hints.get("clients", []) if normalize_text(str(item))][:1],
        ],
        limit=3,
    )
    fallback_segments = deps.compress_title_segments(
        [
            normalize_text(research_focus or ""),
            normalize_text(keyword),
        ],
        limit=2,
    )
    title_scope = "｜".join(scope_segments or fallback_segments) or normalize_text(keyword) or "研究主题"
    return localized_text(
        output_language,
        {
            "zh-CN": f"{title_scope}：待核验清单与补证路径",
            "zh-TW": f"{title_scope}：待核驗清單與補證路徑",
            "en": f"{title_scope}: Verification Backlog and Evidence Path",
        },
        f"{title_scope}：待核验清单与补证路径",
    )

def build_guarded_stored_research_report(
    report: ResearchReportResponse,
    *,
    source_documents: list[SourceDocument],
    scope_hints: dict[str, object],
    output_language: str,
    source_diagnostics: ResearchSourceDiagnosticsOut,
    entity_graph: ResearchEntityGraphOut,
    guarded_rewrite_reasons: list[str] | None = None,
    supported_target_accounts: list[str] | None = None,
    unsupported_target_accounts: list[str] | None = None,
    deps: StoredReportRewriteOrchestrationDependencies,
) -> ResearchReportResponse:
    _theme_labels_from_scope = deps.theme_labels_from_scope
    _sanitize_report_field_rows = deps.sanitize_report_field_rows
    _build_theme_terms = deps.build_theme_terms
    _dedupe_strings = deps.dedupe_strings
    _sanitize_entity_row = deps.sanitize_entity_row
    _source_supports_target_account = deps.source_supports_target_account
    _apply_guarded_rewrite_diagnostics = deps.apply_guarded_rewrite_diagnostics
    _compress_title_segments = deps.compress_title_segments
    _scope_anchor_text_segments = deps.scope_anchor_text_segments
    _summary_fact_rows = deps.summary_fact_rows
    _build_guarded_rewrite_title = deps.build_guarded_rewrite_title
    _build_sections = deps.build_sections
    _evidence_density_level = deps.evidence_density_level
    _source_quality_level = deps.source_quality_level
    _to_research_source_outputs = deps.source_documents_to_research_source_outputs
    _enrich_report_for_delivery = deps.enrich_report_for_delivery

    theme_labels = _theme_labels_from_scope(scope_hints, keyword=report.keyword, research_focus=report.research_focus)
    sanitized_departments = _sanitize_report_field_rows("target_departments", report.target_departments)
    sanitized_budget_signals = _sanitize_report_field_rows("budget_signals", report.budget_signals)
    sanitized_tender_timeline = _sanitize_report_field_rows("tender_timeline", report.tender_timeline)
    theme_terms = _build_theme_terms(report.keyword, report.research_focus, scope_hints)
    supported_accounts = _dedupe_strings(
        [
            normalize_text(str(item))
            for item in (
                supported_target_accounts
                if supported_target_accounts is not None
                else source_diagnostics.supported_target_accounts
            )
            if normalize_text(str(item))
        ],
        4,
    )
    safe_account_candidates = _dedupe_strings(
        [
            _sanitize_entity_row("target_accounts", normalize_text(item))
            for item in [
                *(normalize_text(str(item)) for item in scope_hints.get("clients", []) if normalize_text(str(item))),
                *(normalize_text(item) for item in report.target_accounts if normalize_text(item)),
            ]
            if normalize_text(item)
        ],
        4,
    )
    if not supported_accounts:
        supported_accounts = [
            item
            for item in safe_account_candidates
            if any(
                _source_supports_target_account(
                    source,
                    item,
                    theme_terms=theme_terms,
                    scope_hints=scope_hints,
                )
                for source in source_documents
            )
        ]
    unsupported_accounts = _dedupe_strings(
        [
            normalize_text(str(item))
            for item in (
                unsupported_target_accounts
                if unsupported_target_accounts is not None
                else source_diagnostics.unsupported_target_accounts
            )
            if normalize_text(str(item)) and normalize_text(str(item)) not in supported_accounts
        ],
        4,
    )
    safe_accounts = supported_accounts[:2]
    guarded_source_diagnostics = _apply_guarded_rewrite_diagnostics(
        source_diagnostics,
        output_language=output_language,
        guarded_backlog=True,
        guarded_rewrite_reasons=guarded_rewrite_reasons or source_diagnostics.guarded_rewrite_reasons,
        supported_target_accounts=supported_accounts,
        unsupported_target_accounts=unsupported_accounts,
    )
    guarded_scope_hints = {
        **scope_hints,
        "clients": safe_accounts,
        "company_anchors": _dedupe_strings(safe_accounts, 4),
        "anchor_text": normalize_text(
            " / ".join(
                [
                    *[normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))][:1],
                    *[normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))][:1],
                    *safe_accounts[:1],
                ]
            )
        ),
    }
    safe_departments = sanitized_departments[:3]
    safe_budgets = _summary_fact_rows(sanitized_budget_signals, limit=2)
    safe_timeline = _summary_fact_rows(sanitized_tender_timeline, limit=2)
    safe_key_signals = _dedupe_strings([*safe_accounts[:1], *safe_budgets[:1], *safe_timeline[:1]], 3)
    scope_anchor_segments = _compress_title_segments(
        [
            *_scope_anchor_text_segments(str(guarded_scope_hints.get("anchor_text", ""))),
            *[normalize_text(str(item)) for item in guarded_scope_hints.get("regions", []) if normalize_text(str(item))][:1],
            *[normalize_text(str(item)) for item in guarded_scope_hints.get("industries", []) if normalize_text(str(item))][:1],
            *[normalize_text(str(item)) for item in guarded_scope_hints.get("clients", []) if normalize_text(str(item))][:1],
            normalize_text(report.research_focus or ""),
            normalize_text(report.keyword),
        ],
        limit=4,
    )
    scope_anchor = " / ".join(scope_anchor_segments) or normalize_text(report.keyword)
    guarded_summary = localized_text(
        output_language,
        {
            "zh-CN": (
                f"当前公开来源不足以支持对 {scope_anchor} 形成具体账户、预算或竞对判断。"
                " 这一版仅保留为待核验清单，优先补官网、公告、采购和联系人线索后再进入正式推进。"
            ),
            "zh-TW": (
                f"目前公開來源不足以支撐對 {scope_anchor} 形成具體帳戶、預算或競對判斷。"
                " 這一版僅保留為待核驗清單，優先補官網、公告、採購與聯絡人線索後再進入正式推進。"
            ),
            "en": (
                f"Current public sources are not strong enough to support concrete buyer, budget, or competitor judgments for {scope_anchor}. "
                "Keep this version as a verification backlog and add official pages, notices, procurement records, and contact evidence before formal execution."
            ),
        },
        f"当前公开来源不足以支持对 {scope_anchor} 形成具体账户、预算或竞对判断。这一版仅保留为待核验清单，优先补官网、公告、采购和联系人线索后再进入正式推进。",
    )
    guarded_consulting_angle = localized_text(
        output_language,
        {
            "zh-CN": "先做范围收敛与补证，不做强销售判断，也不输出过度具体的推进承诺。",
            "zh-TW": "先做範圍收斂與補證，不做強銷售判斷，也不輸出過度具體的推進承諾。",
            "en": "Prioritize scope reduction and evidence recovery; do not force a strong sales judgment or overly specific execution claims yet.",
        },
        "先做范围收敛与补证，不做强销售判断，也不输出过度具体的推进承诺。",
    )
    guarded_result = ResearchReportResult(
        report_title=_build_guarded_rewrite_title(
            keyword=report.keyword,
            research_focus=report.research_focus,
            scope_hints=guarded_scope_hints,
            output_language=output_language,
        ),
        executive_summary=guarded_summary,
        consulting_angle=guarded_consulting_angle,
        industry_brief=[],
        key_signals=safe_key_signals,
        policy_and_leadership=[],
        commercial_opportunities=[],
        solution_design=[],
        sales_strategy=[],
        bidding_strategy=[],
        outreach_strategy=[],
        ecosystem_strategy=[],
        target_accounts=safe_accounts,
        target_departments=safe_departments,
        public_contact_channels=[],
        account_team_signals=safe_departments[:2],
        budget_signals=safe_budgets,
        project_distribution=[],
        strategic_directions=[],
        tender_timeline=safe_timeline,
        leadership_focus=[],
        ecosystem_partners=[],
        competitor_profiles=[],
        benchmark_cases=[],
        flagship_products=[],
        key_people=[],
        five_year_outlook=[],
        client_peer_moves=[],
        winner_peer_moves=[],
        competition_analysis=[],
        risks=[
            localized_text(
                output_language,
                {
                    "zh-CN": "当前版本证据门槛不足，若继续沿用会放大错误账户和动作建议。",
                    "zh-TW": "目前版本證據門檻不足，若繼續沿用會放大錯誤帳戶與動作建議。",
                    "en": "Evidence is below the required threshold; forcing this report forward would amplify wrong buyers and wrong next actions.",
                },
                "当前版本证据门槛不足，若继续沿用会放大错误账户和动作建议。",
            )
        ],
        next_actions=[
            localized_text(
                output_language,
                {
                    "zh-CN": "先补官网、公告、采购和联系人线索，再重新生成正式研报。",
                    "zh-TW": "先補官網、公告、採購與聯絡人線索，再重新生成正式研報。",
                    "en": "Add official pages, notices, procurement records, and contact evidence, then regenerate the formal report.",
                },
                "先补官网、公告、采购和联系人线索，再重新生成正式研报。",
            )
        ],
    )
    sections = _build_sections(guarded_result, output_language, source_documents)
    guarded_report = ResearchReportResponse(
        keyword=normalize_text(report.keyword),
        research_focus=normalize_text(report.research_focus or "") or None,
        output_language=output_language,
        research_mode=report.research_mode,
        report_title=guarded_result.report_title,
        executive_summary=guarded_result.executive_summary,
        consulting_angle=guarded_result.consulting_angle,
        sections=sections,
        target_accounts=guarded_result.target_accounts,
        top_target_accounts=[],
        pending_target_candidates=[],
        target_departments=guarded_result.target_departments,
        public_contact_channels=guarded_result.public_contact_channels,
        account_team_signals=guarded_result.account_team_signals,
        budget_signals=guarded_result.budget_signals,
        project_distribution=guarded_result.project_distribution,
        strategic_directions=guarded_result.strategic_directions,
        tender_timeline=guarded_result.tender_timeline,
        leadership_focus=guarded_result.leadership_focus,
        ecosystem_partners=guarded_result.ecosystem_partners,
        top_ecosystem_partners=[],
        pending_partner_candidates=[],
        competitor_profiles=guarded_result.competitor_profiles,
        top_competitors=[],
        pending_competitor_candidates=[],
        benchmark_cases=guarded_result.benchmark_cases,
        flagship_products=guarded_result.flagship_products,
        key_people=guarded_result.key_people,
        five_year_outlook=guarded_result.five_year_outlook,
        client_peer_moves=guarded_result.client_peer_moves,
        winner_peer_moves=guarded_result.winner_peer_moves,
        competition_analysis=guarded_result.competition_analysis,
        source_count=len(source_documents),
        evidence_density=_evidence_density_level(source_documents, guarded_result),
        source_quality=_source_quality_level(source_documents),
        query_plan=[normalize_text(item) for item in report.query_plan if normalize_text(item)],
        sources=_to_research_source_outputs(source_documents),
        source_diagnostics=guarded_source_diagnostics,
        entity_graph=entity_graph,
        generated_at=report.generated_at,
    )
    return _enrich_report_for_delivery(guarded_report)


def rewrite_stored_research_report(
    report: ResearchReportResponse,
    *,
    deps: StoredReportRewriteOrchestrationDependencies,
) -> ResearchReportResponse:
    _report_sources_to_source_documents = deps.report_sources_to_source_documents
    _infer_input_scope_hints = deps.infer_input_scope_hints
    _canonicalize_stored_report_entities = deps.canonicalize_stored_report_entities
    _dedupe_strings = deps.dedupe_strings
    _canonicalize_stored_entity_name = deps.canonicalize_stored_entity_name
    _merge_scope_hints = deps.merge_scope_hints
    _infer_scope_hints = deps.infer_scope_hints
    _prune_industry_hints = deps.prune_industry_hints
    _sanitize_entity_row = deps.sanitize_entity_row
    _build_entity_graph = deps.build_entity_graph
    _extract_topic_anchor_terms = deps.extract_topic_anchor_terms
    _collect_matched_theme_labels = deps.collect_matched_theme_labels
    _clean_candidate_profile_company_names = deps.clean_candidate_profile_company_names
    _build_source_diagnostics = deps.build_source_diagnostics
    _resolve_stored_report_target_support = deps.resolve_stored_report_target_support
    _apply_guarded_rewrite_diagnostics = deps.apply_guarded_rewrite_diagnostics
    _assess_stored_report_rewrite_mode = deps.assess_stored_report_rewrite_mode
    _stored_report_to_result = deps.stored_report_to_result
    _report_intelligence_from_result = deps.report_intelligence_from_result
    _build_source_intelligence = deps.build_source_intelligence
    _sanitize_report_field_rows = deps.sanitize_report_field_rows
    _merge_result_with_intelligence = deps.merge_result_with_intelligence
    _apply_topic_specific_overrides = deps.apply_topic_specific_overrides
    _canonicalize_stored_result_entities = deps.canonicalize_stored_result_entities
    _build_theme_terms = deps.build_theme_terms
    _entity_ranking_rank_report_entities = deps.rank_report_entities
    _rank_top_entities = deps.rank_top_entities
    _filtered_rank_fallback_values = deps.filtered_rank_fallback_values
    _build_entity_specific_contact_rows = deps.build_entity_specific_contact_rows
    _build_entity_specific_team_rows = deps.build_entity_specific_team_rows
    _build_sections = deps.build_sections
    _evidence_density_level = deps.evidence_density_level
    _source_quality_level = deps.source_quality_level
    _to_research_source_outputs = deps.source_documents_to_research_source_outputs
    _enrich_report_for_delivery = deps.enrich_report_for_delivery
    _is_low_signal_execution_report = deps.is_low_signal_execution_report
    SOURCE_MAX_AGE_YEARS = deps.source_max_age_years

    def _build_guarded_stored_research_report(*args: Any, **kwargs: Any) -> ResearchReportResponse:
        return build_guarded_stored_research_report(*args, **kwargs, deps=deps)

    keyword = normalize_text(report.keyword)
    research_focus = normalize_text(report.research_focus or "") or None
    output_language = report.output_language
    source_documents = _report_sources_to_source_documents(report.sources)
    diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
    base_scope_hints = _infer_input_scope_hints(keyword, research_focus)
    report = _canonicalize_stored_report_entities(
        report,
        scope_hints=base_scope_hints,
        source_documents=source_documents,
    )
    diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
    stored_clients = _dedupe_strings(
        [
            _canonicalize_stored_entity_name(
                normalize_text(item),
                field_key="target_accounts",
                scope_hints=base_scope_hints,
                source_documents=source_documents,
            )
            for item in [
                *(normalize_text(item) for item in diagnostics.scope_clients if normalize_text(item)),
                *(normalize_text(item.name) for item in report.top_target_accounts if normalize_text(item.name)),
                *(normalize_text(item.name) for item in report.pending_target_candidates if normalize_text(item.name)),
                *(normalize_text(item) for item in report.target_accounts if normalize_text(item)),
            ]
            if normalize_text(item)
        ],
        4,
    )
    stored_scope_hints = {
        "regions": _dedupe_strings([normalize_text(item) for item in diagnostics.scope_regions if normalize_text(item)], 3),
        "industries": _dedupe_strings([normalize_text(item) for item in diagnostics.scope_industries if normalize_text(item)], 3),
        "clients": stored_clients,
        "company_anchors": _dedupe_strings(stored_clients, 4),
        "strategy_must_include_terms": [],
        "strategy_exclusion_terms": _dedupe_strings(
            [normalize_text(item) for item in diagnostics.strategy_exclusion_terms if normalize_text(item)],
            8,
        ),
        "strategy_query_expansions": [],
        "strategy_scope_summary": normalize_text(diagnostics.strategy_scope_summary),
        "anchor_text": normalize_text(" / ".join(stored_clients[:2])),
    }
    scope_hints = _merge_scope_hints(base_scope_hints, stored_scope_hints)
    if source_documents:
        scope_hints = _merge_scope_hints(
            scope_hints,
            _infer_scope_hints(keyword, research_focus, source_documents),
        )
    stored_regions = [normalize_text(str(item)) for item in stored_scope_hints.get("regions", []) or [] if normalize_text(str(item))]
    stored_industries = [normalize_text(str(item)) for item in stored_scope_hints.get("industries", []) or [] if normalize_text(str(item))]
    if stored_regions or stored_industries:
        scope_hints = {
            **scope_hints,
            "regions": _dedupe_strings(stored_regions or [normalize_text(str(item)) for item in scope_hints.get("regions", []) or [] if normalize_text(str(item))], 3),
            "industries": _prune_industry_hints(stored_industries or [normalize_text(str(item)) for item in scope_hints.get("industries", []) or [] if normalize_text(str(item))]),
        }
    sanitized_scope_clients = _dedupe_strings(
        [
            _sanitize_entity_row("target_accounts", normalize_text(str(item)))
            for item in scope_hints.get("clients", []) or []
            if normalize_text(str(item))
        ],
        4,
    )
    scope_hints = {
        **scope_hints,
        "clients": sanitized_scope_clients,
        "company_anchors": _dedupe_strings(
            [
                *(normalize_text(str(item)) for item in scope_hints.get("company_anchors", []) if normalize_text(str(item))),
                *sanitized_scope_clients,
            ],
            4,
        ),
        "anchor_text": normalize_text(
            " / ".join(
                [
                    *[normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))][:2],
                    *[normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))][:2],
                    *sanitized_scope_clients[:2],
                ]
            )
        ),
    }

    entity_graph = _build_entity_graph(source_documents, scope_hints=scope_hints)
    topic_anchor_terms = diagnostics.topic_anchor_terms or _extract_topic_anchor_terms(keyword, research_focus)
    matched_theme_labels = _collect_matched_theme_labels(
        source_documents,
        scope_hints=scope_hints,
        topic_anchor_terms=topic_anchor_terms,
    )
    candidate_profile_companies = _clean_candidate_profile_company_names(
        [
            *diagnostics.candidate_profile_companies,
            *(normalize_text(item.name) for item in report.top_target_accounts if normalize_text(item.name)),
            *(normalize_text(item.name) for item in report.top_competitors if normalize_text(item.name)),
            *(normalize_text(item.name) for item in report.top_ecosystem_partners if normalize_text(item.name)),
            *(normalize_text(item) for item in scope_hints.get("clients", []) if normalize_text(str(item))),
        ]
    )
    source_diagnostics = _build_source_diagnostics(
        source_documents,
        enabled_source_labels=_dedupe_strings(
            [normalize_text(item) for item in diagnostics.enabled_source_labels if normalize_text(item)]
            or [normalize_text(source.source_label or "") for source in source_documents if normalize_text(source.source_label or "")],
            8,
        ),
        scope_hints=scope_hints,
        recency_window_years=int(diagnostics.recency_window_years or SOURCE_MAX_AGE_YEARS),
        filtered_old_source_count=int(diagnostics.filtered_old_source_count or 0),
        filtered_region_conflict_count=int(diagnostics.filtered_region_conflict_count or 0),
        retained_source_count=len(source_documents),
        strict_topic_source_count=len(source_documents),
        topic_anchor_terms=topic_anchor_terms,
        matched_theme_labels=matched_theme_labels,
        entity_graph=entity_graph,
        expansion_triggered=bool(diagnostics.expansion_triggered),
        corrective_triggered=bool(diagnostics.corrective_triggered),
        candidate_profile_companies=candidate_profile_companies,
        candidate_profile_hit_count=0,
        candidate_profile_official_hit_count=0,
        candidate_profile_source_labels=[],
    )
    _concrete_targets, supported_target_accounts, unsupported_target_accounts = _resolve_stored_report_target_support(
        report,
        source_documents=source_documents,
        scope_hints=scope_hints,
    )
    source_diagnostics = _apply_guarded_rewrite_diagnostics(
        source_diagnostics,
        output_language=output_language,
        guarded_backlog=False,
        guarded_rewrite_reasons=[],
        supported_target_accounts=supported_target_accounts,
        unsupported_target_accounts=unsupported_target_accounts,
    )
    rewrite_mode, rewrite_reasons, _rewrite_metrics = _assess_stored_report_rewrite_mode(
        report,
        source_documents=source_documents,
        scope_hints=scope_hints,
    )
    if rewrite_mode == "guarded":
        guarded_scope_hints = {
            **scope_hints,
            "strategy_scope_summary": normalize_text(" / ".join(rewrite_reasons)),
        }
        return _build_guarded_stored_research_report(
            report,
            source_documents=source_documents,
            scope_hints=guarded_scope_hints,
            output_language=output_language,
            source_diagnostics=source_diagnostics,
            entity_graph=entity_graph,
            guarded_rewrite_reasons=rewrite_reasons,
            supported_target_accounts=supported_target_accounts,
            unsupported_target_accounts=unsupported_target_accounts,
        )

    base_result = _stored_report_to_result(report)
    combined_intelligence = _report_intelligence_from_result(report, base_result)
    if source_documents:
        source_intelligence = _build_source_intelligence(
            source_documents,
            keyword=keyword,
            research_focus=research_focus,
            output_language=output_language,
            scope_hints=scope_hints,
        )
        for key, values in source_intelligence.items():
            combined_intelligence[key] = _sanitize_report_field_rows(
                key,
                [*(combined_intelligence.get(key, []) or []), *values],
            )

    parsed = _merge_result_with_intelligence(base_result, combined_intelligence)
    parsed = _apply_topic_specific_overrides(
        parsed,
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        scope_hints=scope_hints,
        intelligence=combined_intelligence,
    )
    parsed = _canonicalize_stored_result_entities(
        parsed,
        scope_hints=scope_hints,
        source_documents=source_documents,
    )

    theme_terms = _build_theme_terms(keyword, research_focus, scope_hints)
    rankings = _entity_ranking_rank_report_entities(
        sources=source_documents,
        parsed=parsed,
        output_language=output_language,
        scope_hints=scope_hints,
        theme_terms=theme_terms,
        entity_graph=entity_graph,
        rank_top_entities=_rank_top_entities,
        filtered_rank_fallback_values=_filtered_rank_fallback_values,
        dedupe_strings=_dedupe_strings,
        limit=3,
    )

    merged_public_contact_channels = _dedupe_strings(
        [
            *_build_entity_specific_contact_rows(
                source_documents,
                entity_names=rankings.contact_entity_names(
                    scope_clients=list(scope_hints.get("clients", []) or []),
                    dedupe_strings=_dedupe_strings,
                ),
                output_language=output_language,
                limit=5,
            ),
            *parsed.public_contact_channels,
        ],
        5,
    )
    merged_account_team_signals = _dedupe_strings(
        [
            *_build_entity_specific_team_rows(
                source_documents,
                entity_names=rankings.team_entity_names(
                    scope_clients=list(scope_hints.get("clients", []) or []),
                    dedupe_strings=_dedupe_strings,
                ),
                scope_hints=scope_hints,
                output_language=output_language,
                limit=5,
            ),
            *parsed.account_team_signals,
        ],
        5,
    )

    sections = _build_sections(parsed, output_language, source_documents)
    rewritten_report = ResearchReportResponse(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        research_mode=report.research_mode,
        report_title=parsed.report_title,
        executive_summary=parsed.executive_summary,
        consulting_angle=parsed.consulting_angle,
        sections=sections,
        target_accounts=parsed.target_accounts,
        top_target_accounts=rankings.top_target_accounts,
        pending_target_candidates=rankings.pending_target_candidates,
        target_departments=parsed.target_departments,
        public_contact_channels=_sanitize_report_field_rows("public_contact_channels", merged_public_contact_channels),
        account_team_signals=_sanitize_report_field_rows("account_team_signals", merged_account_team_signals),
        budget_signals=parsed.budget_signals,
        project_distribution=parsed.project_distribution,
        strategic_directions=parsed.strategic_directions,
        tender_timeline=parsed.tender_timeline,
        leadership_focus=parsed.leadership_focus,
        ecosystem_partners=parsed.ecosystem_partners,
        top_ecosystem_partners=rankings.top_ecosystem_partners,
        pending_partner_candidates=rankings.pending_partner_candidates,
        competitor_profiles=parsed.competitor_profiles,
        top_competitors=rankings.top_competitors,
        pending_competitor_candidates=rankings.pending_competitor_candidates,
        benchmark_cases=parsed.benchmark_cases,
        flagship_products=parsed.flagship_products,
        key_people=parsed.key_people,
        five_year_outlook=parsed.five_year_outlook,
        client_peer_moves=parsed.client_peer_moves,
        winner_peer_moves=parsed.winner_peer_moves,
        competition_analysis=parsed.competition_analysis,
        source_count=len(source_documents),
        evidence_density=_evidence_density_level(source_documents, parsed),
        source_quality=_source_quality_level(source_documents),
        query_plan=[normalize_text(item) for item in report.query_plan if normalize_text(item)],
        sources=_to_research_source_outputs(source_documents),
        source_diagnostics=source_diagnostics,
        entity_graph=entity_graph,
        generated_at=report.generated_at,
    )
    enriched_report = _enrich_report_for_delivery(rewritten_report)
    if (
        not normalize_text(enriched_report.report_title).endswith(("待核验清单与补证路径", "待核驗清單與補證路徑", "Verification Backlog and Evidence Path"))
        and _is_low_signal_execution_report(enriched_report)
    ):
        guarded_scope_hints = {
            **scope_hints,
            "strategy_scope_summary": normalize_text("post_rewrite_low_signal_guard"),
        }
        return _build_guarded_stored_research_report(
            report,
            source_documents=source_documents,
            scope_hints=guarded_scope_hints,
            output_language=output_language,
            source_diagnostics=source_diagnostics,
            entity_graph=entity_graph,
            guarded_rewrite_reasons=["post_rewrite_low_signal_guard"],
            supported_target_accounts=supported_target_accounts,
            unsupported_target_accounts=unsupported_target_accounts,
        )
    return enriched_report
