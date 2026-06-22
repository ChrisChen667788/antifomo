from __future__ import annotations

from collections.abc import Iterable, Sequence
import re

from app.schemas.research import (
    ResearchDecisionAlternativeOptionOut,
    ResearchDecisionCriterionScoreOut,
    ResearchFinancialScenarioOut,
    ResearchMarketIntelligencePackOut,
    ResearchQuantitativeDecisionModelOut,
    ResearchReportDocument,
    ResearchSensitivityVariableOut,
    ResearchTenderScoreResponseItemOut,
)
from app.services.content_extractor import normalize_text


_AMOUNT_PATTERN = re.compile(r"(?P<number>\d+(?:\.\d+)?)\s*(?P<unit>亿元|万元|元)")


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


def _amount_to_cny(number: float, unit: str) -> float:
    if unit == "亿元":
        return number * 100_000_000
    if unit == "万元":
        return number * 10_000
    return number


def _extract_amounts(values: Iterable[object]) -> list[float]:
    amounts: list[float] = []
    for value in values:
        text = normalize_text(str(value or ""))
        for match in _AMOUNT_PATTERN.finditer(text):
            amounts.append(_amount_to_cny(float(match.group("number")), match.group("unit")))
    return [amount for amount in amounts if amount > 0]


def _round_money(value: float | None) -> float | None:
    if value is None:
        return None
    return float(round(value, 2))


def _percent(value: float | None) -> float | None:
    if value is None:
        return None
    return float(round(value, 2))


def _median(values: Sequence[float]) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    mid = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[mid]
    return (ordered[mid - 1] + ordered[mid]) / 2


def _npv_from_cashflows(cashflows: Sequence[float], rate: float) -> float:
    return sum(value / ((1 + rate) ** index) for index, value in enumerate(cashflows))


def _irr_percent(cashflows: Sequence[float]) -> float | None:
    if not cashflows or not any(value < 0 for value in cashflows) or not any(value > 0 for value in cashflows):
        return None
    low = -0.95
    high = 10.0
    low_value = _npv_from_cashflows(cashflows, low)
    high_value = _npv_from_cashflows(cashflows, high)
    if low_value * high_value > 0:
        return None
    for _ in range(80):
        mid = (low + high) / 2
        mid_value = _npv_from_cashflows(cashflows, mid)
        if abs(mid_value) < 1e-7:
            return _percent(mid * 100)
        if low_value * mid_value <= 0:
            high = mid
            high_value = mid_value
        else:
            low = mid
            low_value = mid_value
    return _percent(((low + high) / 2) * 100)


def _evidence_refs(
    report: ResearchReportDocument,
    market_pack: ResearchMarketIntelligencePackOut,
) -> list[str]:
    return _dedupe_strings(
        [
            market_pack.source_scope_summary,
            *[source.title for source in report.sources[:6]],
            *[
                f"{project.project_name} / {project.amount or '金额待核验'}"
                for project in market_pack.tender_projects[:5]
            ],
        ],
        limit=10,
    )


def _amount_basis(
    report: ResearchReportDocument,
    market_pack: ResearchMarketIntelligencePackOut,
) -> tuple[float | None, list[str]]:
    rows = [
        *report.budget_signals,
        *[project.amount for project in market_pack.tender_projects],
        *[source.snippet for source in report.sources[:8]],
    ]
    amounts = _extract_amounts(rows)
    basis = _dedupe_strings(
        [
            *[signal for signal in report.budget_signals if _extract_amounts([signal])],
            *[
                f"{project.project_name}: {project.amount}"
                for project in market_pack.tender_projects
                if _extract_amounts([project.amount])
            ],
        ],
        limit=8,
    )
    return _median(amounts), basis


def _criterion(
    key: str,
    label: str,
    weight: int,
    score: int,
    rationale: str,
) -> ResearchDecisionCriterionScoreOut:
    return ResearchDecisionCriterionScoreOut(
        criterion_key=key,
        label=label,
        weight_percent=weight,
        score=max(0, min(int(score), 100)),
        rationale=rationale,
    )


def _alternative(
    *,
    option_id: str,
    name: str,
    summary: str,
    criterion_scores: Sequence[ResearchDecisionCriterionScoreOut],
    assumptions: Iterable[object],
    validation_actions: Iterable[object],
) -> ResearchDecisionAlternativeOptionOut:
    weighted_score = round(
        sum(item.score * item.weight_percent for item in criterion_scores)
        / max(sum(item.weight_percent for item in criterion_scores), 1)
    )
    return ResearchDecisionAlternativeOptionOut(
        option_id=option_id,
        name=name,
        summary=summary,
        weighted_score=weighted_score,
        criterion_scores=list(criterion_scores),
        decision_rationale="；".join(
            _dedupe_strings(
                [
                    f"{item.label} {item.score}/100"
                    for item in criterion_scores
                    if item.weight_percent >= 12
                ],
                limit=4,
            )
        ),
        assumptions=_dedupe_strings(assumptions, limit=6),
        validation_actions=_dedupe_strings(validation_actions, limit=6),
    )


def _rank_options(options: Sequence[ResearchDecisionAlternativeOptionOut]) -> list[ResearchDecisionAlternativeOptionOut]:
    ranked = sorted(options, key=lambda item: (-item.weighted_score, item.option_id))
    return [option.model_copy(update={"rank": index + 1}) for index, option in enumerate(ranked)]


def _build_alternatives(
    report: ResearchReportDocument,
    market_pack: ResearchMarketIntelligencePackOut,
    *,
    amount_cny: float | None,
) -> list[ResearchDecisionAlternativeOptionOut]:
    source_score = int(market_pack.source_support_score or 0)
    tender_count = len(market_pack.tender_projects)
    product_count = len(market_pack.product_catalog)
    has_budget = bool(amount_cny)
    urgency = min(100, 48 + min(22, tender_count * 8) + min(18, len(report.budget_signals) * 6) + min(12, len(report.tender_timeline) * 4))
    evidence = min(100, source_score + min(12, tender_count * 3) + min(8, product_count * 2))
    investment_pressure = 72 if not has_budget else max(30, min(90, round((amount_cny or 0) / 100_000)))

    options = [
        _alternative(
            option_id="status_quo",
            name="维持现状 / 观察跟进",
            summary="保持关系和公开源监测，不立即启动建设或试点。",
            criterion_scores=[
                _criterion("strategic_fit", "战略匹配", 14, max(35, urgency - 22), "只能解决情报跟踪，不能形成可验证能力。"),
                _criterion("evidence_support", "证据支撑", 14, evidence, "公开证据越弱，维持观察越安全。"),
                _criterion("implementation_complexity", "实施复杂度", 14, 92, "无需系统建设，组织复杂度最低。"),
                _criterion("investment_pressure", "投资压力", 12, 95, "短期资金压力最低。"),
                _criterion("delivery_risk", "交付风险", 16, 88, "不进入交付实施，风险可控但机会损失较高。"),
                _criterion("value_potential", "价值潜力", 18, 38, "无法验证业务效果和方案竞争力。"),
                _criterion("scalability", "可扩展性", 12, 35, "没有试点沉淀，后续复制基础弱。"),
            ],
            assumptions=["客户预算、接口、组织责任尚未锁定时可采用。"],
            validation_actions=["继续监测招采公告、预算窗口、客户组织变化和竞品动作。"],
        ),
        _alternative(
            option_id="phased_pilot",
            name="分期试点 / 小范围验证",
            summary="先锁定高价值场景和关键接口，用试点验证 ROI、集成边界和用户体验。",
            criterion_scores=[
                _criterion("strategic_fit", "战略匹配", 14, min(96, urgency + 6), "能把机会转化为可验证客户场景。"),
                _criterion("evidence_support", "证据支撑", 14, evidence, "可以用公开招采和产品参数约束试点边界。"),
                _criterion("implementation_complexity", "实施复杂度", 14, 76, "复杂度中等，可通过边界控制。"),
                _criterion("investment_pressure", "投资压力", 12, 78 if has_budget else 66, "资金压力可控，但仍需客户确认预算口径。"),
                _criterion("delivery_risk", "交付风险", 16, 74, "接口、数据和安全风险可在试点中前置暴露。"),
                _criterion("value_potential", "价值潜力", 18, min(94, 58 + tender_count * 7 + product_count * 3), "可用试点沉淀绩效数据和交付方法。"),
                _criterion("scalability", "可扩展性", 12, 82, "试点成功后可复制到更多场景。"),
            ],
            assumptions=["先限定用户范围、数据范围、接口数量和验收指标。"],
            validation_actions=["补试点范围、成功指标、接口清单、数据样本、预算上限和验收口径。"],
        ),
        _alternative(
            option_id="full_build",
            name="整体建设 / 一次性推进",
            summary="在预算、数据、安全、采购和组织责任明确后整体建设。",
            criterion_scores=[
                _criterion("strategic_fit", "战略匹配", 14, min(100, urgency + 10), "若客户已进入建设窗口，整体建设战略匹配较高。"),
                _criterion("evidence_support", "证据支撑", 14, max(35, evidence - 8), "整体建设需要更高证据密度和客户确认。"),
                _criterion("implementation_complexity", "实施复杂度", 14, 48, "涉及多系统、多角色和长期运维，复杂度高。"),
                _criterion("investment_pressure", "投资压力", 12, max(25, 72 - investment_pressure // 2), "一次性投入压力高。"),
                _criterion("delivery_risk", "交付风险", 16, 46, "预算、接口、安全和组织协同风险集中。"),
                _criterion("value_potential", "价值潜力", 18, min(98, 68 + tender_count * 6 + product_count * 3), "规模化价值潜力最高。"),
                _criterion("scalability", "可扩展性", 12, 88, "统一架构有利于规模复制。"),
            ],
            assumptions=["仅在客户确认预算、采购方式、系统边界和安全合规后推荐。"],
            validation_actions=["补正式立项、预算批复、采购路径、接口清单、安全评审和实施组织。"],
        ),
    ]
    return _rank_options(options)


def _tender_item(
    *,
    score_item: str,
    weight_percent: int,
    response_strategy: str,
    mapped_sections: Iterable[object],
    evidence_refs: Iterable[object],
    owner: str,
    risk_level: str,
    validation_action: str,
) -> ResearchTenderScoreResponseItemOut:
    return ResearchTenderScoreResponseItemOut(
        score_item=score_item,
        weight_percent=weight_percent,
        response_strategy=response_strategy,
        mapped_sections=_dedupe_strings(mapped_sections, limit=5),
        evidence_refs=_dedupe_strings(evidence_refs, limit=5),
        owner=owner,
        risk_level=risk_level,  # type: ignore[arg-type]
        validation_action=validation_action,
    )


def _build_tender_score_matrix(
    report: ResearchReportDocument,
    market_pack: ResearchMarketIntelligencePackOut,
) -> list[ResearchTenderScoreResponseItemOut]:
    evidence = _evidence_refs(report, market_pack)
    product_refs = _dedupe_strings(
        [
            *[item.name for item in market_pack.product_catalog[:4]],
            *report.flagship_products[:4],
        ],
        limit=6,
    )
    parameter_refs = _dedupe_strings(
        [
            parameter
            for item in market_pack.technical_parameter_catalog[:4]
            for parameter in item.technical_parameters[:2]
        ],
        limit=8,
    )
    return [
        _tender_item(
            score_item="技术方案与总体架构",
            weight_percent=25,
            response_strategy="用业务场景、能力架构、数据/模型/接口和 NFR 形成一体化技术响应。",
            mapped_sections=["解决方案设计/三、能力架构与产品/模块映射", "解决方案设计/四、数据、模型、接口与集成架构"],
            evidence_refs=[*product_refs, *parameter_refs],
            owner="解决方案架构师",
            risk_level="medium",
            validation_action="补架构图、接口清单、部署拓扑、NFR 指标和演示脚本。",
        ),
        _tender_item(
            score_item="实施组织、项目团队与交付计划",
            weight_percent=18,
            response_strategy="按调研、原型、试点、验收、推广拆分里程碑、角色和交付物。",
            mapped_sections=["项目建议书/六、采购实施、里程碑、组织机制与运营方案", "可研/五、组织实施、采购交付、运营维护与安全合规可行性"],
            evidence_refs=[*report.tender_timeline[:4], *report.target_departments[:4]],
            owner="交付 PM",
            risk_level="medium",
            validation_action="补项目组织图、WBS、里程碑、验收标准和风险响应计划。",
        ),
        _tender_item(
            score_item="安全合规、数据治理与信创适配",
            weight_percent=16,
            response_strategy="把等保、密码、数据安全、权限、审计、信创和运维安全作为强约束响应。",
            mapped_sections=["解决方案设计/五、NFR、安全合规、信创与运维要求", "项目建议书/五、技术方案、系统边界与安全合规"],
            evidence_refs=[*parameter_refs, *evidence],
            owner="安全合规负责人",
            risk_level="high",
            validation_action="补安全方案、数据分类分级、权限矩阵、等保/信创适配说明和客户安全要求。",
        ),
        _tender_item(
            score_item="同类项目经验、产品成熟度与技术参数",
            weight_percent=16,
            response_strategy="以近三年公开招采、产品参数和可复用能力支撑成熟度。",
            mapped_sections=["咨询报告/三、洞察发现、证据与反方观点", "解决方案设计/三、能力架构与产品/模块映射"],
            evidence_refs=[*_evidence_refs(report, market_pack), *product_refs],
            owner="售前负责人",
            risk_level="medium",
            validation_action="补同类案例、截图、验收材料、软著/资质和产品参数表。",
        ),
        _tender_item(
            score_item="报价合理性、投资测算与服务承诺",
            weight_percent=15,
            response_strategy="用 CAPEX/OPEX/TCO、三情景和敏感性变量解释报价边界，不做无来源低价承诺。",
            mapped_sections=["可研/六、投资估算、CAPEX/OPEX/TCO、收益测算与敏感性分析", "项目建议书/七、投资测算、资金口径、绩效目标与综合效益"],
            evidence_refs=[*report.budget_signals[:4], *[project.amount for project in market_pack.tender_projects[:4]]],
            owner="商务/财务负责人",
            risk_level="high",
            validation_action="补报价拆分、税费、运维年限、折现率、付款条款和边界条件。",
        ),
        _tender_item(
            score_item="售后运维、培训与持续优化",
            weight_percent=10,
            response_strategy="明确 SLA、问题闭环、知识/模型更新、安全运营和培训推广机制。",
            mapped_sections=["解决方案设计/六、实施路线、验收方案与运维交接", "项目建议书/八、风险控制、验收安排、证据矩阵与待确认事项"],
            evidence_refs=[*report.technical_appendix.limitations[:4], *market_pack.intelligence_gaps[:4]],
            owner="运营/客户成功负责人",
            risk_level="medium",
            validation_action="补 SLA、培训计划、运维资源、升级机制和验收后持续优化预算。",
        ),
    ]


def _scenario(
    *,
    scenario_key: str,
    label: str,
    capex: float | None,
    opex_factor: float,
    benefit_factor: float,
    discount_rate: float,
    assumptions: Iterable[object],
    confidence: str,
) -> ResearchFinancialScenarioOut:
    if capex is None:
        return ResearchFinancialScenarioOut(
            scenario_key=scenario_key,  # type: ignore[arg-type]
            label=label,
            confidence="low",
            assumptions=_dedupe_strings(
                [
                    *assumptions,
                    "缺少可复算 CAPEX 基准，暂不输出财务数字。",
                ],
                limit=6,
            ),
        )
    annual_opex = capex * opex_factor
    annual_benefit = capex * benefit_factor
    tco_3y = capex + annual_opex * 3
    gross_benefit_3y = annual_benefit * 3
    net_benefit_3y = gross_benefit_3y - tco_3y
    payback = None
    if annual_benefit > annual_opex:
        payback = capex / (annual_benefit - annual_opex) * 12
    annual_net = annual_benefit - annual_opex
    cashflows = [-capex, annual_net, annual_net, annual_net]
    npv = _npv_from_cashflows(cashflows, discount_rate)
    roi = net_benefit_3y / tco_3y * 100 if tco_3y else None
    return ResearchFinancialScenarioOut(
        scenario_key=scenario_key,  # type: ignore[arg-type]
        label=label,
        capex_cny=_round_money(capex),
        annual_opex_cny=_round_money(annual_opex),
        annual_benefit_cny=_round_money(annual_benefit),
        tco_3y_cny=_round_money(tco_3y),
        net_benefit_3y_cny=_round_money(net_benefit_3y),
        payback_months=_percent(payback),
        npv_3y_cny=_round_money(npv),
        irr_percent=_irr_percent(cashflows),
        roi_percent=_percent(roi),
        confidence=confidence,  # type: ignore[arg-type]
        assumptions=_dedupe_strings(assumptions, limit=6),
    )


def _build_financial_scenarios(
    amount_cny: float | None,
    *,
    amount_basis: Sequence[str],
) -> list[ResearchFinancialScenarioOut]:
    basis = "；".join(amount_basis[:3]) if amount_basis else "缺少公开预算或同类招采金额。"
    if amount_cny is None:
        return [
            _scenario(
                scenario_key="pessimistic",
                label="保守情景",
                capex=None,
                opex_factor=0.18,
                benefit_factor=0.18,
                discount_rate=0.08,
                confidence="low",
                assumptions=[basis, "需补单价、数量、周期、税费、折现率和收益归因数据。"],
            ),
            _scenario(
                scenario_key="base",
                label="基准情景",
                capex=None,
                opex_factor=0.15,
                benefit_factor=0.28,
                discount_rate=0.08,
                confidence="low",
                assumptions=[basis, "需先确认 CAPEX 基准后再复算 TCO、NPV、ROI 和回收期。"],
            ),
            _scenario(
                scenario_key="optimistic",
                label="乐观情景",
                capex=None,
                opex_factor=0.12,
                benefit_factor=0.42,
                discount_rate=0.08,
                confidence="low",
                assumptions=[basis, "乐观情景必须有客户业务量、自动化收益和推广范围支撑。"],
            ),
        ]
    return [
        _scenario(
            scenario_key="pessimistic",
            label="保守情景",
            capex=amount_cny * 1.12,
            opex_factor=0.20,
            benefit_factor=0.18,
            discount_rate=0.08,
            confidence="medium",
            assumptions=[basis, "CAPEX 上浮 12%，年度收益按 CAPEX 的 18% 暂估。"],
        ),
        _scenario(
            scenario_key="base",
            label="基准情景",
            capex=amount_cny,
            opex_factor=0.15,
            benefit_factor=0.32,
            discount_rate=0.08,
            confidence="medium",
            assumptions=[basis, "年度 OPEX 暂按 CAPEX 的 15%，年度收益按 32% 暂估。"],
        ),
        _scenario(
            scenario_key="optimistic",
            label="乐观情景",
            capex=amount_cny * 0.92,
            opex_factor=0.12,
            benefit_factor=0.48,
            discount_rate=0.08,
            confidence="medium",
            assumptions=[basis, "CAPEX 下浮 8%，推广充分且年度收益按 CAPEX 的 48% 暂估。"],
        ),
    ]


def _build_sensitivity_variables(amount_cny: float | None) -> list[ResearchSensitivityVariableOut]:
    capex_base = amount_cny if amount_cny is not None else None
    return [
        ResearchSensitivityVariableOut(
            variable_key="capex",
            label="CAPEX 基准",
            base_value=_round_money(capex_base),
            low_value=_round_money(capex_base * 0.85) if capex_base else None,
            high_value=_round_money(capex_base * 1.15) if capex_base else None,
            unit="CNY",
            impact_summary="直接影响 TCO、NPV、ROI 和回收期，是可研财务模型第一敏感变量。",
            validation_action="补软件、硬件/算力、集成、安全、培训、运维准备等报价拆分。",
        ),
        ResearchSensitivityVariableOut(
            variable_key="annual_opex_ratio",
            label="年度 OPEX / CAPEX",
            base_value=0.15,
            low_value=0.10,
            high_value=0.22,
            unit="ratio",
            impact_summary="影响三年 TCO 和净收益，云/模型调用、安全运营和内容更新越重越敏感。",
            validation_action="补云资源、模型调用、运维人力、知识更新和安全运营年化费用。",
        ),
        ResearchSensitivityVariableOut(
            variable_key="annual_benefit_ratio",
            label="年度收益 / CAPEX",
            base_value=0.32,
            low_value=0.18,
            high_value=0.48,
            unit="ratio",
            impact_summary="决定回收期和 ROI，必须用业务量、效率提升或收入转化数据验证。",
            validation_action="补业务基线、用户量、处理量、人工成本、转化率或服务质量收益口径。",
        ),
        ResearchSensitivityVariableOut(
            variable_key="discount_rate",
            label="折现率",
            base_value=0.08,
            low_value=0.06,
            high_value=0.10,
            unit="ratio",
            impact_summary="影响 NPV，对三年以上收益和资金成本敏感。",
            validation_action="由财务负责人确认折现率、税费、付款节奏和残值处理口径。",
        ),
    ]


def _markdown(model: ResearchQuantitativeDecisionModelOut) -> str:
    lines = [
        "## 量化决策模型",
        f"- 框架: {model.framework}",
        f"- 状态: {model.status}",
        f"- 推荐方案: {model.recommended_option_id or '待确认'}",
        f"- 摘要: {model.summary or '待补'}",
        "",
        "### 备选方案加权比选",
    ]
    for option in model.alternative_options:
        lines.extend(
            [
                f"- {option.rank}. {option.name}（{option.option_id}）: {option.weighted_score}/100",
                f"  - {option.summary}",
                f"  - 判断: {option.decision_rationale or '待补'}",
            ]
        )
        for criterion in option.criterion_scores:
            lines.append(
                f"  - {criterion.label}（{criterion.weight_percent}%）: {criterion.score}/100；{criterion.rationale}"
            )
    lines.extend(["", "### 投标评分项—章节—证据—责任人响应矩阵"])
    for item in model.tender_score_response_matrix:
        lines.extend(
            [
                f"- {item.score_item}（{item.weight_percent}% / {item.risk_level}）",
                f"  - 响应策略: {item.response_strategy}",
                f"  - 章节: {'；'.join(item.mapped_sections) if item.mapped_sections else '待补'}",
                f"  - 证据: {'；'.join(item.evidence_refs[:3]) if item.evidence_refs else '待补'}",
                f"  - 负责人: {item.owner or '待确认'}；验证: {item.validation_action or '待补'}",
            ]
        )
    lines.extend(["", "### 可研财务三情景"])
    for scenario in model.financial_scenarios:
        lines.extend(
            [
                f"- {scenario.label}（{scenario.scenario_key} / {scenario.confidence}）",
                f"  - CAPEX: {scenario.capex_cny if scenario.capex_cny is not None else '待补'}",
                f"  - 年度 OPEX: {scenario.annual_opex_cny if scenario.annual_opex_cny is not None else '待补'}",
                f"  - 年度收益: {scenario.annual_benefit_cny if scenario.annual_benefit_cny is not None else '待补'}",
                f"  - 三年 TCO: {scenario.tco_3y_cny if scenario.tco_3y_cny is not None else '待补'}",
                f"  - 三年净收益: {scenario.net_benefit_3y_cny if scenario.net_benefit_3y_cny is not None else '待补'}",
                f"  - 回收期（月）: {scenario.payback_months if scenario.payback_months is not None else '待补'}",
                f"  - NPV: {scenario.npv_3y_cny if scenario.npv_3y_cny is not None else '待补'}；"
                f"IRR: {scenario.irr_percent if scenario.irr_percent is not None else '待补'}%；"
                f"ROI: {scenario.roi_percent if scenario.roi_percent is not None else '待补'}%",
            ]
        )
    lines.extend(["", "### 敏感性变量"])
    for variable in model.sensitivity_variables:
        lines.append(
            f"- {variable.label}: base={variable.base_value if variable.base_value is not None else '待补'} "
            f"low={variable.low_value if variable.low_value is not None else '待补'} "
            f"high={variable.high_value if variable.high_value is not None else '待补'} {variable.unit}；"
            f"{variable.impact_summary}"
        )
    if model.assumptions:
        lines.extend(["", "### 量化假设", *[f"- {item}" for item in model.assumptions]])
    if model.validation_actions:
        lines.extend(["", "### 量化验证动作", *[f"- {item}" for item in model.validation_actions]])
    return "\n".join(lines).strip()


def build_quantitative_decision_model(
    report: ResearchReportDocument,
    *,
    market_pack: ResearchMarketIntelligencePackOut,
    scenario: str,
    target_customer: str,
    vertical_scene: str,
) -> ResearchQuantitativeDecisionModelOut:
    amount_cny, amount_basis = _amount_basis(report, market_pack)
    alternatives = _build_alternatives(report, market_pack, amount_cny=amount_cny)
    recommended = alternatives[0] if alternatives else None
    tender_matrix = _build_tender_score_matrix(report, market_pack)
    financial_scenarios = _build_financial_scenarios(amount_cny, amount_basis=amount_basis)
    sensitivity = _build_sensitivity_variables(amount_cny)
    missing_finance = amount_cny is None
    status = "ready" if not missing_finance and int(market_pack.source_support_score or 0) >= 70 else "assumption_required"
    assumptions = _dedupe_strings(
        [
            f"目标客户暂按“{target_customer or '待确认'}”，场景暂按“{scenario} / {vertical_scene}”。",
            "财务结果为内部测算模型，正式可研需由财务和业务负责人确认输入。",
            "没有客户业务量、单价、税费、付款节奏和折现率时，不输出强 ROI 承诺。",
            "CAPEX 基准来自公开预算/同类招采金额的中位数。"
            if amount_cny is not None
            else "缺少公开预算/同类招采金额，财务三情景保留为待补数据。",
        ],
        limit=8,
    )
    validation_actions = _dedupe_strings(
        [
            "确认 CAPEX 拆分：软件、硬件/算力、集成、安全、数据治理、培训推广。",
            "确认 OPEX 拆分：云/算力、模型调用、运维、内容/知识更新、安全运营。",
            "确认收益口径：人工节省、效率提升、收入转化、体验改善或风险降低。",
            "确认折现率、税费、付款节奏、建设周期和收益起算时间。",
            "把投标评分项逐项映射到章节、证据、负责人和验证动作。",
        ],
        limit=8,
    )
    summary = (
        f"推荐“{recommended.name}”，加权得分 {recommended.weighted_score}/100；"
        f"财务模型状态为 {status}。"
        if recommended is not None
        else f"财务模型状态为 {status}，仍需补充备选方案输入。"
    )
    model = ResearchQuantitativeDecisionModelOut(
        status=status,  # type: ignore[arg-type]
        recommended_option_id=recommended.option_id if recommended is not None else "",
        summary=summary,
        alternative_options=alternatives,
        tender_score_response_matrix=tender_matrix,
        financial_scenarios=financial_scenarios,
        sensitivity_variables=sensitivity,
        assumptions=assumptions,
        validation_actions=validation_actions,
    )
    return model.model_copy(update={"export_markdown": _markdown(model)})


def quantitative_decision_model_sections_for_formal_export(
    model: ResearchQuantitativeDecisionModelOut,
) -> list[tuple[str, list[str]]]:
    alternatives = [
        f"{option.rank}. {option.name}：{option.weighted_score}/100；{option.decision_rationale}"
        for option in model.alternative_options
    ]
    tender_rows = [
        f"{item.score_item}（{item.weight_percent}%）：{item.response_strategy}；章节：{'；'.join(item.mapped_sections[:2])}；负责人：{item.owner}"
        for item in model.tender_score_response_matrix
    ]
    finance_rows = [
        (
            f"{scenario.label}：CAPEX={scenario.capex_cny if scenario.capex_cny is not None else '待补'}；"
            f"OPEX={scenario.annual_opex_cny if scenario.annual_opex_cny is not None else '待补'}；"
            f"TCO3Y={scenario.tco_3y_cny if scenario.tco_3y_cny is not None else '待补'}；"
            f"NPV={scenario.npv_3y_cny if scenario.npv_3y_cny is not None else '待补'}；"
            f"IRR={scenario.irr_percent if scenario.irr_percent is not None else '待补'}%；"
            f"ROI={scenario.roi_percent if scenario.roi_percent is not None else '待补'}%"
        )
        for scenario in model.financial_scenarios
    ]
    sensitivity_rows = [
        f"{variable.label}：base={variable.base_value if variable.base_value is not None else '待补'}；{variable.impact_summary}"
        for variable in model.sensitivity_variables
    ]
    return [
        ("附：量化决策模型摘要", _dedupe_strings([model.summary, f"状态：{model.status}", f"推荐方案：{model.recommended_option_id}"], limit=6)),
        ("附：备选方案加权比选矩阵", alternatives),
        ("附：投标评分项响应矩阵", tender_rows),
        ("附：可研财务三情景与敏感性分析", [*finance_rows, *sensitivity_rows]),
        ("附：量化假设与验证动作", [*model.assumptions, *model.validation_actions]),
    ]
