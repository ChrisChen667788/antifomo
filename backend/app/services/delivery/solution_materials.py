from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.schemas.research import (
    ResearchAdvisoryArtifactOut,
    ResearchMarketIntelligencePackOut,
    ResearchReportDocument,
    ResearchSolutionDeliveryPackOut,
    ResearchSolutionOutlineSectionOut,
)
from app.services.content_extractor import normalize_text


@dataclass(slots=True)
class SolutionDeliveryOutlines:
    feasibility_outline: list[ResearchSolutionOutlineSectionOut]
    project_proposal_outline: list[ResearchSolutionOutlineSectionOut]
    client_ppt_outline: list[ResearchSolutionOutlineSectionOut]


def _dedupe_strings(values: Iterable[object], limit: int = 10) -> list[str]:
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


def _outline(title: str, bullets: Iterable[object]) -> ResearchSolutionOutlineSectionOut:
    return ResearchSolutionOutlineSectionOut(title=title, bullets=_dedupe_strings(bullets, limit=8))


def build_solution_delivery_outlines(
    report: ResearchReportDocument,
    *,
    market_pack: ResearchMarketIntelligencePackOut,
    scenario: str,
    target_customer: str,
    vertical_scene: str,
) -> SolutionDeliveryOutlines:
    feasibility_outline = [
        _outline("一、项目概况", [f"项目/场景：{scenario}", f"建议客户/业主：{target_customer or '待确认'}", f"垂直场景：{vertical_scene or '待确认'}"]),
        _outline("二、研究依据与近三年公开情报", [market_pack.source_scope_summary, *[item.project_name for item in market_pack.tender_projects[:4]], *market_pack.intelligence_gaps[:2]]),
        _outline("三、建设必要性与需求分析", [report.consulting_angle, *report.leadership_focus[:2], *report.budget_signals[:2]]),
        _outline("四、建设内容与技术方案", [*report.strategic_directions[:3], *[item.name for item in market_pack.product_catalog[:4]]]),
        _outline("五、投资估算与效益分析", [*report.budget_signals[:3], "结合近三年同类招采金额、产品模块和交付范围形成分档预算。"]),
        _outline("六、风险、边界与结论", [*report.technical_appendix.limitations[:3], *market_pack.intelligence_gaps[:2], report.commercial_summary.next_action]),
    ]
    project_proposal_outline = [
        _outline("一、项目背景", [report.executive_summary, market_pack.source_scope_summary]),
        _outline("二、建设目标", [f"围绕 {scenario} 建立可演示、可试点、可扩展的方案闭环。", *report.strategic_directions[:3]]),
        _outline("三、建设内容", [*report.project_distribution[:3], *[item.name for item in market_pack.product_catalog[:5]]]),
        _outline("四、实施计划", [*report.tender_timeline[:3], "建议分为调研确认、原型验证、试点上线、规模推广四阶段。"]),
        _outline("五、投资测算", [*report.budget_signals[:3], "按软件平台、模型/算力、集成实施、运营运维、培训推广拆分。"]),
        _outline("六、组织协同与风险控制", [*report.target_departments[:4], *report.competition_analysis[:3]]),
    ]
    client_ppt_outline = [
        _outline("1. 客户当前业务挑战", [report.executive_summary, vertical_scene]),
        _outline("2. 外部趋势与近三年招采参考", [*[item.project_name for item in market_pack.tender_projects[:4]], *market_pack.tender_keywords[:5]]),
        _outline("3. 建设目标与总体架构", [*report.strategic_directions[:3], "业务层、智能中台层、模型/数据层、安全运维层。"]),
        _outline("4. 核心功能与产品清单", [*[item.name for item in market_pack.product_catalog[:6]]]),
        _outline("5. 技术参数与交付边界", [*[param for item in market_pack.technical_parameter_catalog[:3] for param in item.technical_parameters[:2]]]),
        _outline("6. 实施路线与预算口径", [*report.tender_timeline[:3], *report.budget_signals[:3]]),
        _outline("7. 下一步共创计划", [report.commercial_summary.next_action, "客户确认范围后输出正式可研、建议书和对客汇报稿。"]),
    ]
    return SolutionDeliveryOutlines(
        feasibility_outline=feasibility_outline,
        project_proposal_outline=project_proposal_outline,
        client_ppt_outline=client_ppt_outline,
    )


def _artifact_markdown(
    *,
    title: str,
    audience: str,
    purpose: str,
    source_policy: str,
    sections: list[ResearchSolutionOutlineSectionOut],
) -> str:
    lines = [
        f"# {title}",
        "",
        f"- 受众: {audience}",
        f"- 用途: {purpose}",
        f"- 证据口径: {source_policy}",
        "",
    ]
    for section in sections:
        lines.append(f"## {section.title}")
        lines.extend([f"- {bullet}" for bullet in section.bullets])
        lines.append("")
    return "\n".join(lines).strip()


def build_advisory_artifacts(
    report: ResearchReportDocument,
    *,
    market_pack: ResearchMarketIntelligencePackOut,
    scenario: str,
    target_customer: str,
    vertical_scene: str,
    evidence_policy: str,
) -> list[ResearchAdvisoryArtifactOut]:
    customer = target_customer or (report.target_accounts[0] if report.target_accounts else "待确认客户")
    scene = vertical_scene or report.research_focus or scenario
    top_projects = [item.project_name for item in market_pack.tender_projects[:3]]
    top_requirements = [
        param
        for item in market_pack.technical_parameter_catalog[:4]
        for param in item.technical_parameters[:2]
    ]
    client_sections = [
        _outline("客户场景与触发信号", [f"目标客户：{customer}", f"场景：{scene}", report.executive_summary, *report.budget_signals[:2]]),
        _outline("可交流方案主张", [*report.strategic_directions[:3], *[item.name for item in market_pack.product_catalog[:4]], report.commercial_summary.next_action]),
        _outline("公开证据与边界", [market_pack.source_scope_summary, *top_projects, *market_pack.intelligence_gaps[:2]]),
        _outline("建议会议目标", ["确认牵头部门、试点范围、数据边界和预算口径。", "争取客户提供现有流程、系统接口和历史项目材料。"]),
    ]
    bidding_sections = [
        _outline("机会判断", [f"客户/业主：{customer}", f"场景：{scenario}", report.consulting_angle, *report.tender_timeline[:3]]),
        _outline("招采与竞标准备", [*[item.project_name for item in market_pack.tender_projects[:4]], *report.competition_analysis[:3], *market_pack.tender_keywords[:5]]),
        _outline("技术与资质关注", [*top_requirements, *report.technical_appendix.limitations[:2], "补齐投标资质、业绩案例、产品参数和安全合规说明。"]),
        _outline("投标准备动作", ["建立招标文件预审清单。", "准备技术偏离表、商务条款风险表和评分点响应矩阵。", report.commercial_summary.next_action]),
    ]
    execution_sections = [
        _outline("交付拆解", [f"一期建议聚焦：{scene}", *report.project_distribution[:3], *report.target_departments[:4]]),
        _outline("近期行动", ["7 日内完成客户访谈提纲、需求确认表和演示脚本。", "30 日内完成原型范围、预算测算和项目建议书初稿。", report.commercial_summary.next_action]),
        _outline("材料清单", ["客户 brief", "投标准备 memo", "需求访谈表", "方案架构页", "技术参数表", "风险与待核验清单"]),
        _outline("风险控制", [*market_pack.intelligence_gaps[:3], *report.technical_appendix.limitations[:3], "所有客户版结论保留来源或标注为假设。"]),
    ]
    specs = [
        (
            "client_brief",
            f"{customer} {scenario} 客户 brief",
            "客户业务负责人 / 信息化牵头部门",
            "用于客户初次交流、场景确认和下一步共创邀约。",
            client_sections,
        ),
        (
            "bidding_prep_memo",
            f"{customer} {scenario} 投标准备 memo",
            "售前、投标、解决方案和商务团队",
            "用于招采前研判、评分点预判、材料责任分工。",
            bidding_sections,
        ),
        (
            "execution_materials",
            f"{customer} {scenario} 执行材料清单",
            "项目负责人 / 交付 PM / 售前负责人",
            "用于把研究结论转成可下发的任务、清单和交付物。",
            execution_sections,
        ),
    ]
    artifacts: list[ResearchAdvisoryArtifactOut] = []
    for artifact_type, title, audience, purpose, sections in specs:
        review_checklist = _dedupe_strings(
            [
                "确认客户名称、牵头部门和场景是否可对外表达。",
                "确认所有确定性判断是否有官方源、客户材料或招采证据支撑。",
                "确认预算、时间、产品参数和竞品表述是否需要降级为假设。",
            ],
            limit=6,
        )
        artifacts.append(
            ResearchAdvisoryArtifactOut(
                artifact_type=artifact_type,
                title=title,
                audience=audience,
                purpose=purpose,
                source_policy=evidence_policy,
                markdown=_artifact_markdown(
                    title=title,
                    audience=audience,
                    purpose=purpose,
                    source_policy=evidence_policy,
                    sections=sections,
                ),
                review_checklist=review_checklist,
            )
        )
    return artifacts


def _outline_markdown(title: str, sections: list[ResearchSolutionOutlineSectionOut]) -> list[str]:
    lines = [f"## {title}"]
    for section in sections:
        lines.append(f"### {section.title}")
        lines.extend([f"- {bullet}" for bullet in section.bullets])
    return lines


def build_solution_delivery_markdown(
    pack: ResearchSolutionDeliveryPackOut,
    *,
    market_pack: ResearchMarketIntelligencePackOut | None = None,
) -> str:
    lines = [
        "# 解决方案交付包大纲",
        "",
        f"- 场景: {pack.scenario or '待确认'}",
        f"- 目标客户: {pack.target_customer or '待确认'}",
        f"- 垂直场景: {pack.vertical_scene or '待确认'}",
        f"- 来源支撑: {pack.source_support_score}/100",
        f"- 证据口径: {pack.evidence_policy or '正式对客前需复核关键来源。'}",
        "",
        "## 情报摘要",
        *[f"- {item}" for item in pack.intelligence_summary],
        "",
        "## 生成前核验",
        *[f"- {item}" for item in pack.grounding_checks],
        "",
        "## 用户确认问题",
        *[f"- {item}" for item in pack.clarification_questions],
        "",
    ]
    lines.extend(_outline_markdown("可行性研究报告大纲", pack.feasibility_outline))
    lines.append("")
    lines.extend(_outline_markdown("项目建议书大纲", pack.project_proposal_outline))
    lines.append("")
    lines.extend(_outline_markdown("对客汇报 PPT 大纲", pack.client_ppt_outline))
    if pack.advisory_artifacts:
        lines.extend(["", "## Advisory-grade 交付产物"])
        for artifact in pack.advisory_artifacts:
            lines.extend(
                [
                    f"### {artifact.title}",
                    f"- 类型: {artifact.artifact_type}",
                    f"- 受众: {artifact.audience}",
                    f"- 用途: {artifact.purpose}",
                    f"- 证据口径: {artifact.source_policy}",
                ]
            )
    lines.extend(["", "## 审阅清单"])
    lines.extend([f"- {item}" for item in pack.review_checklist])
    architecture = pack.architecture_readiness
    lines.extend(
        [
            "",
            "## 解决方案架构就绪度",
            f"- 评估框架: {architecture.framework_label}",
            f"- 综合评分: {architecture.overall_score}/100",
            f"- 状态: {architecture.status}",
            f"- 摘要: {architecture.summary or '待完成架构就绪度评估。'}",
            "",
            "### 架构蓝图",
        ]
    )
    for section in architecture.blueprint_sections:
        lines.extend(
            [
                f"#### {section.title}",
                f"- 目标: {section.purpose}",
                f"- 组件/对象: {'；'.join(section.components) if section.components else '待补'}",
                f"- 证据: {'；'.join(section.evidence) if section.evidence else '待补'}",
                f"- 待确认: {'；'.join(section.open_questions) if section.open_questions else '待补'}",
            ]
        )
    if architecture.integration_risks:
        lines.extend(["", "### 集成与落地风险", *[f"- {item}" for item in architecture.integration_risks]])
    if architecture.validation_actions:
        lines.extend(["", "### 架构核验动作", *[f"- {item}" for item in architecture.validation_actions]])
    workbench = pack.architect_workbench
    if workbench.customer_scenarios or workbench.stakeholders or workbench.decision_criteria:
        lines.extend(["", "## 解决方案架构师工作台"])
        for scenario in workbench.customer_scenarios[:2]:
            lines.extend(
                [
                    f"### 客户场景：{scenario.name}",
                    f"- 目标客户: {scenario.target_customer or '待确认'}",
                    f"- 关键角色: {'；'.join(scenario.primary_roles) if scenario.primary_roles else '待确认'}",
                    f"- 成功指标: {'；'.join(scenario.success_metrics[:4]) if scenario.success_metrics else '待补'}",
                ]
            )
        if workbench.stakeholders:
            lines.extend(["", "### 干系人问题地图"])
            for stakeholder in workbench.stakeholders[:5]:
                lines.append(
                    f"- {stakeholder.role}（{stakeholder.influence}）: "
                    f"{'；'.join(stakeholder.decision_questions[:2]) if stakeholder.decision_questions else '待补问题'}"
                )
        if workbench.decision_criteria:
            lines.extend(["", "### 决策标准与验证动作"])
            for criterion in workbench.decision_criteria[:5]:
                lines.append(f"- {criterion.criterion}: {criterion.validation_action}")
        if workbench.capability_architecture_matrix:
            lines.extend(["", "### 能力到架构矩阵"])
            for mapping in workbench.capability_architecture_matrix[:4]:
                lines.extend(
                    [
                        f"- {mapping.business_capability}",
                        f"  - 应用服务: {'；'.join(mapping.application_services[:4]) if mapping.application_services else '待补'}",
                        f"  - 数据依赖: {'；'.join(mapping.data_dependencies[:3]) if mapping.data_dependencies else '待补'}",
                        f"  - 集成面: {'；'.join(mapping.integration_surfaces[:3]) if mapping.integration_surfaces else '待补'}",
                        f"  - 核验动作: {'；'.join(mapping.validation_actions[:2]) if mapping.validation_actions else '待补'}",
                    ]
                )
        if workbench.architecture_decision_records:
            lines.extend(["", "### ADR 架构决策记录"])
            for adr in workbench.architecture_decision_records[:4]:
                lines.extend(
                    [
                        f"- 决策: {adr.decision}",
                        f"  - 背景: {adr.context or '待补'}",
                        f"  - 选定方向: {adr.selected_direction or '待补'}",
                        f"  - 风险: {'；'.join(adr.risks[:2]) if adr.risks else '待补'}",
                    ]
                )
        if workbench.integration_dependencies:
            lines.extend(["", "### 集成依赖诊断"])
            for dependency in workbench.integration_dependencies[:4]:
                lines.extend(
                    [
                        f"- {dependency.dependency}（{dependency.risk_level}）",
                        f"  - 来源系统: {dependency.source_system or '待确认'}",
                        f"  - 接口/数据契约: {dependency.api_or_data_contract or '待确认'}",
                        f"  - 权限边界: {dependency.auth_boundary or '待确认'}",
                        f"  - 核验动作: {dependency.validation_action or '待补'}",
                    ]
                )
        if workbench.next_meeting_agenda:
            lines.extend(["", "### 下一次客户会议议程", *[f"- {item}" for item in workbench.next_meeting_agenda[:6]]])
    lines.extend(["", "## 交付质量自审"])
    for profile in (pack.solution_quality_profile, pack.project_proposal_quality_profile):
        lines.extend(
            [
                f"### {profile.framework_label} / {profile.review_target}",
                f"- 综合评分: {profile.overall_score}/100",
                f"- 审查状态: {profile.status}",
                f"- 重点缺口: {'；'.join(profile.gaps[:3]) if profile.gaps else '当前未发现阻塞性交付缺口。'}",
            ]
        )
        if profile.self_review.triggered:
            lines.append(
                f"- 自修订: {profile.self_review.before_score} -> {profile.self_review.after_score}；"
                f"{'；'.join(profile.self_review.actions[:3])}"
            )
    if market_pack is not None:
        lines.extend(["", "## 近三年公开情报附录", market_pack.export_markdown])
    return "\n".join(lines).strip()
