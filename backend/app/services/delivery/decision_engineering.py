from __future__ import annotations

import re
from typing import Iterable

from app.schemas.research import (
    ResearchArchitectureDecisionEngineeringOut,
    ResearchArchitectureDecisionRecordV2Out,
    ResearchArchitectureOptionOut,
    ResearchArchitectureTraceabilityLinkOut,
    ResearchATAMAssessmentOut,
    ResearchATAMFindingOut,
    ResearchATAMUtilityNodeOut,
    ResearchC4ElementOut,
    ResearchC4RelationshipOut,
    ResearchC4ViewOut,
    ResearchQualityAttributeScenarioOut,
    ResearchReportDocument,
    ResearchSolutionArchitectureReadinessOut,
    ResearchSolutionArchitectWorkbenchOut,
    ResearchSolutionCapabilityArchitectureMappingOut,
    ResearchSolutionDeliveryPackOut,
    ResearchWellArchitectedCheckOut,
)
from app.services.content_extractor import normalize_text
from app.services.research.hard_failure_policy import evaluate_research_hard_failures


def _dedupe(values: Iterable[object], limit: int = 12) -> list[str]:
    seen: set[str] = set()
    rows: list[str] = []
    for value in values:
        text = normalize_text(str(value or ""))
        if not text or text in seen:
            continue
        seen.add(text)
        rows.append(text)
        if len(rows) >= limit:
            break
    return rows


def _slug(value: str, fallback: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-")
    return slug[:40] or fallback


def _quality_scenarios(
    customer: str,
    scene: str,
    evidence: list[str],
) -> list[ResearchQualityAttributeScenarioOut]:
    specs = [
        (
            "availability",
            "业务高峰期核心服务出现单实例故障",
            "生产环境且请求持续进入",
            "场景应用与模型编排服务",
            "自动切换到健康实例或受控降级，不丢失已受理任务",
            "5 分钟内恢复；月可用性不低于 99.9%；已受理任务丢失率为 0",
            "high",
        ),
        (
            "security",
            "未授权角色尝试访问客户敏感数据或发布生成内容",
            "生产环境及运维排障环境",
            "身份、权限、数据和内容发布边界",
            "拒绝访问并生成可追溯审计事件",
            "越权请求阻断率 100%；审计字段完整率 100%；高危告警 5 分钟内送达",
            "high",
        ),
        (
            "performance",
            "并发请求达到试点峰值的两倍",
            "代表性数据量和模型配置下",
            "API、检索、模型推理与结果组装链路",
            "在容量边界内保持服务，超限时按优先级排队或降级",
            "P95 响应不高于 3 秒；错误率低于 1%；队列等待不高于 30 秒",
            "high",
        ),
        (
            "cost",
            "日请求量或模型 token 消耗超过试点预算基线",
            "试点运行及扩容评估阶段",
            "模型路由、缓存、检索和算力资源",
            "触发预算告警并切换到经验证的成本受控策略",
            "单次请求成本不超过预算基线 120%；月度预测偏差不超过 10%",
            "medium",
        ),
        (
            "operability",
            "关键链路质量下降或外部依赖超时",
            "生产环境且值班人员仅查看统一观测面板",
            "网关、业务服务、检索、模型和数据依赖",
            "关联 trace、指标、日志和告警，给出故障域与恢复动作",
            "关键请求 trace 覆盖率 100%；10 分钟内定位故障域；30 分钟内恢复",
            "high",
        ),
        (
            "ai_risk",
            "模型输出包含无依据结论、敏感内容或低置信建议",
            "客户内容生成和决策辅助场景",
            "知识检索、模型输出、内容安全与人工复核链路",
            "阻断对外发布并保留证据、模型版本和人工处理记录",
            "高风险内容阻断率 100%；关键主张证据覆盖率 100%；人工复核记录完整率 100%",
            "high",
        ),
    ]
    return [
        ResearchQualityAttributeScenarioOut(
            scenario_id=f"qas-{index:02d}-{attribute}",
            quality_attribute=attribute,  # type: ignore[arg-type]
            business_source=f"{customer} / {scene}",
            stimulus=stimulus,
            environment=environment,
            artifact=artifact,
            response=response,
            response_measure=measure,
            priority=priority,  # type: ignore[arg-type]
            status="draft",
            evidence=evidence[:4],
            acceptance_test_ids=[f"poa-{attribute}"],
        )
        for index, (attribute, stimulus, environment, artifact, response, measure, priority) in enumerate(specs, start=1)
    ]


def _options(adr_id: str, subject: str) -> list[ResearchArchitectureOptionOut]:
    return [
        ResearchArchitectureOptionOut(
            option_id=f"{adr_id}-baseline",
            option_type="baseline",
            name="维持现状基线",
            description=f"保留当前 {subject}，只做必要修补。",
            benefits=["组织改动最小", "可作为成本和质量对照组"],
            tradeoffs=["无法系统性关闭已识别风险", "扩容和审计能力受现状限制"],
            assumptions=["现有链路能支撑试点最低流量"],
        ),
        ResearchArchitectureOptionOut(
            option_id=f"{adr_id}-pilot",
            option_type="pilot",
            name="隔离式低风险试点",
            description=f"在受控用户、数据和容量边界内验证 {subject}。",
            benefits=["可以形成真实测量和回滚证据", "不影响现有生产主链路"],
            tradeoffs=["短期存在双轨运维", "试点结论需要再验证规模化边界"],
            assumptions=["客户可提供脱敏样例数据和测试窗口"],
        ),
        ResearchArchitectureOptionOut(
            option_id=f"{adr_id}-target",
            option_type="target",
            name="目标平台化方案",
            description=f"按可观测、可扩展、可治理要求建设完整 {subject}。",
            benefits=["能力边界统一", "可持续扩容并沉淀治理策略"],
            tradeoffs=["投入和组织协同成本最高", "必须先满足试点门禁"],
            assumptions=["试点达到业务、质量和成本阈值后再放量"],
        ),
    ]


def _adrs(evidence: list[str]) -> list[ResearchArchitectureDecisionRecordV2Out]:
    specs = [
        (
            "adr-001-delivery-path",
            "采用试点到平台化的分阶段交付路径",
            "在控制首次投入和集成风险的同时保留规模化能力边界。",
            ["业务价值可测量", "变更范围可回滚", "阶段验收可审计"],
            "medium",
            ["poa-representative-flow", "poa-rollback"],
        ),
        (
            "adr-002-integration-boundary",
            "采用 API-first 且保留文件/视图补充的集成边界",
            "统一权限、审计和错误语义，避免数据库直连成为默认依赖。",
            ["接口契约稳定", "最小权限", "故障隔离"],
            "high",
            ["poa-api-contract", "poa-access-boundary", "poa-failure-recovery"],
        ),
        (
            "adr-003-ai-runtime-governance",
            "采用证据约束、模型路由和人工兜底的 AI 运行链路",
            "模型输出不能绕过证据、内容安全和人工复核门禁。",
            ["关键主张有证据", "高风险输出可阻断", "模型和提示版本可追溯"],
            "high",
            ["poa-ai-risk", "poa-observability", "poa-capacity-cost"],
        ),
    ]
    rows: list[ResearchArchitectureDecisionRecordV2Out] = []
    for adr_id, title, context, drivers, risk, validation_ids in specs:
        options = _options(adr_id, title)
        rows.append(
            ResearchArchitectureDecisionRecordV2Out(
                adr_id=adr_id,
                title=title,
                status="proposed",
                context=context,
                drivers=drivers,
                options=options,
                selected_option_id=f"{adr_id}-pilot",
                evidence=evidence[:6],
                assumptions=["客户系统、数据、安全和预算边界仍以 workshop 确认为准"],
                consequences=["先形成可执行验证证据，再决定是否进入目标方案", "未验证假设保留为 proposed"],
                rollback_conditions=["任一硬门禁失败", "试点质量、成本或恢复指标未达阈值", "客户撤销数据或接口授权"],
                validation_action_ids=validation_ids,
                owner="解决方案架构师" if risk == "medium" else "技术架构负责人",
                due_date="客户技术 workshop 后 10 个工作日内",
                risk_level=risk,  # type: ignore[arg-type]
            )
        )
    return rows


def _atam(
    scenarios: list[ResearchQualityAttributeScenarioOut],
    adrs: list[ResearchArchitectureDecisionRecordV2Out],
) -> ResearchATAMAssessmentOut:
    utility = [
        ResearchATAMUtilityNodeOut(
            node_id=f"utility-{scenario.quality_attribute}",
            quality_attribute=scenario.quality_attribute,
            scenario_ids=[scenario.scenario_id],
            priority=scenario.priority,
            difficulty="high" if scenario.priority == "high" else "medium",
        )
        for scenario in scenarios
    ]
    findings = [
        ResearchATAMFindingOut(
            finding_id="atam-risk-integration",
            finding_type="risk",
            title="接口、样例数据和测试窗口未确认会阻塞纵向样机",
            scenario_ids=["qas-03-performance", "qas-05-operability"],
            adr_ids=["adr-002-integration-boundary"],
            owner="客户信息化负责人",
        ),
        ResearchATAMFindingOut(
            finding_id="atam-sensitivity-model-route",
            finding_type="sensitivity_point",
            title="模型路由、缓存命中和上下文长度共同影响时延与成本",
            scenario_ids=["qas-03-performance", "qas-04-cost"],
            adr_ids=["adr-003-ai-runtime-governance"],
            owner="技术架构负责人",
        ),
        ResearchATAMFindingOut(
            finding_id="atam-tradeoff-security-usability",
            finding_type="tradeoff_point",
            title="严格权限和人工复核提高安全性，但会增加流程时延",
            scenario_ids=["qas-02-security", "qas-06-ai_risk"],
            adr_ids=["adr-002-integration-boundary", "adr-003-ai-runtime-governance"],
            owner="安全合规负责人",
        ),
        ResearchATAMFindingOut(
            finding_id="atam-nonrisk-phased-rollout",
            finding_type="non_risk",
            title="隔离式试点可在不影响现有生产链路的条件下形成回滚证据",
            scenario_ids=["qas-01-availability"],
            adr_ids=["adr-001-delivery-path"],
            owner="解决方案架构师",
        ),
        ResearchATAMFindingOut(
            finding_id="atam-theme-evidence-governance",
            finding_type="risk_theme",
            title="证据、权限、模型与人工结论必须保持同一条审计链",
            scenario_ids=["qas-02-security", "qas-06-ai_risk"],
            adr_ids=[adr.adr_id for adr in adrs],
            owner="项目治理委员会",
        ),
    ]
    return ResearchATAMAssessmentOut(
        utility_tree=utility,
        findings=findings,
        risk_theme_count=sum(row.finding_type == "risk_theme" for row in findings),
        high_risk_count=sum(adr.risk_level == "high" for adr in adrs),
    )


def _c4_and_traceability(
    customer: str,
    scene: str,
    workbench: ResearchSolutionArchitectWorkbenchOut,
    scenarios: list[ResearchQualityAttributeScenarioOut],
) -> tuple[list[ResearchC4ElementOut], list[ResearchC4ViewOut], list[ResearchArchitectureTraceabilityLinkOut]]:
    qas_ids = [row.scenario_id for row in scenarios]
    deployment_id = "deploy-customer-boundary"
    elements: list[ResearchC4ElementOut] = [
        ResearchC4ElementOut(
            element_id="person-business-user",
            name=f"{customer} 业务用户",
            element_type="person",
            description=f"使用 {scene} 并确认业务结果。",
            business_scenario_ids=["business-scenario-01"],
            responsibility_boundary="客户业务部门",
            quality_scenario_ids=qas_ids,
        ),
        ResearchC4ElementOut(
            element_id="system-solution",
            name=f"{scene} 解决方案",
            element_type="software_system",
            description="承载场景应用、数据接入、AI 运行和治理闭环。",
            interfaces=["HTTPS API", "客户统一身份认证"],
            responsibility_boundary="项目联合交付边界",
            quality_scenario_ids=qas_ids,
        ),
        ResearchC4ElementOut(
            element_id=deployment_id,
            name="客户安全边界内的试点运行环境",
            element_type="deployment_node",
            description="隔离网络、最小权限、日志审计和可回滚部署单元。",
            technology="客户确认的私有化、专有云或受控云环境",
            responsibility_boundary="客户信息化与交付团队联合负责",
            quality_scenario_ids=qas_ids,
            deployment_target="试点环境",
        ),
    ]
    links: list[ResearchArchitectureTraceabilityLinkOut] = []
    relationships: list[ResearchC4RelationshipOut] = [
        ResearchC4RelationshipOut(
            source_id="person-business-user",
            target_id="system-solution",
            description="提交业务请求并查看受控结果",
            interface="HTTPS",
            data_flow="业务输入 -> 受控输出",
        )
    ]
    capabilities = workbench.capability_architecture_matrix[:4]
    for index, mapping in enumerate(capabilities, start=1):
        component_id = f"component-{index:02d}-{_slug(mapping.business_capability, 'capability')}"
        container_id = f"container-{index:02d}-service"
        interface = mapping.integration_surfaces[0] if mapping.integration_surfaces else "受控业务 API"
        data_assets = mapping.data_dependencies[:3] or [f"{mapping.business_capability} 业务数据"]
        elements.extend(
            [
                ResearchC4ElementOut(
                    element_id=container_id,
                    name=f"{mapping.business_capability} 服务容器",
                    element_type="container",
                    description=f"隔离承载 {mapping.business_capability} 的接口、业务和观测职责。",
                    technology="API service + auditable workflow",
                    business_scenario_ids=[f"requirement-{index:02d}"],
                    data_assets=data_assets,
                    interfaces=[interface],
                    responsibility_boundary="应用交付团队",
                    quality_scenario_ids=qas_ids,
                    deployment_target=deployment_id,
                ),
                ResearchC4ElementOut(
                    element_id=component_id,
                    name=f"{mapping.business_capability} 可验证组件",
                    element_type="component",
                    description=f"实现 {mapping.business_capability}，并绑定数据、接口、质量场景和验收测试。",
                    technology=(mapping.application_services[0] if mapping.application_services else "业务组件"),
                    business_scenario_ids=[f"requirement-{index:02d}"],
                    data_assets=data_assets,
                    interfaces=[interface],
                    responsibility_boundary="组件 owner 与客户业务 owner 联合验收",
                    quality_scenario_ids=qas_ids,
                    deployment_target=deployment_id,
                ),
            ]
        )
        relationships.extend(
            [
                ResearchC4RelationshipOut(
                    source_id="system-solution",
                    target_id=container_id,
                    description=f"编排 {mapping.business_capability}",
                    interface=interface,
                    data_flow="请求上下文与审计标识",
                ),
                ResearchC4RelationshipOut(
                    source_id=container_id,
                    target_id=component_id,
                    description=f"执行 {mapping.business_capability}",
                    interface="内部受控契约",
                    data_flow="业务数据与执行结果",
                ),
            ]
        )
        links.append(
            ResearchArchitectureTraceabilityLinkOut(
                requirement_id=f"requirement-{index:02d}",
                business_requirement=mapping.business_capability,
                capability=mapping.business_capability,
                component_ids=[component_id],
                data_assets=data_assets,
                interfaces=[interface],
                deployment_node_ids=[deployment_id],
                risk_ids=["atam-risk-integration", "atam-theme-evidence-governance"],
                acceptance_test_ids=["poa-api-contract", "poa-representative-flow", "poa-observability"],
            )
        )
    element_ids = [row.element_id for row in elements]
    views = [
        ResearchC4ViewOut(
            view_id=f"c4-{level}",
            level=level,  # type: ignore[arg-type]
            title=f"{scene} {label}",
            audience=audience,
            element_ids=element_ids,
            relationships=relationships,
        )
        for level, label, audience in (
            ("context", "系统上下文图", "业务与管理干系人"),
            ("container", "容器图", "架构与交付团队"),
            ("component", "组件图", "研发与测试团队"),
            ("dynamic", "代表性请求动态视图", "研发、测试与运维团队"),
            ("deployment", "部署视图", "信息化、安全与运维团队"),
        )
    ]
    return elements, views, links


def _well_architected(evidence: list[str]) -> list[ResearchWellArchitectedCheckOut]:
    specs = (
        ("reliability", "故障域、恢复时间和数据不丢失阈值是否可测试？"),
        ("security", "身份、权限、数据出域和审计边界是否已确认？"),
        ("performance", "峰值容量、P95 时延和超限降级是否有基线？"),
        ("cost", "模型、检索、存储和运维成本是否能按请求和月份追踪？"),
        ("operations", "trace、指标、日志、告警和 runbook 是否覆盖关键链路？"),
        ("ai_data", "数据来源、授权、质量、更新和删除责任是否可追溯？"),
        ("ai_model", "模型路由、版本、评测、回退和变更审批是否受控？"),
        ("ai_content", "无依据或高风险内容是否在发布前被阻断？"),
        ("ai_supply_chain", "模型、插件、依赖和外部 API 供应链是否有清单和退出方案？"),
        ("ai_human_oversight", "高风险结论是否有明确人工 owner 和复核记录？"),
        ("ai_continuous_monitoring", "质量、漂移、成本、安全和人工纠错是否持续监控？"),
    )
    return [
        ResearchWellArchitectedCheckOut(
            check_id=f"wa-{pillar}",
            pillar=pillar,  # type: ignore[arg-type]
            status="watch",
            question=question,
            finding="已生成可执行验证项；客户约束和真实运行结果确认前保持 watch。",
            evidence=evidence[:3],
            action=f"执行 poa-{pillar.replace('operations', 'observability')} 并回写 artifact。",
            owner="技术架构负责人" if pillar not in {"ai_human_oversight", "ai_content"} else "业务与合规负责人",
        )
        for pillar, question in specs
    ]


def build_architecture_decision_engineering(
    report: ResearchReportDocument,
    *,
    pack: ResearchSolutionDeliveryPackOut,
    architecture: ResearchSolutionArchitectureReadinessOut,
    workbench: ResearchSolutionArchitectWorkbenchOut,
) -> ResearchArchitectureDecisionEngineeringOut:
    hard_failure = evaluate_research_hard_failures(report)
    if hard_failure.blocked:
        return ResearchArchitectureDecisionEngineeringOut(
            status="blocked",
            summary="研究硬门禁失败，不生成完整 QAW/ATAM/ADR/C4 架构包。",
            blockers=list(hard_failure.reasons) or list(hard_failure.failure_codes),
            workshop_questions=["先修复研究证据与引用门，再进入架构 workshop。"],
        )

    customer = pack.target_customer or (report.target_accounts[0] if report.target_accounts else "待确认客户")
    scene = pack.vertical_scene or pack.scenario or report.keyword
    scenario_rows = workbench.customer_scenarios[:1]
    evidence = _dedupe(
        [
            report.executive_summary,
            *report.budget_signals[:2],
            *(scenario_rows[0].evidence if scenario_rows else []),
            *(row.evidence[0] for row in workbench.capability_architecture_matrix if row.evidence),
        ],
        8,
    )
    qaw = _quality_scenarios(customer, scene, evidence)
    adrs = _adrs(evidence)
    atam = _atam(qaw, adrs)
    workshop_questions = _dedupe(
        [
            *architecture.stakeholder_questions,
            "逐项确认 QAW 响应指标的当前基线、目标值和测量环境。",
            "为每个高风险 ADR 确认 owner、截止时间、测试窗口和回滚审批人。",
            "确认客户版可公开结论与内部假设、限制和争议的边界。",
        ],
        10,
    )
    has_decision_inputs = bool(workbench.capability_architecture_matrix and evidence and pack.source_support_score >= 60)
    if not has_decision_inputs:
        return ResearchArchitectureDecisionEngineeringOut(
            status="workshop_only",
            summary="研究门禁已通过，但客户质量属性或架构输入不足；仅输出 QAW 草案和 workshop 验证计划。",
            quality_attribute_scenarios=qaw,
            atam=atam,
            adrs=adrs,
            high_risk_decision_count=sum(row.risk_level == "high" for row in adrs),
            workshop_questions=workshop_questions,
            blockers=["source_support_score < 60 或能力架构映射缺失"],
        )

    c4_elements, c4_views, traceability = _c4_and_traceability(customer, scene, workbench, qaw)
    linked_components = {component for row in traceability for component in row.component_ids}
    component_ids = {row.element_id for row in c4_elements if row.element_type == "component"}
    orphan_count = len(component_ids - linked_components)
    complete_links = sum(
        bool(
            row.capability
            and row.component_ids
            and row.data_assets
            and row.interfaces
            and row.deployment_node_ids
            and row.risk_ids
            and row.acceptance_test_ids
        )
        for row in traceability
    )
    coverage = round(complete_links / max(1, len(traceability)) * 100)
    status = "ready_for_review" if coverage == 100 and orphan_count == 0 else "workshop_only"
    blockers = [] if status == "ready_for_review" else ["架构追溯链未达到 100% 或存在孤立组件"]
    return ResearchArchitectureDecisionEngineeringOut(
        status=status,
        summary=(
            f"已形成 {len(qaw)} 个可量化 QAW 场景、{len(adrs)} 条三方案 ADR、"
            f"5 层 C4 视图和 {coverage}% 需求追溯链；决策状态保持 proposed，待真实验证。"
        ),
        quality_attribute_scenarios=qaw,
        atam=atam,
        adrs=adrs,
        c4_elements=c4_elements,
        c4_views=c4_views,
        well_architected_checks=_well_architected(evidence),
        traceability_links=traceability,
        traceability_coverage_percent=coverage,
        orphan_component_count=orphan_count,
        high_risk_decision_count=sum(row.risk_level == "high" for row in adrs),
        workshop_questions=workshop_questions,
        blockers=blockers,
    )


def validate_architecture_decision_engineering(
    engineering: ResearchArchitectureDecisionEngineeringOut,
) -> dict[str, object]:
    blockers: list[str] = []
    incomplete_qaw = [
        row.scenario_id
        for row in engineering.quality_attribute_scenarios
        if not all(
            (
                row.business_source,
                row.stimulus,
                row.environment,
                row.artifact,
                row.response,
                row.response_measure,
                row.acceptance_test_ids,
            )
        )
    ]
    if incomplete_qaw:
        blockers.append(f"{len(incomplete_qaw)} QAW scenarios lack measurable fields or acceptance tests")
    invalid_adrs = [
        row.adr_id
        for row in engineering.adrs
        if {option.option_type for option in row.options} != {"baseline", "pilot", "target"}
        or not row.drivers
        or not row.evidence
        or not row.rollback_conditions
        or not row.validation_action_ids
        or not row.owner
        or not row.due_date
    ]
    if invalid_adrs:
        blockers.append(f"{len(invalid_adrs)} ADRs lack alternatives, evidence, rollback, owner, due date, or validation")
    required_atam_types = {"risk", "non_risk", "sensitivity_point", "tradeoff_point", "risk_theme"}
    observed_atam_types = {row.finding_type for row in engineering.atam.findings}
    if not required_atam_types <= observed_atam_types:
        blockers.append("ATAM findings do not cover risks, non-risks, sensitivity, tradeoffs, and risk themes")
    required_c4_levels = {"context", "container", "component", "dynamic", "deployment"}
    observed_c4_levels = {row.level for row in engineering.c4_views}
    if observed_c4_levels != required_c4_levels:
        blockers.append("C4 views must include context, container, component, dynamic, and deployment")
    if engineering.traceability_coverage_percent != 100:
        blockers.append("architecture traceability coverage must be 100%")
    if engineering.orphan_component_count:
        blockers.append(f"architecture contains {engineering.orphan_component_count} orphan components")
    high_risk = [row for row in engineering.adrs if row.risk_level == "high"]
    invalid_high_risk = [
        row.adr_id
        for row in high_risk
        if not row.owner or not row.due_date or not row.rollback_conditions or not row.validation_action_ids
    ]
    if invalid_high_risk:
        blockers.append(f"{len(invalid_high_risk)} high-risk ADRs lack accountable validation and rollback")
    if engineering.status != "ready_for_review":
        blockers.append(f"architecture engineering status is {engineering.status}, expected ready_for_review")
    return {
        "status": "pass" if not blockers else "blocked",
        "qaw_scenario_count": len(engineering.quality_attribute_scenarios),
        "adr_count": len(engineering.adrs),
        "atam_finding_count": len(engineering.atam.findings),
        "c4_view_count": len(engineering.c4_views),
        "well_architected_check_count": len(engineering.well_architected_checks),
        "traceability_coverage_percent": engineering.traceability_coverage_percent,
        "orphan_component_count": engineering.orphan_component_count,
        "high_risk_decision_count": len(high_risk),
        "blockers": blockers,
    }


def build_reference_architecture_decision_engineering() -> ResearchArchitectureDecisionEngineeringOut:
    evidence = ["reference requirement", "reference interface contract", "reference acceptance threshold"]
    scenarios = _quality_scenarios("参考客户", "可验证 AI 场景", evidence)
    adrs = _adrs(evidence)
    workbench = ResearchSolutionArchitectWorkbenchOut(
        capability_architecture_matrix=[
            ResearchSolutionCapabilityArchitectureMappingOut(
                business_capability="受控知识问答",
                application_services=["受控问答 API"],
                data_dependencies=["已授权知识库"],
                model_dependencies=["可回退模型路由"],
                integration_surfaces=["HTTPS API / OAuth2"],
                security_constraints=["最小权限和审计日志"],
                evidence=evidence,
                validation_actions=["运行代表性数据流和越权测试"],
            )
        ]
    )
    elements, views, traceability = _c4_and_traceability(
        "参考客户",
        "可验证 AI 场景",
        workbench,
        scenarios,
    )
    return ResearchArchitectureDecisionEngineeringOut(
        status="ready_for_review",
        summary="1.9.0 deterministic architecture decision contract regression.",
        quality_attribute_scenarios=scenarios,
        atam=_atam(scenarios, adrs),
        adrs=adrs,
        c4_elements=elements,
        c4_views=views,
        well_architected_checks=_well_architected(evidence),
        traceability_links=traceability,
        traceability_coverage_percent=100,
        orphan_component_count=0,
        high_risk_decision_count=sum(row.risk_level == "high" for row in adrs),
    )
