from __future__ import annotations

from collections.abc import Iterable, Sequence

from app.schemas.research import (
    ResearchDeliveryCompiledDocumentOut,
    ResearchDeliveryCompiledSectionOut,
    ResearchMarketIntelligencePackOut,
    ResearchReportDocument,
    ResearchSolutionOutlineSectionOut,
)
from app.services.content_extractor import normalize_text


DocumentKind = str


def _dedupe_strings(values: Iterable[object], *, limit: int = 10) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = normalize_text(str(value or ""))
        if not text or text in seen:
            continue
        rows.append(text)
        seen.add(text)
        if len(rows) >= limit:
            break
    return rows


def _section(
    title: str,
    *,
    purpose: str,
    bullets: Iterable[object],
    evidence: Iterable[object] = (),
    assumptions: Iterable[object] = (),
    validation_actions: Iterable[object] = (),
    limit: int = 8,
) -> ResearchDeliveryCompiledSectionOut:
    return ResearchDeliveryCompiledSectionOut(
        title=title,
        purpose=normalize_text(purpose),
        bullets=_dedupe_strings(bullets, limit=limit),
        evidence=_dedupe_strings(evidence, limit=6),
        assumptions=_dedupe_strings(assumptions, limit=5),
        validation_actions=_dedupe_strings(validation_actions, limit=5),
    )


def _markdown(document: ResearchDeliveryCompiledDocumentOut) -> str:
    lines = [
        f"# {document.title}",
        "",
        f"- 文档类型: {document.document_kind}",
        f"- 编译器: {document.framework}",
        f"- 受众: {document.audience or '待确认'}",
        f"- 用途: {document.purpose or '待确认'}",
        f"- 证据口径: {document.evidence_policy or '正式外发前需完成证据复核。'}",
    ]
    if document.quality_gates:
        lines.extend(["", "## 质量门槛", *[f"- {item}" for item in document.quality_gates]])
    for section in document.sections:
        lines.extend(["", f"## {section.title}"])
        if section.purpose:
            lines.append(f"> {section.purpose}")
        lines.extend([f"- {item}" for item in section.bullets])
        if section.evidence:
            lines.extend(["", "证据锚点：", *[f"- {item}" for item in section.evidence]])
        if section.assumptions:
            lines.extend(["", "关键假设：", *[f"- {item}" for item in section.assumptions]])
        if section.validation_actions:
            lines.extend(["", "验证动作：", *[f"- {item}" for item in section.validation_actions]])
    if document.assumptions:
        lines.extend(["", "## 全局假设", *[f"- {item}" for item in document.assumptions]])
    if document.validation_actions:
        lines.extend(["", "## 放行前验证动作", *[f"- {item}" for item in document.validation_actions]])
    return "\n".join(lines).strip()


def _document(
    *,
    framework: str,
    document_kind: str,
    title: str,
    audience: str,
    purpose: str,
    evidence_policy: str,
    sections: Sequence[ResearchDeliveryCompiledSectionOut],
    assumptions: Iterable[object],
    validation_actions: Iterable[object],
    quality_gates: Iterable[object],
) -> ResearchDeliveryCompiledDocumentOut:
    document = ResearchDeliveryCompiledDocumentOut(
        framework=framework,  # type: ignore[arg-type]
        document_kind=document_kind,  # type: ignore[arg-type]
        title=normalize_text(title),
        audience=normalize_text(audience),
        purpose=normalize_text(purpose),
        evidence_policy=normalize_text(evidence_policy),
        sections=list(sections),
        assumptions=_dedupe_strings(assumptions, limit=8),
        validation_actions=_dedupe_strings(validation_actions, limit=8),
        quality_gates=_dedupe_strings(quality_gates, limit=8),
    )
    return document.model_copy(update={"export_markdown": _markdown(document)})


def _top_projects(market_pack: ResearchMarketIntelligencePackOut, *, limit: int = 4) -> list[str]:
    return [
        f"{item.project_name}（{item.notice_type or '公开线索'} / {item.publish_date or '日期待核验'} / {item.amount or '金额待核验'}）"
        for item in market_pack.tender_projects[:limit]
    ]


def _product_rows(market_pack: ResearchMarketIntelligencePackOut, *, limit: int = 6) -> list[str]:
    return [
        f"{item.name}：{'；'.join(item.technical_parameters[:3]) if item.technical_parameters else item.source_context or '参数待核验'}"
        for item in market_pack.product_catalog[:limit]
    ]


def _parameter_rows(market_pack: ResearchMarketIntelligencePackOut, *, limit: int = 8) -> list[str]:
    return _dedupe_strings(
        [
            parameter
            for item in market_pack.technical_parameter_catalog
            for parameter in item.technical_parameters[:3]
        ],
        limit=limit,
    )


def _evidence_rows(report: ResearchReportDocument, market_pack: ResearchMarketIntelligencePackOut) -> list[str]:
    return _dedupe_strings(
        [
            market_pack.source_scope_summary,
            *[source.title for source in report.sources[:6]],
            *_top_projects(market_pack, limit=4),
            *market_pack.intelligence_gaps[:3],
        ],
        limit=10,
    )


def _base_assumptions(
    report: ResearchReportDocument,
    *,
    scenario: str,
    target_customer: str,
    vertical_scene: str,
) -> list[str]:
    return _dedupe_strings(
        [
            f"目标客户暂按“{target_customer}”处理，正式版本以客户或官方材料确认为准。" if target_customer else "",
            f"建设场景暂按“{scenario} / {vertical_scene}”处理，超出范围的类比案例仅作为参考。",
            "预算、周期、绩效和安全合规判断必须以公开来源、客户材料或评审意见放行。",
            *report.technical_appendix.limitations[:3],
        ],
        limit=8,
    )


def build_solution_design_document(
    report: ResearchReportDocument,
    *,
    market_pack: ResearchMarketIntelligencePackOut,
    scenario: str,
    target_customer: str,
    vertical_scene: str,
    evidence_policy: str,
) -> ResearchDeliveryCompiledDocumentOut:
    customer = target_customer or (report.target_accounts[0] if report.target_accounts else "待确认客户")
    scene = vertical_scene or report.research_focus or scenario
    sections = [
        _section(
            "一、业务目标、范围边界与成功指标",
            purpose="锁定解决方案要解决的问题、一期边界和可验收结果。",
            bullets=[
                f"目标客户：{customer}",
                f"业务场景：{scenario} / {scene}",
                report.executive_summary,
                *report.strategic_directions[:3],
                "将目标拆成业务覆盖、效率、质量、用户体验和合规安全五类指标。",
            ],
            evidence=_evidence_rows(report, market_pack),
            assumptions=_base_assumptions(report, scenario=scenario, target_customer=customer, vertical_scene=scene),
            validation_actions=["客户确认一期范围、牵头部门、用户群体、存量系统和成功指标。"],
        ),
        _section(
            "二、客户场景、角色旅程与核心用例",
            purpose="把抽象机会翻译成用户、流程和用例。",
            bullets=[
                *report.project_distribution[:3],
                *report.target_departments[:4],
                "按业务负责人、一线使用者、运维人员、安全/数据负责人拆分旅程和问题。",
                "每个核心用例给出触发条件、输入数据、处理流程、输出结果和异常兜底。",
            ],
            evidence=_top_projects(market_pack),
            validation_actions=["访谈业务、技术、数据和安全负责人，确认用例优先级和演示脚本。"],
        ),
        _section(
            "三、能力架构与产品/模块映射",
            purpose="形成可交付的能力地图，避免只列产品名。",
            bullets=[
                *_product_rows(market_pack),
                *report.flagship_products[:4],
                "将能力拆分为接入层、业务应用层、智能服务层、数据知识层、运维安全层。",
            ],
            evidence=_product_rows(market_pack),
            validation_actions=["确认已有系统复用边界、需新建模块、第三方组件和二次开发工作量。"],
            limit=10,
        ),
        _section(
            "四、数据、模型、接口与集成架构",
            purpose="明确数据来源、模型能力、接口契约和集成风险。",
            bullets=[
                *_parameter_rows(market_pack),
                "列出数据源、主数据、知识库、模型调用、API 接口、权限边界和审计日志。",
                "对接存量系统时明确调用方向、字段口径、认证方式、同步频率和失败补偿。",
            ],
            evidence=_parameter_rows(market_pack),
            assumptions=["接口协议、字段、权限和网络边界未确认前，不承诺上线周期。"],
            validation_actions=["拉通接口清单、数据样本、权限矩阵和网络拓扑。"],
            limit=10,
        ),
        _section(
            "五、NFR、安全合规、信创与运维要求",
            purpose="把非功能要求前置为设计约束。",
            bullets=[
                "明确可用性、性能、并发、容量、可观测性、日志审计、灾备和扩展性要求。",
                "覆盖网络安全、数据安全、等保、密码应用、信创适配和个人信息保护。",
                *report.technical_appendix.limitations[:3],
            ],
            evidence=_evidence_rows(report, market_pack),
            validation_actions=["安全、数据、信创和运维负责人确认 NFR 基线与例外审批机制。"],
        ),
        _section(
            "六、实施路线、验收方案与运维交接",
            purpose="把方案变成可执行项目计划。",
            bullets=[
                *report.tender_timeline[:4],
                "建议分为调研确认、原型验证、试点上线、验收推广、运营优化五阶段。",
                "验收指标应覆盖功能、性能、数据、模型效果、安全合规和用户体验。",
            ],
            evidence=_top_projects(market_pack),
            validation_actions=["确认里程碑、验收口径、责任人、运维交接和变更控制流程。"],
        ),
        _section(
            "七、证据矩阵、风险清单与待核验项",
            purpose="为外发版保留证据边界和人工复核入口。",
            bullets=[
                market_pack.source_scope_summary,
                *market_pack.intelligence_gaps[:4],
                "强主张必须绑定 URL、文号、项目编号或 source/chunk ID；证据不足则降级为假设。",
            ],
            evidence=_evidence_rows(report, market_pack),
            validation_actions=["交付前逐项核对主张—证据账本和语义挑战者结果。"],
        ),
    ]
    return _document(
        framework="solution_design_compiler_v1",
        document_kind="solution_design",
        title=f"{customer}{scenario}解决方案设计",
        audience="客户业务负责人、信息化负责人、解决方案架构师、交付 PM",
        purpose="形成可评审、可实施、可验收的解决方案设计稿。",
        evidence_policy=evidence_policy,
        sections=sections,
        assumptions=_base_assumptions(report, scenario=scenario, target_customer=customer, vertical_scene=scene),
        validation_actions=[
            "确认业务目标、用户范围、系统边界、接口清单、NFR 和安全合规要求。",
            "用主张—证据账本复核预算、周期、绩效和技术参数。",
        ],
        quality_gates=[
            "必须包含业务目标、场景用例、能力架构、数据/模型/接口、NFR、安全、实施和验收。",
            "任何上线承诺必须对应责任主体、前置条件和验证动作。",
        ],
    )


def build_consulting_report_document(
    report: ResearchReportDocument,
    *,
    market_pack: ResearchMarketIntelligencePackOut,
    scenario: str,
    target_customer: str,
    vertical_scene: str,
    evidence_policy: str,
) -> ResearchDeliveryCompiledDocumentOut:
    customer = target_customer or (report.target_accounts[0] if report.target_accounts else "目标客户待确认")
    sections = [
        _section(
            "一、结论先行与管理层摘要",
            purpose="用 SCQA 方式给出可决策的咨询结论。",
            bullets=[
                f"情境：{customer} 正在评估 {scenario} / {vertical_scene or report.research_focus}。",
                f"冲突：{report.consulting_angle}",
                f"答案：{report.commercial_summary.next_action}",
                report.executive_summary,
            ],
            evidence=_evidence_rows(report, market_pack),
            validation_actions=["确认管理层真正要决策的问题、时间窗口和不可触碰约束。"],
        ),
        _section(
            "二、问题树、假设台账与分析边界",
            purpose="拆出问题树，避免泛泛总结。",
            bullets=[
                "问题树：市场/政策机会、客户痛点、技术可行性、采购路径、竞争态势、落地风险。",
                *report.leadership_focus[:3],
                *report.budget_signals[:3],
                "每个假设标注证据等级、反证线索和下一步验证动作。",
            ],
            assumptions=_base_assumptions(report, scenario=scenario, target_customer=customer, vertical_scene=vertical_scene),
            validation_actions=["用客户访谈和公开招采复核问题树是否完整。"],
        ),
        _section(
            "三、洞察发现、证据与反方观点",
            purpose="把事实、洞察和反方证据分层展示。",
            bullets=[
                *_top_projects(market_pack),
                *market_pack.intelligence_gaps[:4],
                *report.competition_analysis[:4],
                "对每条强洞察补充反方解释：是否只是行业趋势、是否缺少客户预算、是否存在替代方案。",
            ],
            evidence=_evidence_rows(report, market_pack),
            validation_actions=["对官方源、行业媒体、企业材料和微信公众号线索做交叉验证。"],
            limit=10,
        ),
        _section(
            "四、战略选项、权衡矩阵与推荐路径",
            purpose="给出可选择方案，而不是单一路径。",
            bullets=[
                "选项 A：维持观察，仅补客户关系和需求访谈。",
                "选项 B：分期试点，先验证高价值场景和集成边界。",
                "选项 C：整体建设，前提是预算、数据、安全和组织责任已锁定。",
                *report.benchmark_cases[:3],
            ],
            evidence=_top_projects(market_pack),
            assumptions=["没有预算和接口确认前，整体建设只能作为条件性方案。"],
            validation_actions=["用成本、周期、风险、收益、组织复杂度和可复制性打分。"],
        ),
        _section(
            "五、行动路线、责任分工与 30/60/90 天计划",
            purpose="把咨询建议转成推进动作。",
            bullets=[
                "30 天：客户访谈、范围确认、证据补齐、演示脚本和技术边界确认。",
                "60 天：试点方案、投资测算、项目建议书、采购路径和风险清单。",
                "90 天：原型验证、评审材料、预算/采购放行、实施计划。",
                *report.tender_timeline[:3],
            ],
            validation_actions=["明确每项行动的 owner、输入材料、输出物和截止时间。"],
        ),
        _section(
            "六、风险、待核验项与放行条件",
            purpose="防止咨询报告把弱证据包装成确定结论。",
            bullets=[
                *report.technical_appendix.limitations[:4],
                *market_pack.intelligence_gaps[:4],
                "预算、绩效、周期、安全合规和客户意向必须进入待核验清单。",
            ],
            validation_actions=["正式外发前通过语义挑战者、证据账本和人工审阅。"],
        ),
    ]
    return _document(
        framework="consulting_report_compiler_v1",
        document_kind="consulting_report",
        title=f"{customer}{scenario}咨询研判报告",
        audience="管理层、行业咨询顾问、售前负责人、BD/战略团队",
        purpose="围绕决策问题输出洞察、选项、权衡、建议和行动计划。",
        evidence_policy=evidence_policy,
        sections=sections,
        assumptions=_base_assumptions(report, scenario=scenario, target_customer=customer, vertical_scene=vertical_scene),
        validation_actions=[
            "补齐客户一手访谈、预算窗口、竞争态势和反方证据。",
            "用选项权衡矩阵复核推荐路径是否可辩护。",
        ],
        quality_gates=[
            "必须包含 SCQA、问题树、假设、洞察、反方观点、选项、建议和行动计划。",
            "不得只输出信息摘要；每条建议必须有证据或验证动作。",
        ],
    )


def build_project_proposal_document(
    report: ResearchReportDocument,
    *,
    market_pack: ResearchMarketIntelligencePackOut,
    scenario: str,
    target_customer: str,
    vertical_scene: str,
    evidence_policy: str,
) -> ResearchDeliveryCompiledDocumentOut:
    customer = target_customer or (report.target_accounts[0] if report.target_accounts else "待确认建设单位")
    sections = [
        _section(
            "一、项目背景、编制依据与立项必要性",
            purpose="说明为什么现在要立项，依据是什么。",
            bullets=[report.executive_summary, market_pack.source_scope_summary, report.consulting_angle, *_top_projects(market_pack)],
            evidence=_evidence_rows(report, market_pack),
            validation_actions=["补充政策、规划、预算、客户内部材料和主管部门要求。"],
            limit=10,
        ),
        _section(
            "二、现状差距、需求分析与建设目标",
            purpose="从现状问题推导建设目标。",
            bullets=[
                f"目标客户/建设单位：{customer}",
                f"项目场景：{scenario} / {vertical_scene or report.research_focus}",
                *report.leadership_focus[:3],
                *report.strategic_directions[:4],
                "目标应拆为业务目标、能力目标、数据目标、安全目标和绩效目标。",
            ],
            validation_actions=["客户确认现状流程、用户范围、目标值和约束条件。"],
        ),
        _section(
            "三、建设内容、产出清单与绩效指标",
            purpose="明确项目要建设什么、产出什么、如何验收。",
            bullets=[*report.project_distribution[:4], *_product_rows(market_pack), "建立章节—产出—绩效—证据—责任人映射。"],
            evidence=_product_rows(market_pack),
            validation_actions=["逐项确认软件、硬件/算力、集成、安全、培训和运维范围。"],
            limit=10,
        ),
        _section(
            "四、方案比选、推荐路径与实施边界",
            purpose="体现项目建议书的决策过程。",
            bullets=[
                "比较维持现状、分期试点、整体建设三种路径。",
                "推荐路径必须说明成本、周期、收益、风险、组织复杂度和扩展性。",
                *report.benchmark_cases[:3],
            ],
            validation_actions=["补充比选矩阵，并明确推荐方案生效条件。"],
        ),
        _section(
            "五、技术方案、系统边界与安全合规",
            purpose="给出建设方案和合规边界。",
            bullets=[
                *report.flagship_products[:4],
                *_parameter_rows(market_pack),
                "说明总体架构、系统接口、数据治理、等保、密码、信创、隐私和运维安全。",
            ],
            evidence=_parameter_rows(market_pack),
            validation_actions=["安全、数据、运维和既有系统负责人确认边界。"],
            limit=10,
        ),
        _section(
            "六、采购实施、里程碑、组织机制与运营方案",
            purpose="明确实施组织和后续运营。",
            bullets=[
                *report.tender_timeline[:4],
                *report.target_departments[:4],
                "明确采购范围、里程碑、验收安排、运营责任、服务等级和问题闭环。",
            ],
            validation_actions=["确认采购方式、招采窗口、评审责任和运维经费。"],
        ),
        _section(
            "七、投资测算、资金口径、绩效目标与综合效益",
            purpose="给出投资与效益口径，不生成伪精确数字。",
            bullets=[
                *report.budget_signals[:4],
                *report.five_year_outlook[:3],
                "按软件平台、硬件/算力、集成实施、安全专项、运营运维、培训推广拆分。",
                "数据不足时输出假设表、取值范围和待补数据，不输出伪精确 ROI。",
            ],
            evidence=_evidence_rows(report, market_pack),
            assumptions=["投资测算需以客户预算、同类招采和供应商报价复核。"],
            validation_actions=["补 CAPEX/OPEX/TCO 基础数据和绩效目标测量口径。"],
            limit=10,
        ),
        _section(
            "八、风险控制、验收安排、证据矩阵与待确认事项",
            purpose="形成建议书的放行清单。",
            bullets=[
                *report.technical_appendix.limitations[:4],
                *market_pack.intelligence_gaps[:4],
                "预算、安全、采购周期、接口兼容、数据质量和推广应用风险必须逐项进入台账。",
            ],
            evidence=_evidence_rows(report, market_pack),
            validation_actions=["通过主张—证据账本、语义挑战者和人工审阅后再生成外发版。"],
        ),
    ]
    return _document(
        framework="project_proposal_compiler_v1",
        document_kind="project_proposal",
        title=f"{customer}{scenario}项目建议书",
        audience="建设单位、主管部门、项目评审人员、售前/项目负责人",
        purpose="支撑立项沟通、项目范围确认、投资估算和后续可研/招采准备。",
        evidence_policy=evidence_policy,
        sections=sections,
        assumptions=_base_assumptions(report, scenario=scenario, target_customer=customer, vertical_scene=vertical_scene),
        validation_actions=[
            "确认立项依据、建设范围、投资口径、绩效目标、采购方式和风险边界。",
            "用证据矩阵把每个关键结论映射到来源或待核验动作。",
        ],
        quality_gates=[
            "必须覆盖立项必要性、目标、建设内容、实施采购、投资绩效、风险和证据。",
            "预算和绩效不得无来源强承诺；必须能降级为假设。",
        ],
    )


def build_feasibility_study_document(
    report: ResearchReportDocument,
    *,
    market_pack: ResearchMarketIntelligencePackOut,
    scenario: str,
    target_customer: str,
    vertical_scene: str,
    evidence_policy: str,
) -> ResearchDeliveryCompiledDocumentOut:
    customer = target_customer or (report.target_accounts[0] if report.target_accounts else "待确认业主")
    sections = [
        _section(
            "一、项目概况、研究依据与范围边界",
            purpose="锁定可研对象、依据、范围和边界。",
            bullets=[
                f"项目/方案场景：{scenario}",
                f"建议业主/建设单位：{customer}",
                f"垂直场景：{vertical_scene or report.research_focus}",
                market_pack.source_scope_summary,
                report.executive_summary,
            ],
            evidence=_evidence_rows(report, market_pack),
            validation_actions=["补政策依据、客户材料、主管部门意见和已有系统台账。"],
        ),
        _section(
            "二、现状评价、需求预测与建设必要性",
            purpose="从现状、需求和趋势论证必要性。",
            bullets=[report.consulting_angle, *report.leadership_focus[:3], *report.budget_signals[:3], *_top_projects(market_pack)],
            evidence=_top_projects(market_pack),
            validation_actions=["补业务量、用户量、服务质量、成本基线和未来需求预测。"],
            limit=10,
        ),
        _section(
            "三、建设目标、内容、产出与验收指标",
            purpose="定义可验收建设内容。",
            bullets=[
                *report.strategic_directions[:4],
                *report.project_distribution[:4],
                "验收指标覆盖功能、性能、数据、模型效果、安全合规、运营服务和用户体验。",
            ],
            validation_actions=["客户确认目标值、验收方法、数据来源和责任部门。"],
        ),
        _section(
            "四、方案比选、推荐方案与技术可行性",
            purpose="可研必须证明推荐方案比替代方案更合理。",
            bullets=[
                "比选维持现状、分期试点、整体建设三种方案。",
                "比较 CAPEX、OPEX、周期、风险、收益、扩展性、组织复杂度和可运维性。",
                *_product_rows(market_pack),
                *report.benchmark_cases[:3],
            ],
            evidence=_product_rows(market_pack),
            validation_actions=["补技术路线、架构图、接口清单、部署方案和方案比选矩阵。"],
            limit=10,
        ),
        _section(
            "五、组织实施、采购交付、运营维护与安全合规可行性",
            purpose="证明项目可组织、可采购、可运营、可合规。",
            bullets=[
                *report.tender_timeline[:4],
                *report.target_departments[:4],
                "说明采购边界、实施组织、运维机制、数据治理、等保、密码、信创和安全审计。",
            ],
            validation_actions=["确认采购方式、实施周期、组织职责、运维预算和安全评审路径。"],
        ),
        _section(
            "六、投资估算、CAPEX/OPEX/TCO、收益测算与敏感性分析",
            purpose="建立可复算的财务和投入产出口径。",
            bullets=[
                *report.budget_signals[:4],
                "CAPEX：平台软件、硬件/算力、集成实施、安全专项、数据治理、培训推广。",
                "OPEX：云/算力、模型调用、运维、内容/知识更新、安全运营和持续优化。",
                "TCO、收益、回收期、NPV/IRR 仅在数据充分时输出；否则输出假设表和敏感性变量。",
            ],
            evidence=_evidence_rows(report, market_pack),
            assumptions=["财务模型需补单价、数量、周期、税费、折现率和收益归因数据。"],
            validation_actions=["补基准、乐观、悲观三情景，并给出可复算表。"],
            limit=10,
        ),
        _section(
            "七、经济、社会、资源能源、生态环境与安全影响评价",
            purpose="覆盖可研影响评价维度。",
            bullets=[
                *report.five_year_outlook[:4],
                "经济影响关注成本节约、效率提升和投资合理性。",
                "社会影响关注服务体验、公平可及、组织协同和公共价值。",
                "安全影响关注数据、网络、模型、供应链和运营连续性。",
            ],
            validation_actions=["为每项影响定义基线、目标、数据来源、测量周期和责任人。"],
        ),
        _section(
            "八、风险控制、结论建议、证据矩阵与附件清单",
            purpose="形成可研结论和放行条件。",
            bullets=[
                *report.technical_appendix.limitations[:4],
                *market_pack.intelligence_gaps[:4],
                report.commercial_summary.next_action,
                "附件至少包含证据矩阵、假设台账、测算表、接口清单、安全核验项和专家评审意见。",
            ],
            evidence=_evidence_rows(report, market_pack),
            validation_actions=["通过主张—证据账本、语义挑战者、财务复算和人工审阅后再外发。"],
        ),
    ]
    return _document(
        framework="feasibility_study_compiler_v1",
        document_kind="feasibility_study",
        title=f"{customer}{scenario}可行性研究报告",
        audience="建设单位、主管部门、投决/评审专家、财务与技术评审人员",
        purpose="支撑项目可行性论证、投资决策、评审和后续招采准备。",
        evidence_policy=evidence_policy,
        sections=sections,
        assumptions=_base_assumptions(report, scenario=scenario, target_customer=customer, vertical_scene=vertical_scene),
        validation_actions=[
            "补需求预测、方案比选、CAPEX/OPEX/TCO、收益测算、敏感性分析和影响评价数据。",
            "把预算、周期、收益和风险逐项绑定证据或待核验动作。",
        ],
        quality_gates=[
            "必须覆盖需求预测、方案比选、技术/组织/财务可行性、影响评价、风险和证据。",
            "财务数字必须可复算；数据不足时输出假设和敏感性变量，不输出伪精确结论。",
        ],
    )


def build_delivery_compiled_documents(
    report: ResearchReportDocument,
    *,
    market_pack: ResearchMarketIntelligencePackOut,
    scenario: str,
    target_customer: str,
    vertical_scene: str,
    evidence_policy: str,
) -> list[ResearchDeliveryCompiledDocumentOut]:
    return [
        build_solution_design_document(
            report,
            market_pack=market_pack,
            scenario=scenario,
            target_customer=target_customer,
            vertical_scene=vertical_scene,
            evidence_policy=evidence_policy,
        ),
        build_consulting_report_document(
            report,
            market_pack=market_pack,
            scenario=scenario,
            target_customer=target_customer,
            vertical_scene=vertical_scene,
            evidence_policy=evidence_policy,
        ),
        build_project_proposal_document(
            report,
            market_pack=market_pack,
            scenario=scenario,
            target_customer=target_customer,
            vertical_scene=vertical_scene,
            evidence_policy=evidence_policy,
        ),
        build_feasibility_study_document(
            report,
            market_pack=market_pack,
            scenario=scenario,
            target_customer=target_customer,
            vertical_scene=vertical_scene,
            evidence_policy=evidence_policy,
        ),
    ]


def select_compiled_document(
    documents: Sequence[ResearchDeliveryCompiledDocumentOut],
    document_kind: str,
) -> ResearchDeliveryCompiledDocumentOut | None:
    return next((document for document in documents if document.document_kind == document_kind), None)


def compiled_document_to_outline_sections(
    document: ResearchDeliveryCompiledDocumentOut,
    *,
    limit: int = 10,
) -> list[ResearchSolutionOutlineSectionOut]:
    return [
        ResearchSolutionOutlineSectionOut(
            title=section.title,
            bullets=_dedupe_strings(
                [
                    *section.bullets,
                    *[f"证据：{item}" for item in section.evidence[:2]],
                    *[f"待核验：{item}" for item in section.validation_actions[:2]],
                ],
                limit=limit,
            ),
        )
        for section in document.sections
    ]


def compiled_document_sections_for_formal_export(
    document: ResearchDeliveryCompiledDocumentOut,
) -> list[tuple[str, list[str]]]:
    rows: list[tuple[str, list[str]]] = []
    for section in document.sections:
        section_rows = _dedupe_strings(
            [
                *section.bullets,
                *[f"证据锚点：{item}" for item in section.evidence],
                *[f"关键假设：{item}" for item in section.assumptions],
                *[f"验证动作：{item}" for item in section.validation_actions],
            ],
            limit=14,
        )
        rows.append((section.title, section_rows))
    if document.quality_gates:
        rows.append(("附：专用编译器质量门槛", list(document.quality_gates)))
    if document.assumptions:
        rows.append(("附：全局假设台账", list(document.assumptions)))
    if document.validation_actions:
        rows.append(("附：放行前验证动作", list(document.validation_actions)))
    return rows
