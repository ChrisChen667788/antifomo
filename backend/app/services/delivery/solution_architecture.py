from __future__ import annotations

from collections.abc import Iterable

from app.schemas.research import (
    ResearchArchitectureAdrTableRowOut,
    ResearchArchitectureDependencyWorkshopItemOut,
    ResearchArchitectureStakeholderBriefOut,
    ResearchArchitectureWorkshopAgendaItemOut,
    ResearchCustomerScenarioOut,
    ResearchDeliveryQualityMetricOut,
    ResearchMarketIntelligencePackOut,
    ResearchReportDocument,
    ResearchSolutionArchitectureBlueprintSectionOut,
    ResearchSolutionArchitectureDecisionRecordOut,
    ResearchSolutionArchitectureReadinessOut,
    ResearchSolutionArchitectureExportBundleOut,
    ResearchSolutionArchitectWorkbenchOut,
    ResearchSolutionCapabilityArchitectureMappingOut,
    ResearchSolutionDecisionCriterionOut,
    ResearchSolutionDeliveryPackOut,
    ResearchSolutionIntegrationDependencyOut,
    ResearchSolutionStakeholderOut,
)
from app.services.content_extractor import normalize_text
from app.services.delivery.decision_engineering import build_architecture_decision_engineering
from app.services.delivery.executable_validation import build_proof_of_architecture


_ARCHITECTURE_TERMS = ("架构", "接口", "API", "数据流", "系统边界", "集成", "中台", "私有化", "多租户", "运维")
_SECURITY_TERMS = ("安全", "等保", "信创", "密码", "数据安全", "网络安全", "权限", "审计", "隐私")
_AI_RUNTIME_TERMS = ("大模型", "RAG", "知识库", "数字人", "智能体", "GPU", "推理", "并发", "QPS", "时延")


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


def _metric_status(score: int, *, threshold: int = 75) -> str:
    if score >= threshold:
        return "pass"
    if score >= max(0, threshold - 14):
        return "watch"
    return "fail"


def _architecture_metric(
    *,
    key: str,
    label: str,
    score: int,
    summary: str,
    gaps: Iterable[object],
    actions: Iterable[object],
    threshold: int = 75,
) -> ResearchDeliveryQualityMetricOut:
    return ResearchDeliveryQualityMetricOut(
        key=key,
        label=label,
        score=max(0, min(int(score), 100)),
        threshold=threshold,
        status=_metric_status(score, threshold=threshold),  # type: ignore[arg-type]
        summary=summary,
        gaps=_dedupe_strings(gaps, limit=5),
        improvement_actions=_dedupe_strings(actions, limit=5),
    )


def _text_has_any(text: str, terms: Iterable[str]) -> bool:
    lowered = text.lower()
    return any(term.lower() in lowered for term in terms)


def _architecture_status(score: int) -> str:
    if score >= 84:
        return "ready"
    if score >= 68:
        return "watch"
    return "blocked"


def _blueprint_section(
    *,
    title: str,
    purpose: str,
    components: Iterable[object],
    evidence: Iterable[object],
    open_questions: Iterable[object],
) -> ResearchSolutionArchitectureBlueprintSectionOut:
    return ResearchSolutionArchitectureBlueprintSectionOut(
        title=title,
        purpose=purpose,
        components=_dedupe_strings(components, limit=8),
        evidence=_dedupe_strings(evidence, limit=5),
        open_questions=_dedupe_strings(open_questions, limit=5),
    )


def build_solution_architecture_readiness(
    report: ResearchReportDocument,
    *,
    market_pack: ResearchMarketIntelligencePackOut,
    pack: ResearchSolutionDeliveryPackOut,
) -> ResearchSolutionArchitectureReadinessOut:
    outline_text = normalize_text(
        " ".join(
            [
                *[section.title for section in pack.feasibility_outline],
                *[section.title for section in pack.project_proposal_outline],
                *[section.title for section in pack.client_ppt_outline],
                *[bullet for section in pack.feasibility_outline for bullet in section.bullets],
                *[bullet for section in pack.project_proposal_outline for bullet in section.bullets],
                *[bullet for section in pack.client_ppt_outline for bullet in section.bullets],
            ]
        )
    )
    technical_parameters = _dedupe_strings(
        [
            *(param for item in market_pack.technical_parameter_catalog for param in item.technical_parameters),
            *(param for item in market_pack.product_catalog for param in item.technical_parameters),
            *(param for item in market_pack.tender_projects for param in item.technical_parameters),
        ],
        limit=16,
    )
    product_names = _dedupe_strings(
        [
            *report.flagship_products,
            *(item.name for item in market_pack.product_catalog),
        ],
        limit=10,
    )
    integration_terms = [value for value in technical_parameters if _text_has_any(value, ("接口", "API", "SDK", "数据", "并发", "私有化"))]
    security_terms = [value for value in technical_parameters if _text_has_any(value, _SECURITY_TERMS)]
    runtime_terms = [value for value in technical_parameters if _text_has_any(value, _AI_RUNTIME_TERMS)]
    business_score = min(
        100,
        42
        + (16 if pack.target_customer else 0)
        + min(12, len(report.target_departments) * 3)
        + min(16, len(market_pack.tender_projects) * 4)
        + min(14, len(report.budget_signals) * 4),
    )
    architecture_score = min(
        100,
        40
        + min(18, len(product_names) * 4)
        + min(18, len(technical_parameters) * 3)
        + (12 if _text_has_any(outline_text, _ARCHITECTURE_TERMS) else 0)
        + (12 if len(pack.client_ppt_outline) >= 6 else 0),
    )
    integration_score = min(
        100,
        36
        + min(18, len(integration_terms) * 5)
        + min(12, len(report.target_departments) * 3)
        + (12 if "接口" in outline_text or "API" in outline_text else 0)
        + (10 if pack.next_steps else 0),
    )
    security_score = min(
        100,
        34
        + min(24, len(security_terms) * 6)
        + (18 if _text_has_any(outline_text, _SECURITY_TERMS) else 0)
        + min(12, len(pack.review_checklist) * 2),
    )
    delivery_score = min(
        100,
        40
        + min(14, len(report.tender_timeline) * 4)
        + min(14, len(report.budget_signals) * 4)
        + min(14, len(pack.advisory_artifacts) * 4)
        + min(18, len(pack.project_proposal_outline)),
    )
    metrics = [
        _architecture_metric(
            key="business_alignment",
            label="业务场景与客户约束",
            score=business_score,
            summary=f"目标客户：{pack.target_customer or '待确认'}；牵头部门 {len(report.target_departments)} 个；公开项目线索 {len(market_pack.tender_projects)} 条。",
            gaps=["客户、部门或预算口径仍不够明确。"] if business_score < 75 else [],
            actions=["补客户组织结构、牵头部门、预算边界和试点成功指标。"],
        ),
        _architecture_metric(
            key="architecture_completeness",
            label="架构拆解完整度",
            score=architecture_score,
            summary=f"产品/能力线索 {len(product_names)} 个，技术参数 {len(technical_parameters)} 条。",
            gaps=["缺少足够清晰的能力分层、模块边界或技术参数。"] if architecture_score < 75 else [],
            actions=["补业务层、应用层、模型/数据层、集成层、安全运维层的边界说明。"],
        ),
        _architecture_metric(
            key="integration_readiness",
            label="集成与数据接口准备",
            score=integration_score,
            summary=f"接口/API/数据相关线索 {len(integration_terms)} 条。",
            gaps=["需明确既有系统、数据源、接口协议、调用频率和责任边界。"] if integration_score < 75 else [],
            actions=["形成系统清单、接口清单、数据字段清单和集成依赖确认表。"],
        ),
        _architecture_metric(
            key="security_and_compliance",
            label="安全合规与非功能要求",
            score=security_score,
            summary=f"安全/信创/等保相关线索 {len(security_terms)} 条。",
            gaps=["安全、等保、信创、密码应用或数据治理要求仍需客户确认。"] if security_score < 75 else [],
            actions=["补等保等级、数据分类分级、部署形态、审计留痕和运维边界。"],
        ),
        _architecture_metric(
            key="delivery_feasibility",
            label="交付可落地性",
            score=delivery_score,
            summary=f"交付材料 {len(pack.advisory_artifacts)} 类，建议书章节 {len(pack.project_proposal_outline)} 个。",
            gaps=["交付里程碑、验收指标或材料责任分工仍不够细。"] if delivery_score < 75 else [],
            actions=["将试点、上线、验收、运维和培训拆成阶段目标与责任清单。"],
        ),
    ]
    overall_score = round(
        metrics[0].score * 0.2
        + metrics[1].score * 0.24
        + metrics[2].score * 0.2
        + metrics[3].score * 0.18
        + metrics[4].score * 0.18
    )
    status = _architecture_status(overall_score)
    customer = pack.target_customer or (report.target_accounts[0] if report.target_accounts else "待确认客户")
    scene = pack.vertical_scene or pack.scenario or report.keyword
    blueprint_sections = [
        _blueprint_section(
            title="业务与角色层",
            purpose="把客户场景、使用角色和试点边界固定下来，避免方案只停留在产品清单。",
            components=[customer, scene, *report.target_departments[:4], *report.leadership_focus[:2]],
            evidence=[report.executive_summary, *report.budget_signals[:2], *[item.project_name for item in market_pack.tender_projects[:2]]],
            open_questions=["谁是业务牵头人和技术牵头人？", "试点成功指标和推广条件是什么？"],
        ),
        _blueprint_section(
            title="应用能力层",
            purpose="沉淀可演示、可投标、可交付的核心功能模块。",
            components=[*product_names[:6], *report.strategic_directions[:3]],
            evidence=[*[item.source_context for item in market_pack.product_catalog[:3]], *report.benchmark_cases[:2]],
            open_questions=["哪些能力进入一期，哪些保留为二期？", "是否已有竞品或既有系统可复用？"],
        ),
        _blueprint_section(
            title="模型、数据与集成层",
            purpose="明确模型能力、知识库/数据源、接口边界和集成依赖。",
            components=[*runtime_terms[:4], *integration_terms[:4], "知识库/RAG", "接口编排"],
            evidence=[*technical_parameters[:4]],
            open_questions=["数据源归属和更新频率是什么？", "既有系统接口、鉴权和日志标准是否已明确？"],
        ),
        _blueprint_section(
            title="安全、部署与运维层",
            purpose="把安全合规、部署形态、运维责任和非功能指标前置到方案阶段。",
            components=[*security_terms[:5], "部署架构", "审计日志", "运维监控"],
            evidence=[*security_terms[:3], pack.evidence_policy],
            open_questions=["等保/信创/密码应用要求是否有硬性等级？", "运维、培训和故障响应由谁负责？"],
        ),
    ]
    non_functional_requirements = _dedupe_strings(
        [
            *technical_parameters,
            "明确并发、响应时延、可用性、扩展性、审计留痕、数据安全和运维 SLA。",
            "若采用大模型或数字人能力，需要补充推理资源、内容安全、知识更新和人工兜底机制。",
        ],
        limit=10,
    )
    integration_risks = _dedupe_strings(
        [
            "既有系统接口、数据字段、鉴权方式和日志规范未确认，可能影响实施排期。"
            if integration_score < 75
            else "",
            "安全合规要求未完全闭合，正式方案需客户或主管部门确认。"
            if security_score < 75
            else "",
            "公开招采或预算证据不足，外发材料中的预算和时间承诺需降级。"
            if market_pack.source_support_score < 70
            else "",
            *market_pack.intelligence_gaps[:3],
        ],
        limit=8,
    )
    assumptions = _dedupe_strings(
        [
            f"目标客户暂按 {customer} 处理。",
            f"垂直场景暂按 {scene} 处理。",
            "方案采用分期推进：需求确认、原型验证、试点上线、规模推广。",
            "所有预算、采购方式、安全等级和接口开放范围以客户正式材料为准。",
        ],
        limit=8,
    )
    validation_actions = _dedupe_strings(
        [
            "与客户确认业务流程、使用角色、试点范围和成功指标。",
            "拉取既有系统、数据源、接口、账号权限和日志审计清单。",
            "确认部署形态、等保/信创/密码应用要求和数据出域边界。",
            "把架构蓝图拆成一期 MVP、二期扩展和投标评分点响应矩阵。",
            *[action for metric in metrics for action in metric.improvement_actions[:1]],
        ],
        limit=10,
    )
    stakeholder_questions = _dedupe_strings(
        [
            "业务部门最希望先解决哪一个流程或指标？",
            "信息化部门能提供哪些系统接口、数据表和测试环境？",
            "安全/合规负责人对部署形态、日志、审计和数据权限有什么硬约束？",
            "采购或预算负责人希望以试点、平台建设还是服务采购方式推进？",
        ],
        limit=8,
    )
    summary = (
        f"面向 {customer} 的 {scene} 方案架构就绪度为 {overall_score}/100。"
        if status == "ready"
        else f"面向 {customer} 的 {scene} 方案架构仍需补齐接口、安全或交付边界，当前就绪度 {overall_score}/100。"
    )
    return ResearchSolutionArchitectureReadinessOut(
        overall_score=overall_score,
        status=status,  # type: ignore[arg-type]
        summary=summary,
        metrics=metrics,
        blueprint_sections=blueprint_sections,
        non_functional_requirements=non_functional_requirements,
        integration_risks=integration_risks,
        assumptions=assumptions,
        validation_actions=validation_actions,
        stakeholder_questions=stakeholder_questions,
    )


def _stakeholder_from_role(role: str, *, has_budget_signal: bool) -> ResearchSolutionStakeholderOut:
    normalized_role = normalize_text(role) or "业务牵头人"
    if any(term in normalized_role for term in ("数字化", "信息", "科技", "IT", "技术")):
        return ResearchSolutionStakeholderOut(
            role=normalized_role,
            influence="high",
            likely_concerns=["既有系统接口开放范围", "数据源质量和更新频率", "部署、账号和日志标准"],
            decision_questions=["哪些系统必须一期打通？", "是否能提供测试环境、接口文档和样例数据？"],
            required_materials=["系统清单", "接口清单", "数据字段样例", "部署拓扑草图"],
        )
    if any(term in normalized_role for term in ("安全", "合规", "法务", "审计")):
        return ResearchSolutionStakeholderOut(
            role=normalized_role,
            influence="medium",
            likely_concerns=["等保/信创/密码应用要求", "数据权限和审计留痕", "内容安全和人工兜底"],
            decision_questions=["是否存在数据出域或敏感数据处理限制？", "上线前需要通过哪些安全评审？"],
            required_materials=["安全合规清单", "数据分类分级说明", "日志审计方案"],
        )
    if any(term in normalized_role for term in ("采购", "预算", "财务", "招采")) or has_budget_signal:
        return ResearchSolutionStakeholderOut(
            role=normalized_role,
            influence="high",
            likely_concerns=["采购路径和预算口径", "评分点响应", "供应商资质和交付周期"],
            decision_questions=["本项目更适合试点、平台建设还是服务采购？", "预算、验收和付款节点如何设置？"],
            required_materials=["预算测算", "评分点响应矩阵", "分阶段报价口径"],
        )
    return ResearchSolutionStakeholderOut(
        role=normalized_role,
        influence="medium",
        likely_concerns=["业务流程改造成本", "一线使用体验", "试点指标和推广条件"],
        decision_questions=["先验证哪个场景和哪类用户？", "试点成功指标是什么？"],
        required_materials=["场景流程图", "试点范围说明", "用户旅程和成功指标"],
    )


def build_solution_architect_workbench(
    report: ResearchReportDocument,
    *,
    market_pack: ResearchMarketIntelligencePackOut,
    pack: ResearchSolutionDeliveryPackOut,
    architecture: ResearchSolutionArchitectureReadinessOut,
) -> ResearchSolutionArchitectWorkbenchOut:
    customer = pack.target_customer or (report.target_accounts[0] if report.target_accounts else "待确认客户")
    scene = pack.vertical_scene or pack.scenario or report.keyword
    product_names = _dedupe_strings(
        [
            *report.flagship_products,
            *(item.name for item in market_pack.product_catalog),
        ],
        limit=6,
    )
    technical_parameters = _dedupe_strings(
        [
            *(param for item in market_pack.technical_parameter_catalog for param in item.technical_parameters),
            *(param for item in market_pack.tender_projects for param in item.technical_parameters),
        ],
        limit=8,
    )
    architecture_business_evidence = (
        architecture.blueprint_sections[0].evidence[:2]
        if architecture.blueprint_sections
        else []
    )
    scenario = ResearchCustomerScenarioOut(
        name=scene,
        target_customer=customer,
        primary_roles=_dedupe_strings([*report.target_departments, "业务牵头人", "信息化负责人"], limit=6),
        pain_points=_dedupe_strings(
            [
                report.executive_summary,
                *market_pack.intelligence_gaps[:2],
                "公开材料显示需求、预算或招采口径仍需转成客户可确认的场景边界。",
            ],
            limit=5,
        ),
        desired_outcomes=_dedupe_strings(
            [
                *report.strategic_directions[:3],
                *product_names[:4],
                f"围绕 {scene} 形成可试点、可投标、可交付的方案蓝图。",
            ],
            limit=6,
        ),
        success_metrics=_dedupe_strings(
            [
                *technical_parameters[:4],
                "明确试点范围、用户角色、验收指标和规模化推广条件。",
                "在客户会议后拿到系统清单、接口清单、安全约束和预算口径确认。",
            ],
            limit=6,
        ),
        evidence=_dedupe_strings(
            [
                *report.budget_signals[:2],
                *[item.project_name for item in market_pack.tender_projects[:2]],
                *architecture_business_evidence,
            ],
            limit=6,
        ),
    )
    stakeholder_roles = _dedupe_strings(
        [
            *report.target_departments,
            "业务牵头人",
            "信息化负责人",
            "安全合规负责人",
            "采购/预算负责人",
        ],
        limit=6,
    )
    stakeholders = [
        _stakeholder_from_role(role, has_budget_signal=bool(report.budget_signals or market_pack.tender_projects))
        for role in stakeholder_roles
    ]
    decision_criteria = [
        ResearchSolutionDecisionCriterionOut(
            criterion="业务价值和试点边界",
            why_it_matters="决定方案是否能从泛化能力清单进入客户真实流程。",
            evidence=_dedupe_strings([report.executive_summary, *report.strategic_directions[:2]], limit=4),
            validation_action="在客户会上确认首批使用角色、流程节点、试点范围和成功指标。",
        ),
        ResearchSolutionDecisionCriterionOut(
            criterion="系统集成和数据可得性",
            why_it_matters="决定一期能否按期交付，也决定大模型/RAG/数字人能力能否稳定运行。",
            evidence=_dedupe_strings([*architecture.non_functional_requirements[:3], *technical_parameters[:2]], limit=5),
            validation_action="要求客户提供既有系统清单、接口文档、样例数据、鉴权方式和测试环境窗口。",
        ),
        ResearchSolutionDecisionCriterionOut(
            criterion="安全合规和部署形态",
            why_it_matters="影响私有化、云部署、数据出域、日志审计和上线评审路径。",
            evidence=_dedupe_strings(architecture.integration_risks[:3] + architecture.assumptions[:2], limit=5),
            validation_action="确认等保/信创/密码应用等级、数据分类分级、内容安全和人工审核机制。",
        ),
        ResearchSolutionDecisionCriterionOut(
            criterion="采购路径和交付节奏",
            why_it_matters="决定材料应包装成试点方案、平台建设建议书还是正式投标响应。",
            evidence=_dedupe_strings([*report.budget_signals[:2], *report.tender_timeline[:2]], limit=5),
            validation_action="对齐预算来源、采购方式、里程碑、验收口径和各阶段交付物。",
        ),
    ]
    base_evidence = _dedupe_strings(
        [
            report.executive_summary,
            *report.budget_signals[:2],
            *report.tender_timeline[:2],
            *[item.project_name for item in market_pack.tender_projects[:2]],
            *architecture_business_evidence,
        ],
        limit=8,
    )
    architecture_components = _dedupe_strings(
        [component for section in architecture.blueprint_sections for component in section.components],
        limit=12,
    )
    business_capabilities = _dedupe_strings(
        [
            *report.strategic_directions,
            scene,
            *product_names,
        ],
        limit=4,
    ) or [scene]
    data_dependencies = _dedupe_strings(
        [
            "客户业务数据、知识库资料、内容素材和运营指标",
            *[param for param in technical_parameters if any(term in param for term in ("数据", "接口", "API", "知识库"))],
            "测试环境样例数据与脱敏规则",
        ],
        limit=5,
    )
    model_dependencies = _dedupe_strings(
        [
            *[name for name in product_names if any(term in name for term in _AI_RUNTIME_TERMS)],
            *[param for param in technical_parameters if any(term in param for term in _AI_RUNTIME_TERMS)],
            "大模型/RAG/数字人能力按场景分层接入，正式选型以客户安全和成本边界为准。",
        ],
        limit=5,
    )
    integration_surfaces = _dedupe_strings(
        [
            "客户既有业务系统 API 或数据库视图",
            "统一身份认证、账号权限和组织架构",
            "内容管理、工单/CRM、数据看板或运营平台",
            *architecture.validation_actions[:2],
        ],
        limit=6,
    )
    security_constraints = _dedupe_strings(
        [
            *architecture.non_functional_requirements,
            "等保/信创/密码应用要求和数据出域边界需在方案冻结前确认。",
        ],
        limit=6,
    )
    capability_matrix = [
        ResearchSolutionCapabilityArchitectureMappingOut(
            business_capability=capability,
            application_services=_dedupe_strings(
                [
                    product_names[index % len(product_names)] if product_names else f"{capability}应用服务",
                    "运营管理后台",
                    "客户侧配置与报表工作台",
                    *architecture_components[:2],
                ],
                limit=5,
            ),
            data_dependencies=data_dependencies,
            model_dependencies=model_dependencies,
            integration_surfaces=integration_surfaces,
            security_constraints=security_constraints,
            evidence=base_evidence,
            validation_actions=_dedupe_strings(
                [
                    f"确认 {capability} 的首批业务角色、流程节点、数据输入和验收指标。",
                    "用客户系统清单逐项标注一期必须打通、二期可扩展和暂不接入的范围。",
                ],
                limit=4,
            ),
        )
        for index, capability in enumerate(business_capabilities)
    ]
    risk_level: str = "high" if architecture.status == "blocked" else "medium" if architecture.status == "watch" else "low"
    integration_dependencies = [
        ResearchSolutionIntegrationDependencyOut(
            dependency="核心业务流程和数据源接入",
            source_system="客户业务系统、内容库、知识库或运营数据平台",
            api_or_data_contract="API、数据库视图、文件交换或知识库导入模板需在一期试点前锁定。",
            auth_boundary="由客户信息化团队确认账号、组织架构、权限分级和接口调用凭证。",
            deployment_assumption="优先按客户安全边界选择私有化、专有云或内网部署。",
            operational_owner="信息化负责人",
            risk_level=risk_level,  # type: ignore[arg-type]
            validation_action="要求客户提供系统清单、接口文档、样例数据、测试环境窗口和数据脱敏规则。",
            evidence=_dedupe_strings([*data_dependencies, *base_evidence], limit=6),
        ),
        ResearchSolutionIntegrationDependencyOut(
            dependency="模型/RAG/数字人运行链路",
            source_system="模型服务、向量库、内容生成平台和知识库管理后台",
            api_or_data_contract="明确模型调用 API、知识库更新频率、召回评估口径和内容审核字段。",
            auth_boundary="模型访问、知识库编辑和内容发布权限需分角色配置并保留审计日志。",
            deployment_assumption="算力、并发、时延和可用性指标按试点容量先行测算。",
            operational_owner="技术架构负责人",
            risk_level=risk_level,  # type: ignore[arg-type]
            validation_action="在客户会上确认模型选型、知识库样本、并发指标、日志留存和人工兜底流程。",
            evidence=_dedupe_strings([*model_dependencies, *technical_parameters[:3]], limit=6),
        ),
        ResearchSolutionIntegrationDependencyOut(
            dependency="安全合规和上线评审",
            source_system="统一认证、日志审计、安全网关、内容安全和运维监控体系",
            api_or_data_contract="确认登录鉴权、接口白名单、审计字段、内容审核状态和告警事件格式。",
            auth_boundary="安全/合规负责人确认数据分类分级、出域限制、日志留存和人工复核责任。",
            deployment_assumption="上线前需预留安全测试、等保/信创材料和运维交接时间。",
            operational_owner="安全合规负责人",
            risk_level=risk_level,  # type: ignore[arg-type]
            validation_action="整理安全合规清单、部署拓扑、日志审计方案和上线评审材料责任人。",
            evidence=_dedupe_strings([*security_constraints, *architecture.integration_risks[:2]], limit=6),
        ),
    ]
    architecture_decision_records = [
        ResearchSolutionArchitectureDecisionRecordOut(
            decision="采用场景试点到平台化建设的分阶段架构路径",
            context=f"{customer} 的 {scene} 需要先证明业务价值，再扩展到更多角色、渠道和系统。",
            options=["一次性平台建设", "单点工具采购", "一期试点 + 二期平台化扩展"],
            selected_direction="一期试点 + 二期平台化扩展",
            tradeoffs=["能降低首次集成风险，但需要提前定义可复用能力边界。", "试点范围收窄后，二期预算和采购节奏必须同步规划。"],
            risks=["如果客户无法确认试点指标，平台化路线会缺少验收依据。"],
            validation_evidence=_dedupe_strings([*base_evidence, *report.strategic_directions[:2]], limit=6),
        ),
        ResearchSolutionArchitectureDecisionRecordOut(
            decision="采用 API-first 的系统集成和数据接入边界",
            context="解决方案能否落地取决于客户既有系统、数据源、权限和日志链路是否可接入。",
            options=["手工导入为主", "数据库直连为主", "API-first + 文件/视图补充"],
            selected_direction="API-first + 文件/视图补充",
            tradeoffs=["API-first 更利于权限和审计治理，但前期需要客户提供接口文档和测试窗口。"],
            risks=["接口开放范围、数据质量或测试环境不足会直接影响一期交付周期。"],
            validation_evidence=_dedupe_strings([*data_dependencies, *architecture.validation_actions[:2]], limit=6),
        ),
        ResearchSolutionArchitectureDecisionRecordOut(
            decision="安全合规和部署形态先于正式材料冻结",
            context="政企客户通常会把部署形态、数据出域、日志审计和上线评审作为方案可行性的前置条件。",
            options=["公有云优先", "私有化/专有云优先", "混合部署后置确认"],
            selected_direction="私有化/专有云优先，保留混合部署选项",
            tradeoffs=["更贴近安全评审和招采要求，但会增加算力、运维和交付成本测算工作。"],
            risks=["安全等级、信创和密码应用要求如果后置确认，可能导致方案返工。"],
            validation_evidence=_dedupe_strings([*security_constraints, *architecture.integration_risks[:2]], limit=6),
        ),
    ]
    agenda = _dedupe_strings(
        [
            f"确认 {customer} 的 {scene} 首批业务角色、流程和成功指标。",
            "拉通业务、信息化、安全合规、采购/预算四类干系人的问题清单。",
            "逐项核验系统清单、接口清单、数据样例、部署形态和安全要求。",
            "将架构蓝图拆成一期 MVP、二期扩展和正式投标/建议书材料责任分工。",
            "确认下一步材料：客户 brief、方案蓝图、ADR 决策表、阶段路线图和会议纪要。",
        ],
        limit=6,
    )
    return ResearchSolutionArchitectWorkbenchOut(
        customer_scenarios=[scenario],
        stakeholders=stakeholders,
        decision_criteria=decision_criteria,
        capability_architecture_matrix=capability_matrix,
        architecture_decision_records=architecture_decision_records,
        integration_dependencies=integration_dependencies,
        next_meeting_agenda=agenda,
    )


def _architecture_export_markdown(
    bundle: ResearchSolutionArchitectureExportBundleOut,
) -> str:
    lines = [
        "## 架构交付导出包",
        f"- 框架: {bundle.framework_label}",
        f"- ADR 决策: {len(bundle.adr_table)} 条",
        f"- 依赖 workshop 项: {len(bundle.dependency_workshop_checklist)} 条",
        f"- 技术 workshop 议程: {len(bundle.customer_technical_workshop_agenda)} 项",
        "",
        "### ADR 表",
        "| 决策 | 选定方向 | Owner | 状态 | 关键风险 |",
        "| --- | --- | --- | --- | --- |",
    ]
    for row in bundle.adr_table:
        lines.append(
            "| "
            + " | ".join(
                [
                    row.decision or "待补",
                    row.selected_direction or "待确认",
                    row.owner or "解决方案架构师",
                    row.status,
                    "；".join(row.risks[:2]) or "待补",
                ]
            )
            + " |"
        )
    lines.extend(["", "### 集成依赖 workshop 清单"])
    for item in bundle.dependency_workshop_checklist:
        lines.extend(
            [
                f"- {item.dependency}（{item.risk_level} / {item.owner or '待确认 owner'}）",
                f"  - 输入材料: {'；'.join(item.required_inputs[:4]) if item.required_inputs else '待补'}",
                f"  - 核心问题: {'；'.join(item.workshop_questions[:3]) if item.workshop_questions else '待补'}",
                f"  - 预期决策: {item.expected_decision or '待确认'}",
            ]
        )
    brief = bundle.stakeholder_brief
    lines.extend(
        [
            "",
            "### Stakeholder Brief",
            f"- 标题: {brief.title or '待补'}",
            f"- 受众: {brief.audience or '待确认'}",
            f"- 摘要: {brief.summary or '待补'}",
            "- 关键信息:",
            *[f"  - {message}" for message in brief.key_messages],
            "- 决策问题:",
            *[f"  - {question}" for question in brief.stakeholder_questions[:6]],
        ]
    )
    lines.extend(["", "### 客户技术 workshop 议程"])
    for item in bundle.customer_technical_workshop_agenda:
        lines.extend(
            [
                f"- {item.topic}（{item.duration_minutes} 分钟 / {item.owner or '待确认 owner'}）",
                f"  - 问题: {'；'.join(item.questions[:3]) if item.questions else '待补'}",
                f"  - 输出: {'；'.join(item.expected_outputs[:3]) if item.expected_outputs else '待补'}",
            ]
        )
    return "\n".join(lines).strip()


def build_solution_architecture_export_bundle(
    report: ResearchReportDocument,
    *,
    market_pack: ResearchMarketIntelligencePackOut,
    pack: ResearchSolutionDeliveryPackOut,
    architecture: ResearchSolutionArchitectureReadinessOut,
    workbench: ResearchSolutionArchitectWorkbenchOut,
) -> ResearchSolutionArchitectureExportBundleOut:
    customer = pack.target_customer or (report.target_accounts[0] if report.target_accounts else "待确认客户")
    scene = pack.vertical_scene or pack.scenario or report.keyword
    adr_rows = [
        ResearchArchitectureAdrTableRowOut(
            decision=record.decision,
            context=record.context,
            selected_direction=record.selected_direction,
            options=record.options,
            tradeoffs=record.tradeoffs,
            risks=record.risks,
            validation_evidence=record.validation_evidence,
            owner="解决方案架构师",
            status="review_ready" if record.validation_evidence else "draft",
        )
        for record in workbench.architecture_decision_records
    ]
    dependency_items = [
        ResearchArchitectureDependencyWorkshopItemOut(
            dependency=dependency.dependency,
            owner=dependency.operational_owner or "待确认 owner",
            risk_level=dependency.risk_level,
            source_system=dependency.source_system,
            required_inputs=_dedupe_strings(
                [
                    dependency.api_or_data_contract,
                    dependency.auth_boundary,
                    dependency.deployment_assumption,
                    *dependency.evidence[:3],
                ],
                limit=6,
            ),
            workshop_questions=_dedupe_strings(
                [
                    f"{dependency.source_system or dependency.dependency} 的当前责任 owner 是谁？",
                    "一期必须打通、二期可延后和暂不接入的边界分别是什么？",
                    "测试环境、样例数据、权限申请和安全评审窗口何时可用？",
                    dependency.validation_action,
                ],
                limit=5,
            ),
            expected_decision="确认 owner、输入材料、接口/数据契约、风险等级和下一步验证动作。",
            validation_action=dependency.validation_action,
            evidence=dependency.evidence,
        )
        for dependency in workbench.integration_dependencies
    ]
    stakeholder_questions = _dedupe_strings(
        [
            question
            for stakeholder in workbench.stakeholders
            for question in stakeholder.decision_questions
        ],
        limit=10,
    )
    required_materials = _dedupe_strings(
        [
            material
            for stakeholder in workbench.stakeholders
            for material in stakeholder.required_materials
        ],
        limit=10,
    )
    decision_criteria = _dedupe_strings(
        [
            f"{criterion.criterion}: {criterion.validation_action or criterion.why_it_matters}"
            for criterion in workbench.decision_criteria
        ],
        limit=8,
    )
    stakeholder_brief = ResearchArchitectureStakeholderBriefOut(
        title=f"{customer} {scene} stakeholder brief",
        audience="业务牵头人 / 信息化负责人 / 安全合规负责人 / 采购预算负责人",
        summary=(
            f"围绕 {scene} 把业务价值、系统集成、安全合规和采购节奏拆成可确认问题，"
            "用于客户会前对齐和会后材料责任分工。"
        ),
        key_messages=_dedupe_strings(
            [
                architecture.summary,
                report.executive_summary,
                f"架构就绪度 {architecture.overall_score}/100，状态 {architecture.status}。",
                f"来源支撑度 {pack.source_support_score}/100，正式对客前按证据口径处理假设。",
                *pack.intelligence_summary[:2],
            ],
            limit=6,
        ),
        stakeholder_questions=stakeholder_questions,
        required_materials=required_materials,
        decision_criteria=decision_criteria,
    )
    agenda_items: list[ResearchArchitectureWorkshopAgendaItemOut] = []
    for index, criterion in enumerate(workbench.decision_criteria[:4], start=1):
        agenda_items.append(
            ResearchArchitectureWorkshopAgendaItemOut(
                topic=criterion.criterion,
                owner="解决方案架构师" if index == 1 else "客户侧 owner",
                duration_minutes=20 if index <= 2 else 15,
                questions=_dedupe_strings(
                    [
                        criterion.validation_action,
                        criterion.why_it_matters,
                        *stakeholder_questions[index - 1 : index + 2],
                    ],
                    limit=4,
                ),
                expected_outputs=_dedupe_strings(
                    [
                        "确认可写入方案的事实、假设和待核验项。",
                        "形成下一步材料责任人和时间点。",
                        *(criterion.evidence[:2] or []),
                    ],
                    limit=4,
                ),
                source_refs=criterion.evidence,
            )
        )
    for dependency in dependency_items[:3]:
        agenda_items.append(
            ResearchArchitectureWorkshopAgendaItemOut(
                topic=f"依赖确认：{dependency.dependency}",
                owner=dependency.owner,
                duration_minutes=15,
                questions=dependency.workshop_questions,
                expected_outputs=[
                    dependency.expected_decision,
                    dependency.validation_action or "输出依赖确认结论和风险处理方式。",
                ],
                source_refs=dependency.evidence,
            )
        )
    if not agenda_items:
        agenda_items.append(
            ResearchArchitectureWorkshopAgendaItemOut(
                topic=f"{customer} {scene} 技术边界确认",
                owner="解决方案架构师",
                duration_minutes=30,
                questions=architecture.stakeholder_questions[:4],
                expected_outputs=["确认系统边界、数据边界、安全边界和下一步材料责任。"],
                source_refs=[market_pack.source_scope_summary],
            )
        )
    bundle = ResearchSolutionArchitectureExportBundleOut(
        adr_table=adr_rows,
        dependency_workshop_checklist=dependency_items,
        stakeholder_brief=stakeholder_brief,
        customer_technical_workshop_agenda=agenda_items[:8],
    )
    bundle.export_markdown = _architecture_export_markdown(bundle)
    return bundle


def build_solution_architecture_delivery(
    report: ResearchReportDocument,
    *,
    market_pack: ResearchMarketIntelligencePackOut,
    pack: ResearchSolutionDeliveryPackOut,
) -> ResearchSolutionDeliveryPackOut:
    architecture = build_solution_architecture_readiness(report, market_pack=market_pack, pack=pack)
    workbench = build_solution_architect_workbench(
        report,
        market_pack=market_pack,
        pack=pack,
        architecture=architecture,
    )
    export_bundle = build_solution_architecture_export_bundle(
        report,
        market_pack=market_pack,
        pack=pack,
        architecture=architecture,
        workbench=workbench,
    )
    engineering = build_architecture_decision_engineering(
        report,
        pack=pack,
        architecture=architecture,
        workbench=workbench,
    )
    proof = build_proof_of_architecture(report, engineering=engineering)
    return pack.model_copy(
        update={
            "architecture_readiness": architecture,
            "architect_workbench": workbench,
            "architecture_export_bundle": export_bundle,
            "architecture_decision_engineering": engineering,
            "proof_of_architecture": proof,
        }
    )
