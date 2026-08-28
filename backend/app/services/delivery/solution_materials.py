from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.schemas.research import (
    ResearchAdvisoryArtifactOut,
    ResearchDeliveryCompiledDocumentOut,
    ResearchMarketIntelligencePackOut,
    ResearchReportDocument,
    ResearchSolutionDeliveryPackOut,
    ResearchSolutionOutlineSectionOut,
)
from app.services.content_extractor import normalize_text
from app.services.delivery.document_compilers import (
    build_delivery_compiled_documents,
    compiled_document_to_outline_sections,
    select_compiled_document,
)


@dataclass(slots=True)
class SolutionDeliveryOutlines:
    compiled_documents: list[ResearchDeliveryCompiledDocumentOut]
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
    evidence_policy: str = "",
) -> SolutionDeliveryOutlines:
    resolved_policy = evidence_policy or (
        "仅把已命中主题、客户或招采/技术参数的来源写成确定判断；其余内容保留为待核验假设。"
        if market_pack.source_support_score < 70
        else "当前来源可支撑初版方案大纲，正式对客前仍需确认预算、客户和交付边界。"
    )
    compiled_documents = build_delivery_compiled_documents(
        report,
        market_pack=market_pack,
        scenario=scenario,
        target_customer=target_customer,
        vertical_scene=vertical_scene,
        evidence_policy=resolved_policy,
    )
    feasibility_document = select_compiled_document(compiled_documents, "feasibility_study")
    proposal_document = select_compiled_document(compiled_documents, "project_proposal")
    feasibility_outline = (
        compiled_document_to_outline_sections(feasibility_document)
        if feasibility_document is not None
        else []
    )
    project_proposal_outline = (
        compiled_document_to_outline_sections(proposal_document)
        if proposal_document is not None
        else []
    )
    reference_title = (
        "2. 外部趋势与近三年招采参考"
        if market_pack.tender_projects
        else "2. 外部趋势与公开政策/试点参考"
    )
    client_ppt_outline = [
        _outline("1. 客户当前业务挑战", [report.executive_summary, vertical_scene]),
        _outline(reference_title, [*[item.project_name for item in market_pack.tender_projects[:4]], *market_pack.tender_keywords[:5]]),
        _outline("3. 建设目标与总体架构", [*report.strategic_directions[:3], "业务层、智能中台层、模型/数据层、安全运维层。"]),
        _outline("4. 核心功能与产品清单", [*[item.name for item in market_pack.product_catalog[:6]]]),
        _outline("5. 技术参数与交付边界", [*[param for item in market_pack.technical_parameter_catalog[:3] for param in item.technical_parameters[:2]]]),
        _outline("6. 实施路线与预算口径", [*report.tender_timeline[:3], *report.budget_signals[:3]]),
        _outline("7. 下一步共创计划", [report.commercial_summary.next_action, "客户确认范围后输出正式可研、建议书和对客汇报稿。"]),
    ]
    return SolutionDeliveryOutlines(
        compiled_documents=compiled_documents,
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
    has_tender_projects = bool(market_pack.tender_projects)
    prep_title = "招采与竞标准备" if has_tender_projects else "政策/试点与机会准备"
    action_title = "投标准备动作" if has_tender_projects else "机会准备动作"
    memo_title = "投标准备 memo" if has_tender_projects else "机会准备 memo"
    memo_purpose = (
        "用于招采前研判、评分点预判、材料责任分工。"
        if has_tender_projects
        else "用于政策、试点、申报或预算窗口研判、材料责任分工。"
    )
    prep_actions = (
        ["建立招标文件预审清单。", "准备技术偏离表、商务条款风险表和评分点响应矩阵。"]
        if has_tender_projects
        else ["建立政策/试点申报材料预审清单。", "准备范围边界、证据矩阵、预算假设和责任分工表。"]
    )
    client_sections = [
        _outline("客户场景与触发信号", [f"目标客户：{customer}", f"场景：{scene}", report.executive_summary, *report.budget_signals[:2]]),
        _outline("可交流方案主张", [*report.strategic_directions[:3], *[item.name for item in market_pack.product_catalog[:4]], report.commercial_summary.next_action]),
        _outline("公开证据与边界", [market_pack.source_scope_summary, *top_projects, *market_pack.intelligence_gaps[:2]]),
        _outline("建议会议目标", ["确认牵头部门、试点范围、数据边界和预算口径。", "争取客户提供现有流程、系统接口和历史项目材料。"]),
    ]
    bidding_sections = [
        _outline("机会判断", [f"客户/业主：{customer}", f"场景：{scenario}", report.consulting_angle, *report.tender_timeline[:3]]),
        _outline(prep_title, [*[item.project_name for item in market_pack.tender_projects[:4]], *report.competition_analysis[:3], *market_pack.tender_keywords[:5]]),
        _outline("技术与资质关注", [*top_requirements, *report.technical_appendix.limitations[:2], "补齐资质、业绩案例、产品参数和安全合规说明。"]),
        _outline(action_title, [*prep_actions, report.commercial_summary.next_action]),
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
            f"{customer} {scenario} {memo_title}",
            "售前、投标、解决方案和商务团队",
            memo_purpose,
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
    industry_context = pack.industry_skill_context
    if industry_context.status == "available":
        lines.extend(
            [
                "## 本地行业资料技能",
                f"- 本地索引版本: {industry_context.catalog_version or '待确认'}",
                f"- 已调用技能: {'；'.join(skill.name for skill in industry_context.selected_skills) or '待确认'}",
                f"- 覆盖资料: {industry_context.source_document_count} 份（仅作行业框架与规范性校验）",
                "- 证据边界: 本地资料不计入公开来源支撑度、客户事实或正式项目证据；对外引用前必须回查原件和官方来源。",
            ]
        )
        for skill in industry_context.selected_skills:
            lines.extend(
                [
                    f"### {skill.name}",
                    f"- 调用原因: {skill.selection_reason or '按当前场景匹配'}",
                    f"- 资料类型: {'；'.join(f'{label} {count} 份' for label, count in skill.document_type_counts.items()) or '待确认'}",
                    *[f"- 规范: {item}" for item in skill.guidance[:3]],
                    *[f"- 本地参考要点（待核验）: {item}" for item in skill.reference_highlights[:2]],
                    *[
                        f"- 参考资料: {reference.title}"
                        + (f"（{reference.published_year}）" if reference.published_year else "")
                        for reference in skill.references[:4]
                    ],
                ]
            )
        if industry_context.warnings:
            lines.extend(["", "### 资料库提示", *[f"- {item}" for item in industry_context.warnings[:4]]])
        lines.append("")
    if pack.compiled_documents:
        lines.extend(["## 四类专用文档编译器"])
        for document in pack.compiled_documents:
            lines.extend(
                [
                    f"### {document.title}",
                    f"- 类型: {document.document_kind}",
                    f"- 编译器: {document.framework}",
                    f"- 受众: {document.audience or '待确认'}",
                    f"- 用途: {document.purpose or '待确认'}",
                    f"- 章节数: {len(document.sections)}",
                    f"- 质量门槛: {'；'.join(document.quality_gates[:2]) if document.quality_gates else '待补'}",
                ]
            )
        lines.append("")
    quantitative_model = pack.quantitative_decision_model
    if (
        quantitative_model.alternative_options
        or quantitative_model.tender_score_response_matrix
        or quantitative_model.financial_scenarios
    ):
        if quantitative_model.export_markdown:
            lines.extend(["", quantitative_model.export_markdown, ""])
        else:
            lines.extend(
                [
                    "",
                    "## 量化决策模型",
                    f"- 状态: {quantitative_model.status}",
                    f"- 推荐方案: {quantitative_model.recommended_option_id or '待确认'}",
                    f"- 摘要: {quantitative_model.summary or '待补'}",
                    "",
                ]
            )
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
    architecture_exports = pack.architecture_export_bundle
    if (
        architecture_exports.adr_table
        or architecture_exports.dependency_workshop_checklist
        or architecture_exports.customer_technical_workshop_agenda
    ):
        lines.extend(["", architecture_exports.export_markdown or "## 架构交付导出包"])
    engineering = pack.architecture_decision_engineering
    lines.extend(
        [
            "",
            "## QAW / ATAM / ADR / C4 架构决策工程",
            f"- 状态: {engineering.status}",
            f"- 摘要: {engineering.summary or '待完成架构决策工程。'}",
            f"- QAW 场景: {len(engineering.quality_attribute_scenarios)}",
            f"- ADR: {len(engineering.adrs)}",
            f"- C4 视图: {len(engineering.c4_views)}",
            f"- 追溯链覆盖: {engineering.traceability_coverage_percent}%",
            f"- 孤立组件: {engineering.orphan_component_count}",
        ]
    )
    for scenario in engineering.quality_attribute_scenarios:
        lines.append(
            f"- {scenario.scenario_id} | {scenario.quality_attribute} | {scenario.response_measure} | {scenario.status}"
        )
    for adr in engineering.adrs:
        lines.extend(
            [
                f"- {adr.adr_id} | {adr.title} | {adr.status} | {adr.risk_level}",
                f"  - 选项: {'；'.join(f'{option.option_type}:{option.name}' for option in adr.options)}",
                f"  - 回滚: {'；'.join(adr.rollback_conditions[:2]) if adr.rollback_conditions else '待补'}",
                f"  - 验证: {'；'.join(adr.validation_action_ids) if adr.validation_action_ids else '待补'}",
            ]
        )
    proof = pack.proof_of_architecture
    lines.extend(
        [
            "",
            "## Proof of Architecture 与验收证据",
            f"- 状态: {proof.status}",
            f"- 摘要: {proof.summary or '待运行可执行验证。'}",
            f"- 质量场景测试覆盖: {proof.scenario_test_coverage_percent}%",
            f"- 高风险 ADR 证据覆盖: {proof.high_risk_decision_evidence_percent}%",
            "",
            "### 机器可读验证项",
        ]
    )
    for check in proof.checks:
        lines.append(
            f"- {check.check_id} | {check.category} | {check.status} | {check.threshold} | "
            f"{check.artifact_path or '待补 artifact'}"
        )
    lines.extend(
        [
            "",
            "### 客户版证据边界",
            *[f"- 已确认: {item}" for item in proof.customer_evidence.confirmed_findings],
            *[f"- 假设: {item}" for item in proof.customer_evidence.assumptions],
            *[f"- 限制: {item}" for item in proof.customer_evidence.limitations],
            *[f"- 待验证: {item}" for item in proof.customer_evidence.pending_validations],
            "",
            "### 内部证据附录",
            *[f"- 已确认: {item}" for item in proof.internal_evidence.confirmed_findings],
            *[f"- 限制: {item}" for item in proof.internal_evidence.limitations],
            *[f"- 待验证: {item}" for item in proof.internal_evidence.pending_validations],
            *[f"- Artifact: {item}" for item in proof.internal_evidence.artifact_paths],
        ]
    )
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
    ledger = pack.evidence_ledger
    lines.extend(
        [
            "",
            "## 主张—证据账本与一致性检查",
            f"- 账本状态: {ledger.status}",
            f"- 稳定主张: {ledger.claim_count} 条",
            f"- 证据锚点: {ledger.evidence_count} 个",
            f"- 总体主张覆盖: {ledger.claim_coverage_percent}%",
            f"- 高置信主张覆盖: {ledger.high_confidence_coverage_percent}%",
            f"- 实体一致性: {ledger.entity_consistency_score}/100",
            f"- 数字一致性: {ledger.numeric_consistency_score}/100",
        ]
    )
    for claim in ledger.claims[:10]:
        relation_ids = [
            relation.evidence_id
            for relation in claim.evidence_relations
            if relation.relation_type in {"supports", "conflicts"}
        ]
        lines.append(
            f"- {claim.claim_id} | {claim.verification_status} | {claim.text}"
            + (f" | {'、'.join(relation_ids[:3])}" if relation_ids else "")
        )
    if ledger.consistency_issues:
        lines.extend(["", "### 一致性问题"])
        lines.extend(
            [
                f"- {issue.issue_id} | {issue.severity} | {issue.summary} | {'；'.join(issue.details[:3])}"
                for issue in ledger.consistency_issues[:8]
            ]
        )
    challenge = pack.semantic_challenge or pack.solution_quality_profile.semantic_challenge
    lines.extend(
        [
            "",
            "## 语义挑战者审查记录",
            f"- 挑战者状态: {challenge.status}",
            f"- 挑战者评分: {challenge.overall_score}/100",
            f"- 问题总数: {challenge.issue_count}",
            f"- 高严重度问题: {challenge.high_severity_count}",
            f"- 范围漂移: {challenge.scope_drift_count}",
            f"- 跨章节冲突: {challenge.cross_section_conflict_count}",
            f"- 黄金样本: {challenge.golden_sample_title or '未匹配'}",
            f"- 黄金样本对齐: {challenge.golden_sample_alignment_score}/100",
        ]
    )
    if challenge.issues:
        lines.extend(["", "### 挑战者问题"])
        lines.extend(
            [
                f"- {issue.issue_id} | {issue.severity} | {issue.issue_type} | {issue.summary}"
                for issue in challenge.issues[:8]
            ]
        )
    if challenge.recommended_actions:
        lines.extend(["", "### 挑战者修订动作", *[f"- {action}" for action in challenge.recommended_actions[:6]]])
    if market_pack is not None:
        lines.extend(["", "## 近三年公开情报附录", market_pack.export_markdown])
    return "\n".join(lines).strip()
