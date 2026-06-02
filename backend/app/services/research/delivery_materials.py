from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
import re

from app.schemas.research import (
    ResearchCommercialSummaryOut,
    ResearchReportDocument,
    ResearchReportReadinessOut,
    ResearchReportSectionOut,
    ResearchReviewQueueItemOut,
    ResearchScenarioOut,
    ResearchSourceDiagnosticsOut,
    ResearchTechnicalAppendixOut,
)
from app.services.content_extractor import normalize_text
from app.services.language import localized_text


@dataclass(frozen=True, slots=True)
class DeliveryMaterialsDependencies:
    dedupe_strings: Callable[[Iterable[str], int], list[str]]
    theme_labels_from_scope: Callable[..., list[str]]
    entity_names_from_ranked: Callable[..., list[str]]
    looks_like_scope_prompt_noise: Callable[[str], bool]
    looks_like_placeholder_entity_name: Callable[[str], bool]
    looks_like_fragment_entity_name: Callable[[str], bool]
    contains_low_value_entity_token: Callable[[str], bool]
    is_trustworthy_scope_client_name: Callable[..., bool]
    is_theme_aligned_entity_name: Callable[..., bool]
    is_lightweight_entity_name: Callable[[str], bool]
    entity_display_labels: Callable[..., list[str]]
    is_actionable_budget_row: Callable[[str], bool]
    summary_fact_rows: Callable[..., list[str]]
    derive_entry_window: Callable[[ResearchReportDocument, str], str]
    truncate_sentence: Callable[[str, int], str]
    is_useful_public_contact_row: Callable[[str], bool]
    looks_like_placeholder_contact_row: Callable[[str], bool]
    looks_like_source_artifact_text: Callable[[str], bool]
    resolved_report_readiness: Callable[[ResearchReportDocument], ResearchReportReadinessOut]
    is_low_signal_execution_report: Callable[[ResearchReportDocument], bool]
    field_row_noise_tokens: tuple[str, ...]


def build_commercial_summary(
    report: ResearchReportDocument,
    *,
    deps: DeliveryMaterialsDependencies,
) -> ResearchCommercialSummaryOut:
    if deps.is_low_signal_execution_report(report):
        output_language = getattr(report, "output_language", "zh-CN")
        return ResearchCommercialSummaryOut(
            account_focus=[],
            budget_signal="",
            entry_window="",
            competition_or_partner="",
            next_action=localized_text(
                output_language,
                {
                    "zh-CN": "先补官网、公告、采购和联系人线索，再决定是否进入正式推进。",
                    "zh-TW": "先補官網、公告、採購與聯絡人線索，再決定是否進入正式推進。",
                    "en": "Add official pages, notices, procurement records, and contact evidence before deciding whether to enter formal execution.",
                },
                "先补官网、公告、采购和联系人线索，再决定是否进入正式推进。",
            ),
        )
    diagnostics = report.source_diagnostics if getattr(report, "source_diagnostics", None) else ResearchSourceDiagnosticsOut()
    theme_labels = deps.theme_labels_from_scope(
        {
            "industries": list(diagnostics.scope_industries),
            "regions": list(diagnostics.scope_regions),
            "clients": list(diagnostics.scope_clients),
        },
        keyword=report.keyword,
        research_focus=report.research_focus,
    )
    account_focus = deps.dedupe_strings(
        [
            normalize_text(name)
            for name in [
                *deps.entity_names_from_ranked(report.top_target_accounts, report.target_accounts, limit=3),
                *(normalize_text(item) for item in report.target_accounts if normalize_text(item)),
            ]
            if normalize_text(name)
            and not deps.looks_like_scope_prompt_noise(normalize_text(name))
            and not deps.looks_like_placeholder_entity_name(normalize_text(name))
            and not deps.looks_like_fragment_entity_name(normalize_text(name))
            and not deps.contains_low_value_entity_token(normalize_text(name))
            and (
                deps.is_trustworthy_scope_client_name(normalize_text(name), theme_labels=theme_labels)
                or deps.is_theme_aligned_entity_name(normalize_text(name), role="target", theme_labels=theme_labels)
                or deps.is_lightweight_entity_name(normalize_text(name))
            )
        ],
        3,
    )
    competitor_names = deps.entity_display_labels(
        [
            *(normalize_text(item.name) for item in report.top_competitors if normalize_text(item.name)),
            *(normalize_text(item) for item in report.competitor_profiles if normalize_text(item)),
        ],
        limit=2,
    )
    partner_names = deps.entity_display_labels(
        [
            *(normalize_text(item.name) for item in report.top_ecosystem_partners if normalize_text(item.name)),
            *(normalize_text(item) for item in report.ecosystem_partners if normalize_text(item)),
        ],
        limit=2,
    )
    competition_or_partner_parts: list[str] = []
    if competitor_names:
        competition_or_partner_parts.append(f"竞品侧重点关注 {'、'.join(competitor_names[:2])}")
    if partner_names:
        competition_or_partner_parts.append(f"伙伴侧可优先联动 {'、'.join(partner_names[:2])}")
    competition_or_partner = "；".join(competition_or_partner_parts)
    budget_signal_rows = [row for row in report.budget_signals if deps.is_actionable_budget_row(row)]
    budget_signal = normalize_text(
        (
            deps.summary_fact_rows(budget_signal_rows, limit=1)
            or deps.summary_fact_rows(report.project_distribution, limit=1)
            or [""]
        )[0]
    )
    entry_window = normalize_text((report.tender_timeline or [""])[0]) or deps.derive_entry_window(
        report,
        report.output_language,
    )
    primary_accounts = "、".join(account_focus[:2])
    department_hint = deps.truncate_sentence(
        normalize_text((report.target_departments or report.account_team_signals or [""])[0]),
        56,
    )
    contact_rows = [
        row
        for row in report.public_contact_channels
        if deps.is_useful_public_contact_row(row) and not deps.looks_like_placeholder_contact_row(row)
    ]
    contact_hint = deps.truncate_sentence(normalize_text((contact_rows or [""])[0]), 56)
    benchmark_rows = [
        row
        for row in report.benchmark_cases
        if normalize_text(row)
        and not deps.looks_like_source_artifact_text(row)
        and not any(token in normalize_text(row) for token in deps.field_row_noise_tokens)
    ]
    benchmark_hint = deps.truncate_sentence(normalize_text((benchmark_rows or [""])[0]), 56)
    next_action_steps: list[str] = []
    if account_focus:
        if department_hint:
            next_action_steps.append(f"先围绕{primary_accounts}锁定{department_hint}这类业务或预算牵头部门")
        else:
            next_action_steps.append(f"先围绕{primary_accounts}确认业务牵头部门和预算归口")
    else:
        next_action_steps.append("先把主题收敛到 1-2 个重点账户，再补业务牵头部门和预算归口")
    if budget_signal:
        next_action_steps.append(f"结合“{budget_signal}”倒排会前材料和拜访节奏")
    elif entry_window:
        next_action_steps.append(f"围绕“{entry_window}”倒排接触窗口和方案节奏")
    if contact_hint:
        next_action_steps.append(f"同步核验{contact_hint}等公开触达入口")
    elif benchmark_hint:
        next_action_steps.append(f"首轮沟通带上“{benchmark_hint}”这类标杆案例")
    if competitor_names and partner_names:
        next_action_steps.append(f"准备针对{competitor_names[0]}的差异化切口，并评估{partner_names[0]}是否适合牵线")
    elif competitor_names:
        next_action_steps.append(f"准备针对{competitor_names[0]}的差异化切口")
    elif partner_names:
        next_action_steps.append(f"评估{partner_names[0]}是否适合作为牵线或联合推进伙伴")
    next_action = deps.truncate_sentence("；".join(deps.dedupe_strings(next_action_steps, 3)) or "", 132)
    if next_action and not next_action.endswith(("。", ".", "!", "！", "?", "？")):
        next_action = f"{next_action}。"
    if not next_action and account_focus:
        next_action = f"围绕{account_focus[0]}继续补预算归口、组织入口与联系人。"
    return ResearchCommercialSummaryOut(
        account_focus=account_focus,
        budget_signal=budget_signal,
        entry_window=entry_window,
        competition_or_partner=competition_or_partner,
        next_action=next_action,
    )


def build_technical_appendix(
    report: ResearchReportDocument,
    *,
    deps: DeliveryMaterialsDependencies,
) -> ResearchTechnicalAppendixOut:
    diagnostics = report.source_diagnostics
    readiness = deps.resolved_report_readiness(report)
    output_language = getattr(report, "output_language", "zh-CN")
    account_focus = deps.dedupe_strings(
        [
            *(normalize_text(item.name) for item in report.top_target_accounts if normalize_text(item.name)),
            *(normalize_text(item) for item in report.target_accounts if normalize_text(item)),
        ],
        3,
    )
    key_assumptions = deps.dedupe_strings(
        [
            (
                f"当前判断默认以 {'/'.join(account_focus[:2])} 作为优先进入对象。"
                if account_focus
                else "当前判断默认先把行业主题收敛到可验证的具体账户。"
            ),
            (
                f"公开源口径以 {round(float(diagnostics.official_source_ratio or 0.0) * 100)}% 官方源占比为当前可信度基线。"
                if report.source_count
                else "当前仍需补公开源，尤其是官网、公告和采购信息。"
            ),
            (
                f"当前时间判断默认以 {normalize_text((report.tender_timeline or report.strategic_directions or ['近期预算窗口'])[0])} 为主要进入窗口。"
                if report.tender_timeline or report.strategic_directions
                else "当前仍默认预算窗口未完全确认，进入节奏需继续验证。"
            ),
            "本研判仅基于公开网页、公告、政策、行业媒体和浏览器可获取正文，不包含未授权后台数据。",
        ],
        4,
    )
    scenario_comparison = [
        ResearchScenarioOut(
            name="乐观情景",
            summary=(
                "预算与部门口径被进一步确认，且官方源继续补强。"
                if report.budget_signals or report.public_contact_channels
                else "下一轮公开源补强后，出现更明确的预算和组织入口。"
            ),
            implication="可直接进入账户计划、伙伴绑定和 close plan 执行。",
        ),
        ResearchScenarioOut(
            name="基准情景",
            summary=(
                "当前以候选推进为主，边推进边补证。"
                if readiness.status != "ready"
                else "当前已具备首轮推进条件，但仍需同步补证。"
            ),
            implication="适合先做会前简报、部门映射和公开触达，再决定是否进入更重资源投入。",
        ),
        ResearchScenarioOut(
            name="保守情景",
            summary="若预算、联系人或官方源迟迟无法补齐，则当前结论需要降级。",
            implication="保留为候选账户与审查队列，不建议直接当作最终销售/咨询判断。",
        ),
    ]
    limitations = deps.dedupe_strings(
        [
            *(f"仍缺关键维度：{axis}" for axis in readiness.missing_axes[:3]),
            (
                f"官方源占比仅 {round(float(diagnostics.official_source_ratio or 0.0) * 100)}%，仍有继续补强空间。"
                if float(diagnostics.official_source_ratio or 0.0) < 0.3
                else ""
            ),
            "部分账户、伙伴或竞品仍来自公开线索推断，需要进一步做交叉核验。",
            (
                "当前公开联系人不足，部分行动建议仍以组织入口和部门推断为主。"
                if not report.public_contact_channels
                else ""
            ),
        ],
        4,
    )
    technical_appendix = deps.dedupe_strings(
        [
            f"检索计划：{'；'.join(report.query_plan[:4])}" if report.query_plan else "",
            (
                f"来源结构：共保留 {report.source_count} 条来源，官方源 {diagnostics.source_tier_counts.get('official', 0)} 条，媒体源 {diagnostics.source_tier_counts.get('media', 0)} 条，聚合源 {diagnostics.source_tier_counts.get('aggregate', 0)} 条。"
            ),
            (
                f"Pipeline：{diagnostics.pipeline_summary or '取数 -> 清洗 -> 分析'}；取数 {next((stage.value for stage in diagnostics.pipeline_stages if stage.key == 'fetch'), 0)}，清洗 {next((stage.value for stage in diagnostics.pipeline_stages if stage.key == 'clean'), 0)}，分析 {next((stage.value for stage in diagnostics.pipeline_stages if stage.key == 'analyze'), 0)}。"
            ),
            (
                f"实体归一：共识别 {diagnostics.normalized_entity_count} 个实体，其中甲方 {diagnostics.normalized_target_count} 个、竞品 {diagnostics.normalized_competitor_count} 个、伙伴 {diagnostics.normalized_partner_count} 个。"
            ),
            localized_text(
                output_language,
                {
                    "zh-CN": "边界说明：不绕过登录、付费墙或未授权后台数据；若证据不足会明确降级或进入审查队列。",
                    "zh-TW": "邊界說明：不繞過登入、付費牆或未授權後台資料；若證據不足會明確降級或進入審查佇列。",
                    "en": "Boundary: no login, paywall, or unauthorized backend bypass is used; weak evidence is explicitly downgraded or queued for review.",
                },
                "边界说明：不绕过登录、付费墙或未授权后台数据；若证据不足会明确降级或进入审查队列。",
            ),
        ],
        5,
    )
    return ResearchTechnicalAppendixOut(
        key_assumptions=key_assumptions,
        scenario_comparison=scenario_comparison,
        limitations=limitations,
        technical_appendix=technical_appendix,
    )


def review_queue_severity(section: ResearchReportSectionOut) -> str:
    if section.contradiction_detected or section.confidence_tone == "conflict":
        return "high"
    if not section.meets_evidence_quota or (section.evidence_count or 0) <= 0:
        return "medium"
    return "low"


def build_review_queue(
    report: ResearchReportDocument,
    *,
    deps: DeliveryMaterialsDependencies,
) -> list[ResearchReviewQueueItemOut]:
    items: list[ResearchReviewQueueItemOut] = []
    readiness = deps.resolved_report_readiness(report)
    for section in report.sections:
        severity = review_queue_severity(section)
        should_include = (
            severity == "high"
            or not section.meets_evidence_quota
            or section.confidence_tone in {"low", "conflict"}
        )
        if not should_include:
            continue
        summary_parts = [
            normalize_text(section.contradiction_note),
            normalize_text(section.quota_note),
            normalize_text(section.confidence_reason),
        ]
        recommended_action = (
            "优先补官方源与原始公告，再对冲突结论做二次审查。"
            if severity == "high"
            else "优先补强该章节的官方源、原始网页和账户级证据，再决定是否保留结论。"
        )
        items.append(
            ResearchReviewQueueItemOut(
                id=re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", normalize_text(f"review-{section.title}").lower()).strip("-")
                or "review-section",
                section_title=section.title,
                severity=severity,
                summary="；".join(part for part in summary_parts if part) or f"{section.title} 仍需继续补证。",
                recommended_action=recommended_action,
                evidence_links=list(section.evidence_links[:3]),
            )
        )
    if readiness.status != "ready" and readiness.missing_axes:
        items.append(
            ResearchReviewQueueItemOut(
                id="review-report-readiness",
                section_title="总体待核验",
                severity="medium",
                summary=f"当前仍缺关键维度：{' / '.join(readiness.missing_axes[:3])}",
                recommended_action="先补关键维度，再决定是否进入正式推进；不要把当前版本当作最终结论。",
                evidence_links=[],
            )
        )
    deduped: list[ResearchReviewQueueItemOut] = []
    seen_ids: set[str] = set()
    for item in items:
        if item.id in seen_ids:
            continue
        seen_ids.add(item.id)
        deduped.append(item)
    severity_order = {"high": 0, "medium": 1, "low": 2}
    deduped.sort(key=lambda item: (severity_order.get(item.severity, 3), item.section_title))
    return deduped[:6]
