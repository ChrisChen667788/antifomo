from __future__ import annotations

from app.schemas.research import (
    ResearchArchitectureTraceabilityItemOut,
    ResearchCustomerArchitectureTraceabilityOut,
    ResearchReportResponse,
    ResearchSolutionDeliveryPackOut,
)
from app.services.content_extractor import normalize_text


def _item(
    item_id: str,
    *,
    component: str,
    classification: str,
    statement: str,
    evidence_links: list,
    customer_material_allowed: bool,
    validation_action: str,
) -> ResearchArchitectureTraceabilityItemOut:
    return ResearchArchitectureTraceabilityItemOut(
        item_id=item_id,
        component=component,
        classification=classification,  # type: ignore[arg-type]
        statement=statement,
        evidence_links=evidence_links,
        customer_material_allowed=customer_material_allowed,
        validation_action=validation_action,
    )


def build_customer_architecture_traceability(
    report: ResearchReportResponse,
    *,
    pack: ResearchSolutionDeliveryPackOut,
) -> ResearchCustomerArchitectureTraceabilityOut:
    pursuit = report.account_pursuit_pack
    if pursuit.status != "ready" or not pursuit.cards:
        return ResearchCustomerArchitectureTraceabilityOut(
            status="blocked",
            blockers=["没有可验证账户，不能把行业通用架构伪装成客户方案。"],
            current_estate_questions=["先确认客户、业务牵头部门、既有系统、数据边界和采购阶段。"],
            option_tradeoff_questions=["在获得客户事实前，仅保留行业级方案假设。"],
        )

    card = pursuit.cards[0]
    facts = [
        _item(
            "fact_account_role",
            component="客户与项目边界",
            classification="fact",
            statement=f"{card.account_name} 已在公开来源中出现{card.account_role}或项目责任相关角色。",
            evidence_links=card.evidence_links,
            customer_material_allowed=True,
            validation_action="在客户会前复核采购公告原文、主体名称和项目归口。",
        ),
        _item(
            "fact_current_signal",
            component="项目窗口",
            classification="fact",
            statement=card.current_signal,
            evidence_links=card.evidence_links,
            customer_material_allowed=True,
            validation_action="确认该信号的发布时间、有效性与当前采购阶段。",
        ),
    ]
    benchmarks = [
        _item(
            "benchmark_external_cases",
            component="行业对标",
            classification="benchmark",
            statement="外部同类案例仅用于验证能力形态、交付节奏和风险假设，不作为客户预算、系统现状或采购概率证据。",
            evidence_links=[],
            customer_material_allowed=False,
            validation_action="在客户材料中单独标注为外部标杆并说明地域与时间差异。",
        )
    ]
    assumptions = [
        _item(
            "assumption_current_estate",
            component="现有系统与数据",
            classification="assumption",
            statement="客户既有业务系统、数据目录、接口能力、身份认证和部署边界尚未由一手材料确认。",
            evidence_links=[],
            customer_material_allowed=False,
            validation_action="索取系统清单、接口文档、数据样例、权限模型和测试环境窗口。",
        ),
        _item(
            "assumption_economics",
            component="预算与投入产出",
            classification="assumption",
            statement=card.budget_signal,
            evidence_links=card.evidence_links if "未取得" not in card.budget_signal else [],
            customer_material_allowed=False,
            validation_action="核验预算批复、采购限价、实施周期与运维责任，再计算 TCO/ROI。",
        ),
    ]
    recommendations: list[ResearchArchitectureTraceabilityItemOut] = []
    for index, section in enumerate(pack.architecture_readiness.blueprint_sections[:6], start=1):
        statement = normalize_text(section.purpose or "；".join(section.components[:2]))
        if not statement:
            continue
        recommendations.append(
            _item(
                f"recommendation_{index}",
                component=section.title,
                classification="recommendation",
                statement=statement,
                evidence_links=[],
                customer_material_allowed=False,
                validation_action="将该能力写入备选方案 A/B/C，并由客户确认一期范围、验收指标和依赖条件。",
            )
        )
    estate_terms = " ".join([*report.strategic_directions, *report.project_distribution, *report.budget_signals])
    has_estate_fact = any(token in estate_terms for token in ("接口", "系统", "数据", "平台", "部署"))
    status = "ready_for_workshop" if has_estate_fact else "assumption_required"
    blockers = [] if has_estate_fact else ["现有系统、数据、接口和部署边界仍为假设，不能冻结客户架构。"]
    return ResearchCustomerArchitectureTraceabilityOut(
        status=status,  # type: ignore[arg-type]
        target_account=card.account_name,
        facts=facts,
        assumptions=assumptions,
        benchmarks=benchmarks,
        recommendations=recommendations,
        current_estate_questions=[
            "当前业务流程、系统 owner、接口能力和数据质量分别是什么？",
            "一期需要接入哪些系统，哪些能力可延后到二期？",
            "部署形态、数据出域、审计留痕和安全评审有哪些硬约束？",
        ],
        option_tradeoff_questions=[
            "单点试点、平台化一期和一次性建设三种路径的范围、成本与风险如何取舍？",
            "哪些 ADR 依赖客户事实，哪些可由行业基线先行？",
        ],
        blockers=blockers,
    )
