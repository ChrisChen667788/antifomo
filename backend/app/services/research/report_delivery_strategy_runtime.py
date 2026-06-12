from __future__ import annotations

from collections.abc import Iterable
import re

from app.services.content_extractor import normalize_text
from app.services.language import localized_text
from app.services.llm_parser import (
    ResearchReportResult,
    parse_research_strategy_refine_response,
    parse_research_strategy_scope_response,
)
from app.services.llm_service import get_strategy_llm_service
from app.services.research.entity_heuristics import (
    company_intent_summary_needs_override,
    filter_theme_aligned_rows,
)
from app.services.research.entity_policy import (
    ENTITY_INVALID_PHRASE_TOKENS,
    ENTITY_SUFFIX_TOKENS,
    GENERIC_FOCUS_TOKENS,
    GENERIC_SCOPE_CLIENT_TOKENS,
    KNOWN_LIGHTWEIGHT_ENTITY_NAMES,
    THEME_ENTITY_BLOCK_TOKENS,
    contains_low_value_entity_token,
    fallback_entity_name_from_row,
    is_theme_aligned_entity_name,
    looks_like_fragment_entity_name,
    looks_like_placeholder_entity_name,
    strip_entity_leading_noise,
)
from app.services.research.report_common import dedupe_strings
from app.services.research.report_row_quality import (
    BAD_EXEC_SUMMARY_PHRASES,
    FIELD_ROW_NOISE_TOKENS,
    SUMMARY_GUIDANCE_TOKENS,
    is_actionable_budget_row,
    looks_like_insufficient,
    summary_fact_rows,
)
from app.services.research.report_text_quality import (
    ReportTextQualityDependencies,
    looks_like_bad_executive_summary,
)
from app.services.research.scope_entity_runtime_dependencies import scope_entity_runtime_functions
from app.services.research.scope_hints import clean_scope_entity_names, extract_rank_entity_candidates, merge_scope_hints
from app.services.research.source_documents import looks_like_source_artifact_text
from app.services.research.strategy_refinement import (
    StrategyRefinementDependencies,
    apply_topic_specific_overrides as apply_strategy_topic_specific_overrides,
)


TITLE_SCOPE_GENERIC_TOKENS = (
    "相关商机",
    "潛在商機",
    "潜在商机",
    "市场机会",
    "市場機會",
    "机会分析",
    "機會分析",
    "解决方案",
    "解決方案",
    "研究",
    "研报",
    "報告",
    "报告",
)
SCENARIO_PRIORITY_TOKENS = (
    "漫剧", "短剧", "动画", "動漫", "内容", "內容", "政务服务", "政務服務",
    "政务云", "政務雲", "数据中心", "數據中心", "采购", "採購", "招标", "標案",
    "预算", "預算", "平台", "场景", "場景",
)
TITLE_STAGE_LABELS = (
    ("四期", "扩容窗口"),
    ("三期", "扩容窗口"),
    ("二期", "扩容窗口"),
    ("扩容", "扩容窗口"),
    ("中标", "交付窗口"),
    ("開標", "招标窗口"),
    ("开标", "招标窗口"),
    ("招标", "招标窗口"),
    ("立项", "立项窗口"),
    ("試點", "试点切入"),
    ("试点", "试点切入"),
    ("预算", "预算窗口"),
)


def summary_contains_output_noise(value: str) -> bool:
    runtime = scope_entity_runtime_functions()
    normalized = normalize_text(value)
    if not normalized:
        return False
    if len(normalized) > 320 or looks_like_source_artifact_text(normalized):
        return True
    if any(token in normalized for token in FIELD_ROW_NOISE_TOKENS):
        return True
    if any(token in normalized for token in ("CSDN博客", "腾讯新闻", "文章标签", "报告共计", "中国政府网政策/讲话")):
        return True
    for candidate in extract_rank_entity_candidates(normalized)[:6]:
        cleaned = strip_entity_leading_noise(candidate)
        if not cleaned or runtime.looks_like_scope_prompt_noise(cleaned) or looks_like_placeholder_entity_name(cleaned):
            return True
    return False


def concrete_rows(values: Iterable[str]) -> list[str]:
    return [normalize_text(value) for value in values if normalize_text(value) and not looks_like_insufficient(value)]


def entity_display_labels(values: Iterable[str], *, limit: int = 2) -> list[str]:
    runtime = scope_entity_runtime_functions()
    labels: list[str] = []
    for value in values:
        normalized = normalize_text(value)
        if not normalized or looks_like_insufficient(normalized):
            continue
        if "待验证" in normalized or "待驗證" in normalized:
            continue
        if looks_like_source_artifact_text(normalized):
            continue
        if any(token in normalized for token in SUMMARY_GUIDANCE_TOKENS):
            continue
        entity_name = runtime.extract_rank_entity_name(normalized) or fallback_entity_name_from_row(normalized)
        label = strip_entity_leading_noise(entity_name or normalized.split("：", 1)[0].split(":", 1)[0])
        if (
            not label
            or looks_like_fragment_entity_name(label)
            or contains_low_value_entity_token(label)
            or looks_like_placeholder_entity_name(label)
            or runtime.looks_like_scope_prompt_noise(label)
        ):
            continue
        labels.append(label)
    return dedupe_strings(labels, limit)


def research_result_needs_override(result: ResearchReportResult) -> bool:
    title = normalize_text(result.report_title).lower()
    summary = normalize_text(result.executive_summary).lower()
    return (
        title in {"研究主题待确认", "研究主題待確認", "research topic pending"}
        or looks_like_insufficient(summary)
        or len(concrete_rows(result.target_accounts)) < 2
        or len(concrete_rows(result.competitor_profiles)) < 2
    )


def looks_like_bad_report_title(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return True
    lowered = normalized.lower()
    if re.match(r"^(19|20)\d{2}", normalized) or len(normalized) > 42:
        return True
    if any(token in normalized for token in ENTITY_INVALID_PHRASE_TOKENS):
        return True
    if any(token in normalized for token in ("当前证据不足", "当前證據不足", "建议", "建議", "报告", "研报", "研究主题待确认")):
        return True
    if lowered.startswith(("本次", "当前", "建议", "research", "report")):
        return True
    if normalized.count("：") > 1 or normalized.count(":") > 1:
        return True
    return any(token in normalized for token in ("社区", "服务", "系统")) and not any(
        token in normalized for token in ("公司", "集团", "中心", "平台", "场景", "赛道")
    )


def is_theme_aligned_report_title(
    value: str,
    *,
    scope_hints: dict[str, object],
    keyword: str,
    research_focus: str | None,
) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    runtime = scope_entity_runtime_functions()
    theme_labels = runtime.theme_labels_from_scope(scope_hints, keyword=keyword, research_focus=research_focus)
    if not theme_labels:
        return True
    scope_text = normalize_text(" ".join([keyword, research_focus or "", str(scope_hints.get("anchor_text", ""))]))
    for theme_label in theme_labels:
        blocked_tokens = THEME_ENTITY_BLOCK_TOKENS.get(theme_label, {}).get("target", ())
        if any(token in normalized for token in blocked_tokens) and not any(token in scope_text for token in blocked_tokens):
            return False
    return True


def sanitize_title_scope_token(value: str) -> str:
    runtime = scope_entity_runtime_functions()
    normalized = normalize_text(value)
    if not normalized or runtime.looks_like_scope_prompt_noise(normalized):
        return ""
    if looks_like_fragment_entity_name(normalized) or contains_low_value_entity_token(normalized):
        return ""
    compact = normalized
    for prefix in ("优先关注", "優先關注", "重点关注", "重點關注", "锁定", "鎖定"):
        if compact.startswith(prefix):
            compact = normalize_text(compact[len(prefix):])
    for token in TITLE_SCOPE_GENERIC_TOKENS:
        compact = compact.replace(token, "")
    compact = re.sub(r"(?:19|20)\d{2}年?", "", compact)
    compact = re.sub(r"[：:|｜/]+$", "", compact)
    compact = re.sub(r"\s+", "", compact)
    compact = strip_entity_leading_noise(compact)
    if (
        not compact
        or compact in GENERIC_FOCUS_TOKENS
        or looks_like_placeholder_entity_name(compact)
        or any(token in compact for token in GENERIC_SCOPE_CLIENT_TOKENS)
        or len(compact) > 18
    ):
        return ""
    return compact


def compress_title_segments(segments: Iterable[str], *, limit: int = 3) -> list[str]:
    cleaned: list[str] = []
    for item in segments:
        normalized = sanitize_title_scope_token(item)
        if not normalized or normalized in cleaned:
            continue
        cleaned.append(normalized)
        if len(cleaned) >= limit:
            break
    return cleaned


def pick_primary_stage_phrase(stage_rows: Iterable[str]) -> str:
    for row in stage_rows:
        normalized = normalize_text(row)
        if not normalized:
            continue
        for token, label in TITLE_STAGE_LABELS:
            if token in normalized:
                return label
    return ""


def pick_primary_scenario_hint(
    *,
    keyword: str,
    research_focus: str | None,
    regions: list[str],
    industries: list[str],
    company_anchors: list[str],
) -> str:
    runtime = scope_entity_runtime_functions()
    candidates: list[tuple[int, int, str]] = []
    excluded = {normalize_text(item) for item in [*regions, *industries, *company_anchors]}
    for token in runtime.extract_topic_anchor_terms(keyword, research_focus):
        normalized = sanitize_title_scope_token(token)
        if not normalized or normalized in excluded:
            continue
        score = min(len(normalized), 10)
        if any(priority in normalized for priority in SCENARIO_PRIORITY_TOKENS):
            score += 8
        if any(theme in normalized for theme in ("AI", "AIGC", "政务", "內容", "内容", "采购", "招标", "预算", "交付")):
            score += 3
        candidates.append((score, len(normalized), normalized))
    if not candidates:
        return ""
    candidates.sort(key=lambda item: (-item[0], -item[1], item[2]))
    return candidates[0][2]


def build_report_title_suffix(
    *, intelligence: dict[str, list[str]], selected_company_anchor: str, stage_hint: str, output_language: str
) -> str:
    budget_rows = summary_fact_rows(intelligence.get("budget_signals", []), limit=2)
    timeline_rows = summary_fact_rows(
        [*intelligence.get("tender_timeline", []), *intelligence.get("project_distribution", [])], limit=2
    )
    competitor_rows = entity_display_labels(intelligence.get("competitor_profiles", []), limit=2)
    partner_rows = entity_display_labels(intelligence.get("ecosystem_partners", []), limit=2)
    target_rows = entity_display_labels(intelligence.get("target_accounts", []), limit=2)
    if stage_hint:
        suffix = f"{stage_hint}与推进路径"
    elif budget_rows and (competitor_rows or partner_rows):
        suffix = "预算信号与切入策略"
    elif competitor_rows or partner_rows:
        suffix = "竞争格局与切入策略"
    elif selected_company_anchor or target_rows:
        suffix = "账户优先级与推进路径"
    elif budget_rows or timeline_rows:
        suffix = "进入窗口与推进路径"
    else:
        suffix = "重点机会与推进路径"
    english = (
        "Entry Window & Execution Path" if suffix in {
            "扩容窗口与推进路径", "交付窗口与推进路径", "招标窗口与推进路径", "立项窗口与推进路径",
            "试点切入与推进路径", "预算窗口与推进路径", "进入窗口与推进路径",
        } else "Budget Signals & Entry Strategy" if suffix == "预算信号与切入策略"
        else "Competition Landscape & Entry Strategy" if suffix == "竞争格局与切入策略"
        else "Account Priorities & Execution Path" if suffix == "账户优先级与推进路径"
        else "Priority Opportunities & Execution Path"
    )
    return localized_text(output_language, {"zh-CN": suffix, "zh-TW": suffix.replace("与", "與"), "en": english}, suffix)


def build_exec_summary_override(
    *,
    scope_anchor: str,
    accounts: list[str],
    budgets: list[str],
    competitors: list[str],
    partners: list[str],
    teams: list[str],
    output_language: str,
) -> str:
    conclusion_subject = "、".join(accounts[:2]) if accounts else scope_anchor
    budget_anchor = next((item for item in budgets if is_actionable_budget_row(item)), "")
    team_anchor = teams[0] if teams else ""
    competitor_anchor = competitors[0] if competitors else ""
    partner_anchor = partners[0] if partners else ""
    if accounts and budget_anchor:
        conclusion_line = f"优先把{conclusion_subject}列为首批推进对象，当前公开信号已经出现{budget_anchor}这类预算或采购窗口。"
    elif accounts:
        conclusion_line = f"优先把{conclusion_subject}列为首批推进对象，先确认预算归口、业务牵头部门和进入窗口。"
    elif budget_anchor:
        conclusion_line = f"当前更适合围绕{scope_anchor}继续收敛到具体账户，尤其优先核验{budget_anchor}对应的项目窗口。"
    else:
        conclusion_line = f"当前应先把{scope_anchor}收敛到 1-2 个可验证账户，再进入更强的商业判断。"
    evidence_parts = dedupe_strings(
        [budget_anchor, team_anchor, f"竞品侧出现 {competitor_anchor}" if competitor_anchor else "", f"伙伴侧可借力 {partner_anchor}" if partner_anchor else ""],
        3,
    )
    evidence_line = f"公开证据目前主要集中在{'、'.join(evidence_parts)}。" if evidence_parts else "公开证据目前主要集中在范围锁定、账户筛选和进入窗口判断。"
    action_parts: list[str] = []
    if accounts:
        action_parts.append(
            f"先围绕{conclusion_subject}核验{team_anchor}是否是业务或预算牵头团队"
            if team_anchor else f"先围绕{conclusion_subject}补业务牵头部门和预算归口"
        )
    else:
        action_parts.append("先把主题收敛到 1-2 个可验证账户，再补预算归口和组织入口")
    if budget_anchor:
        action_parts.append(f"围绕“{budget_anchor}”倒排会前材料和拜访节奏")
    elif team_anchor:
        action_parts.append(f"从{team_anchor}对应的公开入口补联系人与会前材料")
    if competitor_anchor and partner_anchor:
        action_parts.append(f"准备针对{competitor_anchor}的差异化切口，并评估{partner_anchor}是否适合牵线")
    elif competitor_anchor:
        action_parts.append(f"准备针对{competitor_anchor}的差异化切口")
    elif partner_anchor:
        action_parts.append(f"评估{partner_anchor}是否适合作为牵线或联合推进伙伴")
    action_parts.append("把研判拆成两条主线：方案侧先定义场景、试点与扩容路径，打单侧先锁定账户、部门、预算与伙伴节奏")
    action_line = "；".join(dedupe_strings(action_parts, 3)) or "先锁定重点账户，再补预算归口、组织入口和首轮沟通材料。"
    if output_language.startswith("en"):
        evidence = ", ".join(evidence_parts) if evidence_parts else "account scoping, buyer qualification, and entry timing"
        return f"Prioritize {conclusion_subject} as the first execution target within {scope_anchor}. The strongest public signals currently cluster around {evidence}. The next step is to {action_line.rstrip('.')}."
    return f"{conclusion_line}{evidence_line}下一步建议{action_line.rstrip('。')}。"


def build_scope_summary_sentence(
    *,
    scope_anchor: str,
    accounts: list[str],
    budgets: list[str],
    competitors: list[str],
    partners: list[str],
    teams: list[str],
    output_language: str,
) -> str:
    clauses = [
        localized_text(
            output_language,
            {
                "zh-CN": f"本次研判锁定在 {scope_anchor} 范围内",
                "zh-TW": f"本次研判鎖定在 {scope_anchor} 範圍內",
                "en": f"This memo is constrained to {scope_anchor}",
            },
            f"本次研判锁定在 {scope_anchor} 范围内",
        )
    ]
    if accounts:
        clauses.append(localized_text(output_language, {"zh-CN": f"甲方线索优先收敛到 {'、'.join(accounts[:2])}", "zh-TW": f"甲方線索優先收斂到 {'、'.join(accounts[:2])}", "en": f"buyer-side leads converge around {' / '.join(accounts[:2])}"}, f"甲方线索优先收敛到 {'、'.join(accounts[:2])}"))
    if budgets:
        clauses.append(localized_text(output_language, {"zh-CN": f"预算与采购信号集中在 {'、'.join(budgets[:2])}", "zh-TW": f"預算與採購信號集中在 {'、'.join(budgets[:2])}", "en": f"budget and procurement signals cluster around {' / '.join(budgets[:2])}"}, f"预算与采购信号集中在 {'、'.join(budgets[:2])}"))
    if competitors:
        clauses.append(localized_text(output_language, {"zh-CN": f"高相关竞合对象包括 {'、'.join(competitors[:2])}", "zh-TW": f"高相關競合對象包括 {'、'.join(competitors[:2])}", "en": f"high-relevance competitors include {' / '.join(competitors[:2])}"}, f"高相关竞合对象包括 {'、'.join(competitors[:2])}"))
    if partners:
        clauses.append(localized_text(output_language, {"zh-CN": f"可用生态抓手集中在 {'、'.join(partners[:2])}", "zh-TW": f"可用生態抓手集中在 {'、'.join(partners[:2])}", "en": f"ecosystem leverage points include {' / '.join(partners[:2])}"}, f"可用生态抓手集中在 {'、'.join(partners[:2])}"))
    if teams:
        clauses.append(localized_text(output_language, {"zh-CN": f"活跃团队线索包括 {'、'.join(teams[:2])}", "zh-TW": f"活躍團隊線索包括 {'、'.join(teams[:2])}", "en": f"active team signals include {' / '.join(teams[:2])}"}, f"活跃团队线索包括 {'、'.join(teams[:2])}"))
    sentence = "，".join(clauses)
    return sentence + ("." if output_language.startswith("en") else "。")


def select_title_company_anchor(
    company_anchors: list[str], *, scope_hints: dict[str, object], keyword: str, research_focus: str | None
) -> str:
    runtime = scope_entity_runtime_functions()
    theme_labels = runtime.theme_labels_from_scope(scope_hints, keyword=keyword, research_focus=research_focus)
    for candidate in company_anchors:
        normalized = normalize_text(candidate)
        if normalized and is_theme_aligned_entity_name(normalized, role="target", theme_labels=theme_labels):
            return normalized
    return ""


def build_report_title_override(
    *, keyword: str, research_focus: str | None, scope_hints: dict[str, object], intelligence: dict[str, list[str]], output_language: str
) -> str:
    runtime = scope_entity_runtime_functions()
    regions = dedupe_strings([normalize_text(str(item)) for item in scope_hints.get("regions", []) if normalize_text(str(item))], 2)
    industries = dedupe_strings([normalize_text(str(item)) for item in scope_hints.get("industries", []) if normalize_text(str(item))], 2)
    theme_labels = runtime.theme_labels_from_scope(scope_hints, keyword=keyword, research_focus=research_focus)
    company_anchors = clean_scope_entity_names(
        [
            *[runtime.extract_rank_entity_name(item) for item in intelligence.get("target_accounts", []) if runtime.extract_rank_entity_name(item)],
            *[normalize_text(str(item)) for item in scope_hints.get("company_anchors", []) if normalize_text(str(item))],
        ],
        limit=4,
        theme_labels=theme_labels,
    )
    company_anchors = [
        item for item in company_anchors
        if normalize_text(item)
        and not looks_like_fragment_entity_name(item)
        and not contains_low_value_entity_token(item)
        and (item in KNOWN_LIGHTWEIGHT_ENTITY_NAMES or any(token in item for token in ENTITY_SUFFIX_TOKENS) or any(token in item for token in ("集团", "公司", "平台", "银行", "大学", "医院", "中心", "局", "委", "办")))
    ]
    selected_company_anchor = select_title_company_anchor(company_anchors, scope_hints=scope_hints, keyword=keyword, research_focus=research_focus)
    stage_rows = dedupe_strings([
        *[normalize_text(item) for item in intelligence.get("tender_timeline", []) if normalize_text(item)],
        *[normalize_text(item) for item in intelligence.get("project_distribution", []) if normalize_text(item)],
    ], 2)
    stage_hint = pick_primary_stage_phrase(stage_rows)
    scenario_hint = pick_primary_scenario_hint(keyword=keyword, research_focus=research_focus, regions=regions, industries=industries, company_anchors=company_anchors)
    scope_segments = compress_title_segments([*regions[:1], scenario_hint or (industries[0] if industries else ""), selected_company_anchor], limit=3)
    if not scope_segments:
        scope_segments = compress_title_segments([normalize_text(str(scope_hints.get("anchor_text", ""))), normalize_text(research_focus or ""), normalize_text(keyword)], limit=3)
    title_scope = "｜".join(scope_segments) or normalize_text(keyword)
    suffix = build_report_title_suffix(intelligence=intelligence, selected_company_anchor=selected_company_anchor, stage_hint=stage_hint, output_language=output_language)
    return localized_text(output_language, {"zh-CN": f"{title_scope}：{suffix}", "zh-TW": f"{title_scope}：{suffix}", "en": f"{title_scope}: {suffix}"}, f"{title_scope}：{suffix}")


def strategy_refinement_dependencies() -> StrategyRefinementDependencies:
    runtime = scope_entity_runtime_functions()
    return StrategyRefinementDependencies(
        theme_labels_from_scope=runtime.theme_labels_from_scope,
        filter_theme_aligned_rows=filter_theme_aligned_rows,
        entity_display_labels=entity_display_labels,
        summary_fact_rows=summary_fact_rows,
        is_actionable_budget_row=is_actionable_budget_row,
        research_result_needs_override=research_result_needs_override,
        company_intent_summary_needs_override=company_intent_summary_needs_override,
        summary_contains_output_noise=summary_contains_output_noise,
        build_report_title_override=build_report_title_override,
        build_scope_summary_sentence=build_scope_summary_sentence,
        looks_like_insufficient=looks_like_insufficient,
        looks_like_bad_executive_summary=lambda value: looks_like_bad_executive_summary(
            value,
            deps=ReportTextQualityDependencies(
                summary_contains_output_noise=summary_contains_output_noise,
                bad_executive_summary_phrases=BAD_EXEC_SUMMARY_PHRASES,
            ),
        ),
        build_exec_summary_override=build_exec_summary_override,
        concrete_rows=concrete_rows,
        dedupe_strings=dedupe_strings,
        get_strategy_llm_service=get_strategy_llm_service,
        parse_strategy_scope_response=parse_research_strategy_scope_response,
        parse_strategy_refine_response=parse_research_strategy_refine_response,
        merge_scope_hints=merge_scope_hints,
        looks_like_bad_report_title=looks_like_bad_report_title,
        is_theme_aligned_report_title=is_theme_aligned_report_title,
    )


def apply_topic_specific_overrides(
    result: ResearchReportResult,
    *,
    keyword: str,
    research_focus: str | None,
    output_language: str,
    scope_hints: dict[str, object],
    intelligence: dict[str, list[str]],
) -> ResearchReportResult:
    return apply_strategy_topic_specific_overrides(
        result,
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        scope_hints=scope_hints,
        intelligence=intelligence,
        deps=strategy_refinement_dependencies(),
    )
