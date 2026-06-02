from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
from typing import Any

from app.services.content_extractor import normalize_text
from app.services.language import localized_text
from app.services.llm_parser import ResearchReportResult


@dataclass(frozen=True, slots=True)
class StrategyRefinementDependencies:
    theme_labels_from_scope: Callable[..., list[str]]
    filter_theme_aligned_rows: Callable[..., list[str]]
    entity_display_labels: Callable[..., list[str]]
    summary_fact_rows: Callable[..., list[str]]
    is_actionable_budget_row: Callable[[str], bool]
    research_result_needs_override: Callable[[ResearchReportResult], bool]
    company_intent_summary_needs_override: Callable[..., bool]
    summary_contains_output_noise: Callable[[str], bool]
    build_report_title_override: Callable[..., str]
    build_scope_summary_sentence: Callable[..., str]
    looks_like_insufficient: Callable[[str], bool]
    looks_like_bad_executive_summary: Callable[[str], bool]
    build_exec_summary_override: Callable[..., str]
    concrete_rows: Callable[[list[str]], list[str]]
    dedupe_strings: Callable[..., list[str]]
    get_strategy_llm_service: Callable[[], Any]
    parse_strategy_scope_response: Callable[[str], Any]
    parse_strategy_refine_response: Callable[[str], Any]
    merge_scope_hints: Callable[[dict[str, object], dict[str, object]], dict[str, object]]
    looks_like_bad_report_title: Callable[[str], bool]
    is_theme_aligned_report_title: Callable[..., bool]


def apply_topic_specific_overrides(
    result: ResearchReportResult,
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    scope_hints: dict[str, object],
    intelligence: dict[str, list[str]],
    deps: StrategyRefinementDependencies,
) -> ResearchReportResult:
    payload = result.model_dump(mode="python")
    theme_labels = deps.theme_labels_from_scope(scope_hints, keyword=keyword, research_focus=research_focus)
    if theme_labels:
        for field_key, role in (
            ("target_accounts", "target"),
            ("competitor_profiles", "competitor"),
            ("ecosystem_partners", "partner"),
            ("client_peer_moves", "target"),
            ("winner_peer_moves", "competitor"),
        ):
            payload[field_key] = deps.filter_theme_aligned_rows(
                payload.get(field_key, []),
                role=role,
                theme_labels=theme_labels,
                scope_hints=scope_hints,
            )
    scope_anchor = normalize_text(str(scope_hints.get("anchor_text", ""))) or normalize_text(research_focus or "") or keyword
    accounts = deps.entity_display_labels(payload.get("target_accounts", []) or intelligence.get("target_accounts", []), limit=2)
    budgets = deps.summary_fact_rows(
        [item for item in intelligence.get("budget_signals", []) if deps.is_actionable_budget_row(item)],
        limit=2,
    )
    competitors = deps.entity_display_labels(payload.get("competitor_profiles", []) or intelligence.get("competitor_profiles", []), limit=2)
    partners = deps.entity_display_labels(payload.get("ecosystem_partners", []) or intelligence.get("ecosystem_partners", []), limit=2)
    teams = deps.summary_fact_rows(payload.get("account_team_signals", []) or intelligence.get("account_team_signals", []), limit=2)
    original_summary = normalize_text(result.executive_summary)
    original_consulting_angle = normalize_text(result.consulting_angle)
    needs_override = deps.research_result_needs_override(result) or deps.company_intent_summary_needs_override(
        scope_hints=scope_hints,
        summary=original_summary,
        accounts=accounts,
        competitors=competitors,
    ) or deps.summary_contains_output_noise(original_summary)

    payload["report_title"] = deps.build_report_title_override(
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
        intelligence=intelligence,
        output_language=output_language,
    )

    summary_rows = [
        deps.build_scope_summary_sentence(
            scope_anchor=scope_anchor,
            accounts=accounts,
            budgets=budgets,
            competitors=competitors,
            partners=partners,
            teams=teams,
            output_language=output_language,
        )
    ]
    if accounts and budgets:
        summary_rows.append(localized_text(output_language, {"zh-CN": "研判重点应先围绕甲方收敛、预算口径和采购节奏同步推进，而不是泛泛讨论赛道趋势。", "zh-TW": "研判重點應先圍繞甲方收斂、預算口徑與採購節奏同步推進，而不是泛泛討論賽道趨勢。", "en": "The memo should prioritize buyer convergence, budget validation, and procurement timing instead of generic market commentary."}, "研判重点应先围绕甲方收敛、预算口径和采购节奏同步推进，而不是泛泛讨论赛道趋势。"))
    if competitors or partners:
        summary_rows.append(localized_text(output_language, {"zh-CN": "竞品与生态判断应优先服务于进入路径设计：谁在抢预算、谁适合合作、谁能帮助尽快触达甲方。", "zh-TW": "競品與生態判斷應優先服務於進入路徑設計：誰在搶預算、誰適合合作、誰能幫助盡快觸達甲方。", "en": "Competition and ecosystem analysis should be used to shape the entry path: who is contesting budget, who is coopetition-ready, and who can accelerate buyer access."}, "竞品与生态判断应优先服务于进入路径设计：谁在抢预算、谁适合合作、谁能帮助尽快触达甲方。"))
    if summary_rows:
        if needs_override or not original_summary or deps.looks_like_insufficient(original_summary) or deps.looks_like_bad_executive_summary(original_summary):
            payload["executive_summary"] = deps.build_exec_summary_override(
                scope_anchor=scope_anchor,
                accounts=accounts,
                budgets=budgets,
                competitors=competitors,
                partners=partners,
                teams=teams,
                output_language=output_language,
            )
        else:
            payload["executive_summary"] = original_summary

    consulting_angle_override = localized_text(
        output_language,
        {
            "zh-CN": f"建议围绕 {scope_anchor} 同时服务两类任务：方案设计上聚焦场景拆解、试点路径和扩容逻辑；打单策略上聚焦账户收敛、预算口径、竞品差异化和伙伴牵线。",
            "zh-TW": f"建議圍繞 {scope_anchor} 同時服務兩類任務：方案設計上聚焦場景拆解、試點路徑與擴容邏輯；打單策略上聚焦帳戶收斂、預算口徑、競品差異化與夥伴牽線。",
            "en": f"For {scope_anchor}, the memo should serve both solution design and deal strategy: use-case decomposition, pilot-to-scale logic, buyer targeting, budget validation, competitor differentiation, and partner-led access.",
        },
        f"建议围绕 {scope_anchor} 同时服务两类任务：方案设计上聚焦场景拆解、试点路径和扩容逻辑；打单策略上聚焦账户收敛、预算口径、竞品差异化和伙伴牵线。",
    )
    if needs_override or not original_consulting_angle or deps.looks_like_insufficient(original_consulting_angle):
        payload["consulting_angle"] = consulting_angle_override

    if not deps.concrete_rows(payload.get("key_signals", [])):
        payload["key_signals"] = deps.dedupe_strings([*accounts[:1], *budgets[:1], *competitors[:1], *partners[:1]], 4)
    if not deps.concrete_rows(payload.get("commercial_opportunities", [])):
        payload["commercial_opportunities"] = deps.dedupe_strings([*accounts[:2], *budgets[:2]], 4)
    if not deps.concrete_rows(payload.get("competition_analysis", [])):
        payload["competition_analysis"] = deps.dedupe_strings([*competitors[:2], *partners[:1]], 4)
    if not deps.concrete_rows(payload.get("account_team_signals", [])):
        payload["account_team_signals"] = deps.dedupe_strings(teams, 4)

    return ResearchReportResult.model_validate(payload)


def apply_strategy_scope_planning(
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    input_scope_hints: dict[str, object],
    deps: StrategyRefinementDependencies,
) -> dict[str, object]:
    strategy_llm = deps.get_strategy_llm_service()
    if strategy_llm is None:
        return input_scope_hints
    try:
        raw = strategy_llm.run_prompt(
            "research_strategy_scope.txt",
            {
                "keyword": keyword,
                "research_focus": research_focus or "",
                "output_language": output_language,
                "scope_hints": json.dumps(input_scope_hints, ensure_ascii=False),
            },
        )
        planned = deps.parse_strategy_scope_response(raw)
    except Exception:
        return input_scope_hints
    return deps.merge_scope_hints(
        input_scope_hints,
        {
            "regions": planned.locked_regions,
            "industries": planned.locked_industries,
            "clients": planned.locked_clients,
            "company_anchors": planned.company_anchors,
            "strategy_must_include_terms": planned.must_include_terms,
            "strategy_exclusion_terms": planned.must_exclude_terms,
            "strategy_query_expansions": planned.query_expansions,
            "strategy_scope_summary": planned.reasoning_summary,
        },
    )


def apply_strategy_llm_refinement(
    result: ResearchReportResult,
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    scope_hints: dict[str, object],
    intelligence: dict[str, list[str]],
    deps: StrategyRefinementDependencies,
) -> ResearchReportResult:
    strategy_llm = deps.get_strategy_llm_service()
    if strategy_llm is None:
        return result
    current_report = {
        "report_title": result.report_title,
        "executive_summary": result.executive_summary,
        "consulting_angle": result.consulting_angle,
        "target_accounts": result.target_accounts[:4],
        "target_departments": result.target_departments[:4],
        "public_contact_channels": result.public_contact_channels[:4],
        "account_team_signals": result.account_team_signals[:4],
        "budget_signals": result.budget_signals[:4],
        "project_distribution": result.project_distribution[:4],
        "strategic_directions": result.strategic_directions[:4],
        "tender_timeline": result.tender_timeline[:4],
        "ecosystem_partners": result.ecosystem_partners[:4],
        "competitor_profiles": result.competitor_profiles[:4],
        "benchmark_cases": result.benchmark_cases[:4],
    }
    try:
        raw = strategy_llm.run_prompt(
            "research_strategy_refine.txt",
            {
                "keyword": keyword,
                "research_focus": research_focus or "",
                "output_language": output_language,
                "scope_hints": json.dumps(scope_hints, ensure_ascii=False),
                "source_intelligence": json.dumps(intelligence, ensure_ascii=False),
                "current_report": json.dumps(current_report, ensure_ascii=False),
            },
        )
        refined = deps.parse_strategy_refine_response(raw)
    except Exception:
        return result

    payload = result.model_dump(mode="python")
    refined_title = normalize_text(refined.report_title)
    if refined_title and not deps.looks_like_bad_report_title(refined_title) and deps.is_theme_aligned_report_title(
        refined_title,
        scope_hints=scope_hints,
        keyword=keyword,
        research_focus=research_focus,
    ):
        payload["report_title"] = refined_title
    refined_summary = normalize_text(refined.executive_summary)
    if refined_summary and not deps.looks_like_bad_executive_summary(refined_summary):
        payload["executive_summary"] = normalize_text(refined.executive_summary)
    if normalize_text(refined.consulting_angle):
        payload["consulting_angle"] = normalize_text(refined.consulting_angle)
    if deps.looks_like_bad_report_title(str(payload.get("report_title", ""))):
        payload["report_title"] = deps.build_report_title_override(
            keyword=keyword,
            research_focus=research_focus,
            scope_hints=scope_hints,
            intelligence=intelligence,
            output_language=output_language,
        )
    return ResearchReportResult.model_validate(payload)
