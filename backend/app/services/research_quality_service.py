from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from app.schemas.research import (
    ResearchIndustryMethodologyOut,
    ResearchMethodologyAxisOut,
    ResearchQualityDimensionOut,
    ResearchQualityProfileOut,
    ResearchReportDocument,
    ResearchSectionEvidencePackOut,
)
from app.services.content_extractor import normalize_text


@dataclass(frozen=True, slots=True)
class _MethodologyAxisSpec:
    key: str
    label: str
    checkpoints: tuple[str, ...]
    tokens: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _MethodologySpec:
    industry_key: str
    industry_label: str
    framework_name: str
    summary: str
    match_tokens: tuple[str, ...]
    axes: tuple[_MethodologyAxisSpec, ...]
    recommended_questions: tuple[str, ...]


def _dedupe_strings(values: Iterable[str], limit: int = 8) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for value in values:
        normalized = normalize_text(str(value or ""))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        rows.append(normalized)
        if len(rows) >= limit:
            break
    return rows


_METHODOLOGIES: tuple[_MethodologySpec, ...] = (
    _MethodologySpec(
        industry_key="government_cloud",
        industry_label="政务云 / 数字政府",
        framework_name="政策-预算-招采-部门-生态-风险六段式",
        summary="优先核验政策牵引、财政/预算窗口、采购路径、业务牵头部门、生态伙伴和合规交付风险。",
        match_tokens=("政务云", "数字政府", "一网通办", "数据局", "政务服务", "电子政务", "公共资源交易"),
        axes=(
            _MethodologyAxisSpec("policy_fit", "政策牵引", ("政策/规划口径", "领导或主管部门关注点", "区域数字化任务"), ("政策", "规划", "意见", "方案", "领导", "主管部门")),
            _MethodologyAxisSpec("budget_procurement", "预算与招采", ("预算来源", "采购意向/招标/中标", "时间窗口"), ("预算", "采购", "招标", "中标", "采购意向", "公共资源")),
            _MethodologyAxisSpec("buyer_org", "组织入口", ("业主单位", "业务牵头部门", "公开联系入口"), ("数据局", "大数据中心", "采购中心", "办公室", "联系人", "联系方式")),
            _MethodologyAxisSpec("solution_fit", "方案切口", ("云平台/数据平台场景", "安全合规要求", "现有系统迁移或扩容"), ("云", "数据", "安全", "等保", "信创", "平台", "扩容")),
            _MethodologyAxisSpec("ecosystem", "生态与竞合", ("集成商/运营商/云厂商", "本地伙伴", "既有中标方"), ("运营商", "集成商", "生态", "伙伴", "中标方", "供应商")),
            _MethodologyAxisSpec("delivery_risk", "落地风险", ("预算不确定性", "合规/安全边界", "跨部门协调风险"), ("风险", "合规", "安全", "跨部门", "延期", "不确定")),
        ),
        recommended_questions=(
            "是否有官方政策、预算或采购意向能支撑该账户进入窗口？",
            "业务牵头部门和采购归口是否被公开来源确认？",
            "现有中标方、运营商或本地伙伴是否影响切入路径？",
        ),
    ),
    _MethodologySpec(
        industry_key="compute_llm",
        industry_label="算力 / 大模型基础设施",
        framework_name="供给-需求-场景-成本-生态-合规六段式",
        summary="围绕算力供给、模型/应用需求、成本结构、数据安全、生态合作和采购窗口做交叉验证。",
        match_tokens=("算力", "大模型", "智算", "GPU", "AI Infra", "模型训练", "推理", "智能超参数"),
        axes=(
            _MethodologyAxisSpec("capacity_supply", "算力供给", ("资源规模", "GPU/集群/机房", "交付周期"), ("算力", "GPU", "集群", "智算", "机房", "数据中心")),
            _MethodologyAxisSpec("demand_scenario", "需求场景", ("训练/推理需求", "行业应用场景", "业务负载"), ("训练", "推理", "模型", "应用", "场景", "负载")),
            _MethodologyAxisSpec("cost_budget", "成本与预算", ("CAPEX/OPEX", "采购或租赁模式", "预算窗口"), ("预算", "采购", "租赁", "成本", "投资", "CAPEX", "OPEX")),
            _MethodologyAxisSpec("data_security", "数据与安全", ("数据来源", "安全合规", "私有化/混合云边界"), ("数据", "安全", "合规", "私有化", "混合云", "等保")),
            _MethodologyAxisSpec("ecosystem", "生态合作", ("芯片/云/模型/集成伙伴", "既有供应商", "联合方案"), ("芯片", "云厂商", "模型", "生态", "伙伴", "供应商")),
            _MethodologyAxisSpec("business_case", "商业闭环", ("ROI", "业务价值", "规模化路径"), ("ROI", "收益", "价值", "商业化", "规模化", "降本")),
        ),
        recommended_questions=(
            "目标账户的算力需求是训练、推理还是行业应用落地？",
            "预算更可能来自采购、租赁、项目制还是平台建设？",
            "数据安全和私有化部署是否构成必须满足的进入条件？",
        ),
    ),
    _MethodologySpec(
        industry_key="ai_application",
        industry_label="AI 应用 / 内容与行业智能",
        framework_name="场景-用户-产品-商业化-竞品-风险六段式",
        summary="先确认应用场景和目标用户，再核验产品能力、商业化路径、竞品替代点和内容/合规风险。",
        match_tokens=("AI应用", "AIGC", "AI漫剧", "智能体", "Agent", "内容平台", "多模态", "应用开发"),
        axes=(
            _MethodologyAxisSpec("scenario", "应用场景", ("使用场景", "用户/部门", "业务痛点"), ("场景", "用户", "部门", "痛点", "需求")),
            _MethodologyAxisSpec("product_fit", "产品匹配", ("功能能力", "部署形态", "集成接口"), ("产品", "能力", "部署", "接口", "平台", "功能")),
            _MethodologyAxisSpec("commercialization", "商业化", ("付费模式", "预算来源", "规模化路径"), ("商业化", "付费", "预算", "采购", "规模化", "收入")),
            _MethodologyAxisSpec("competition", "竞品替代", ("竞品方案", "差异化", "替代成本"), ("竞品", "竞争", "替代", "差异化", "对手")),
            _MethodologyAxisSpec("ecosystem", "渠道生态", ("渠道/平台/伙伴", "内容或行业资源", "联合方案"), ("渠道", "生态", "伙伴", "平台", "联合")),
            _MethodologyAxisSpec("risk", "风险边界", ("内容/版权/合规", "模型幻觉", "交付稳定性"), ("风险", "版权", "合规", "幻觉", "稳定性", "安全")),
        ),
        recommended_questions=(
            "这个 AI 应用是降本、增收还是增强客户体验？",
            "目标账户已有竞品或替代方案是什么？",
            "商业化证据来自合同、采购、用户增长还是合作入口？",
        ),
    ),
)

_GENERIC_METHODOLOGY = _MethodologySpec(
    industry_key="generic",
    industry_label="通用 B2B 解决方案研究",
    framework_name="市场-账户-预算-竞争-落地五段式",
    summary="用市场背景收敛机会，再用具体账户、预算窗口、竞争态势和落地路径验证是否值得推进。",
    match_tokens=(),
    axes=(
        _MethodologyAxisSpec("market_context", "市场与政策背景", ("趋势/政策", "需求变化", "关键约束"), ("市场", "政策", "趋势", "需求")),
        _MethodologyAxisSpec("target_account", "目标账户", ("具体客户/机构", "业务场景", "组织入口"), ("客户", "甲方", "账户", "部门", "联系人")),
        _MethodologyAxisSpec("budget_window", "预算窗口", ("预算/采购", "项目期次", "时间节点"), ("预算", "采购", "招标", "项目", "时间")),
        _MethodologyAxisSpec("competition", "竞品与伙伴", ("竞品", "伙伴", "替代方案"), ("竞品", "竞争", "伙伴", "生态", "供应商")),
        _MethodologyAxisSpec("execution", "落地动作", ("下一步动作", "风险", "验证清单"), ("下一步", "行动", "风险", "验证", "补证")),
    ),
    recommended_questions=(
        "是否已经收敛到具体账户和业务场景？",
        "预算、采购或进入窗口是否被公开来源支撑？",
        "下一步动作是否足够具体，能否转化为会前准备或拜访计划？",
    ),
)


def _report_text(report: ResearchReportDocument) -> str:
    section_text = "；".join(
        "；".join([section.title, *section.items, section.evidence_note, section.insufficiency_summary])
        for section in report.sections
    )
    source_text = "；".join(
        "；".join([source.title, source.snippet, source.source_label or "", source.source_tier or ""])
        for source in report.sources
    )
    entity_text = "；".join(
        [
            *report.target_accounts,
            *report.target_departments,
            *report.public_contact_channels,
            *report.account_team_signals,
            *report.budget_signals,
            *report.project_distribution,
            *report.strategic_directions,
            *report.tender_timeline,
            *report.ecosystem_partners,
            *report.competitor_profiles,
            *report.benchmark_cases,
            *report.competition_analysis,
        ]
    )
    return normalize_text(
        "；".join(
            [
                report.keyword,
                report.research_focus or "",
                report.report_title,
                report.executive_summary,
                report.consulting_angle,
                section_text,
                source_text,
                entity_text,
            ]
        )
    )


def _select_methodology(report: ResearchReportDocument) -> _MethodologySpec:
    diagnostics = report.source_diagnostics
    haystack = _report_text(report)
    scoped_text = normalize_text(
        "；".join([*diagnostics.scope_industries, *diagnostics.matched_theme_labels, report.keyword, report.research_focus or ""])
    )
    scored: list[tuple[int, _MethodologySpec]] = []
    for spec in _METHODOLOGIES:
        score = 0
        for token in spec.match_tokens:
            if token and token in scoped_text:
                score += 3
            elif token and token in haystack:
                score += 1
        scored.append((score, spec))
    scored.sort(key=lambda item: item[0], reverse=True)
    return scored[0][1] if scored and scored[0][0] > 0 else _GENERIC_METHODOLOGY


def _axis_to_output(axis: _MethodologyAxisSpec, report_text: str) -> ResearchMethodologyAxisOut:
    passed = [checkpoint for checkpoint in axis.checkpoints if any(token in report_text for token in axis.tokens)]
    if not passed and any(token in report_text for token in axis.tokens):
        passed = list(axis.checkpoints[:1])
    missing = [checkpoint for checkpoint in axis.checkpoints if checkpoint not in passed]
    implication = (
        f"{axis.label}已有初步证据，可用于推进判断。"
        if len(passed) >= max(1, len(axis.checkpoints) // 2)
        else f"{axis.label}仍偏弱，下一轮需要优先补证。"
    )
    return ResearchMethodologyAxisOut(
        key=axis.key,
        label=axis.label,
        checkpoints=list(axis.checkpoints),
        passed=_dedupe_strings(passed, 4),
        missing=_dedupe_strings(missing, 4),
        implication=implication,
    )


def _build_methodology(report: ResearchReportDocument) -> ResearchIndustryMethodologyOut:
    spec = _select_methodology(report)
    report_text = _report_text(report)
    return ResearchIndustryMethodologyOut(
        industry_key=spec.industry_key,
        industry_label=spec.industry_label,
        framework_name=spec.framework_name,
        summary=spec.summary,
        axes=[_axis_to_output(axis, report_text) for axis in spec.axes],
        recommended_questions=list(spec.recommended_questions),
    )


def _dimension_status(score: int) -> str:
    if score >= 75:
        return "strong"
    if score >= 55:
        return "usable"
    return "weak"


def _score_from_flags(*flags: bool, base: int = 18, weight: int = 12, cap: int = 96) -> int:
    return max(8, min(cap, base + sum(weight for flag in flags if flag)))


def _build_section_evidence_packs(report: ResearchReportDocument) -> list[ResearchSectionEvidencePackOut]:
    packs: list[ResearchSectionEvidencePackOut] = []
    for section in report.sections:
        official_count = int((section.source_tier_counts or {}).get("official", 0) or 0)
        evidence_count = int(section.evidence_count or len(section.evidence_links or []))
        quota_gap = int(section.quota_gap or 0)
        support_score = 20
        support_score += min(30, evidence_count * 10)
        support_score += min(24, official_count * 12)
        if section.meets_evidence_quota:
            support_score += 16
        if section.status == "ready":
            support_score += 10
        if section.contradiction_detected:
            support_score -= 24
        support_score = max(0, min(100, support_score))
        risks = _dedupe_strings(
            [
                *(section.insufficiency_reasons or []),
                section.contradiction_note if section.contradiction_detected else "",
                "官方证据不足" if official_count <= 0 else "",
                "未达到章节证据配额" if quota_gap > 0 else "",
            ],
            4,
        )
        next_steps = _dedupe_strings(
            [
                *(section.next_verification_steps or []),
                "补充该章节对应的官网、公告、采购或原始网页。" if official_count <= 0 else "",
                "补齐至少一条能直接支撑该章节结论的证据。" if evidence_count <= 0 else "",
            ],
            4,
        )
        packs.append(
            ResearchSectionEvidencePackOut(
                section_title=section.title,
                status=section.status,
                support_score=support_score,
                evidence_count=evidence_count,
                official_evidence_count=official_count,
                quota_gap=quota_gap,
                source_titles=_dedupe_strings([link.title for link in section.evidence_links if link.title], 3),
                risks=risks,
                next_steps=next_steps,
            )
        )
    packs.sort(key=lambda item: (item.status != "needs_evidence", item.status != "degraded", -item.quota_gap, item.support_score))
    return packs[:8]


def _build_dimensions(
    report: ResearchReportDocument,
    methodology: ResearchIndustryMethodologyOut,
    section_packs: list[ResearchSectionEvidencePackOut],
) -> list[ResearchQualityDimensionOut]:
    diagnostics = report.source_diagnostics
    readiness = report.report_readiness
    passed_axis_count = sum(1 for axis in methodology.axes if len(axis.passed) >= max(1, len(axis.checkpoints) // 2))
    weak_section_count = sum(1 for pack in section_packs if pack.status != "ready")
    official_ratio = float(diagnostics.official_source_ratio or 0.0)
    supported_targets = len(diagnostics.supported_target_accounts or [])
    has_budget = bool(report.budget_signals or report.tender_timeline)
    has_contacts = bool(report.public_contact_channels or report.target_departments or report.account_team_signals)
    has_competition = bool(report.competitor_profiles or report.top_competitors or report.ecosystem_partners or report.top_ecosystem_partners)
    has_next_action = bool(report.commercial_summary.next_action or report.strategic_directions)
    professional_score = _score_from_flags(
        passed_axis_count >= max(3, len(methodology.axes) // 2),
        bool(report.technical_appendix.key_assumptions),
        bool(report.technical_appendix.scenario_comparison),
        weak_section_count <= 2,
        base=22,
        weight=16,
    )
    intelligence_score = _score_from_flags(
        supported_targets > 0,
        has_budget,
        has_contacts,
        has_competition,
        diagnostics.retrieval_quality in {"medium", "high"},
        base=18,
        weight=14,
    )
    action_score = _score_from_flags(
        readiness.actionable,
        bool(report.commercial_summary.account_focus),
        bool(report.commercial_summary.entry_window or report.tender_timeline),
        has_next_action,
        readiness.status in {"ready", "degraded"},
        base=18,
        weight=14,
    )
    evidence_score = _score_from_flags(
        report.source_count >= 6,
        official_ratio >= 0.25,
        diagnostics.evidence_mode in {"strong", "provisional"},
        readiness.evidence_gate_passed,
        weak_section_count <= 1,
        base=14,
        weight=15,
    )
    return [
        ResearchQualityDimensionOut(
            key="professional_rigor",
            label="专业严谨度",
            score=professional_score,
            status=_dimension_status(professional_score),
            summary=f"采用「{methodology.framework_name}」校验，{passed_axis_count}/{len(methodology.axes)} 个方法论维度已有支撑。",
            evidence=[axis.label for axis in methodology.axes if axis.passed][:4],
            next_steps=[f"补强{axis.label}：{' / '.join(axis.missing[:2])}" for axis in methodology.axes if axis.missing][:3],
        ),
        ResearchQualityDimensionOut(
            key="intelligence_value",
            label="情报价值",
            score=intelligence_score,
            status=_dimension_status(intelligence_score),
            summary="重点看目标账户、预算窗口、组织入口、竞品/伙伴和检索质量是否形成可交叉验证的情报。",
            evidence=_dedupe_strings(
                [
                    *(diagnostics.supported_target_accounts or []),
                    *(report.budget_signals[:2]),
                    *(report.target_departments[:2]),
                    *(report.competitor_profiles[:1]),
                    *(report.ecosystem_partners[:1]),
                ],
                5,
            ),
            next_steps=_dedupe_strings(
                [
                    "补目标账户正文支撑。" if supported_targets <= 0 else "",
                    "补预算、采购或时间窗口。" if not has_budget else "",
                    "补业务牵头部门、公开联系人或组织入口。" if not has_contacts else "",
                    "补竞品替代点或生态伙伴路径。" if not has_competition else "",
                ],
                4,
            ),
        ),
        ResearchQualityDimensionOut(
            key="actionability",
            label="行动可执行性",
            score=action_score,
            status=_dimension_status(action_score),
            summary="重点看是否能转成账户计划、会前材料、拜访切口和下一步补证动作。",
            evidence=_dedupe_strings(
                [
                    *(report.commercial_summary.account_focus or []),
                    report.commercial_summary.entry_window,
                    report.commercial_summary.next_action,
                ],
                4,
            ),
            next_steps=_dedupe_strings(
                [
                    *(readiness.next_verification_steps[:3]),
                    "把结论拆成 30/60/90 天推进动作。" if action_score < 75 else "",
                ],
                4,
            ),
        ),
        ResearchQualityDimensionOut(
            key="evidence_strength",
            label="证据强度",
            score=evidence_score,
            status=_dimension_status(evidence_score),
            summary=f"当前来源 {report.source_count} 条，官方源占比 {round(official_ratio * 100)}%，弱证据章节 {weak_section_count} 个。",
            evidence=_dedupe_strings(
                [
                    f"官方源 {diagnostics.source_tier_counts.get('official', 0)} 条",
                    f"严格主题命中 {diagnostics.strict_topic_source_count} 条",
                    diagnostics.evidence_mode_label,
                ],
                4,
            ),
            next_steps=_dedupe_strings(
                [
                    "补官方源占比到 25% 以上。" if official_ratio < 0.25 else "",
                    "补齐弱证据章节的原始来源。" if weak_section_count else "",
                    "增加多域名交叉验证。" if diagnostics.unique_domain_count < 3 else "",
                ],
                4,
            ),
        ),
    ]


def build_research_quality_profile(report: ResearchReportDocument) -> ResearchQualityProfileOut:
    methodology = _build_methodology(report)
    section_packs = _build_section_evidence_packs(report)
    dimensions = _build_dimensions(report, methodology, section_packs)
    scores = {dimension.key: int(dimension.score or 0) for dimension in dimensions}
    overall = round(
        scores.get("professional_rigor", 0) * 0.28
        + scores.get("intelligence_value", 0) * 0.32
        + scores.get("actionability", 0) * 0.22
        + scores.get("evidence_strength", 0) * 0.18
    )
    if overall >= 78 and all(score >= 65 for score in scores.values()):
        status = "high_value"
        headline = "当前研报具备较高专业度和情报推进价值，可进入正式打单/方案设计使用。"
    elif overall >= 55:
        status = "usable"
        headline = "当前研报可用于内部判断和候选推进，但仍需按缺口继续补证。"
    else:
        status = "needs_evidence"
        headline = "当前研报稳定性尚可，但专业支撑和情报价值不足，建议先补关键证据。"
    strengths = _dedupe_strings(
        [
            dimension.summary
            for dimension in dimensions
            if dimension.status in {"strong", "usable"} and dimension.evidence
        ],
        4,
    )
    gaps = _dedupe_strings(
        [
            *(f"{dimension.label}：{' / '.join(dimension.next_steps[:2])}" for dimension in dimensions if dimension.status == "weak"),
            *(f"{pack.section_title}：{' / '.join(pack.risks[:2])}" for pack in section_packs if pack.risks),
        ],
        6,
    )
    next_actions = _dedupe_strings(
        [
            *(step for dimension in dimensions for step in dimension.next_steps[:2]),
            *(step for pack in section_packs for step in pack.next_steps[:1]),
            *methodology.recommended_questions[:2],
        ],
        6,
    )
    return ResearchQualityProfileOut(
        overall_score=overall,
        status=status,
        headline=headline,
        professional_score=scores.get("professional_rigor", 0),
        intelligence_value_score=scores.get("intelligence_value", 0),
        actionability_score=scores.get("actionability", 0),
        evidence_score=scores.get("evidence_strength", 0),
        dimensions=dimensions,
        methodology=methodology,
        section_evidence_packs=section_packs,
        strengths=strengths,
        gaps=gaps,
        next_actions=next_actions,
    )
