from __future__ import annotations

from typing import Iterable, Sequence

from app.schemas.research import (
    ResearchEntityEvidenceOut,
    ResearchReportDocument,
    ResearchSolutionDeliveryPackOut,
)
from app.services.content_extractor import normalize_text
from app.services.delivery.market_intelligence import build_market_intelligence_pack
from app.services.delivery.solution_architecture import build_solution_architecture_delivery
from app.services.delivery.quantitative_models import build_quantitative_decision_model
from app.services.delivery.industry_skill_context import apply_industry_skill_context
from app.services.delivery.solution_evidence_guard import evaluate_solution_delivery_guard
from app.services.delivery.solution_materials import (
    build_advisory_artifacts,
    build_solution_delivery_markdown,
    build_solution_delivery_outlines,
)
from app.services.research_delivery_quality_service import review_and_improve_solution_delivery_pack
from app.services.research.architecture_traceability import build_customer_architecture_traceability
from app.services.industry_knowledge_rag import DEFAULT_INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGY, IndustryKnowledgeRetrievalStrategy
from app.services.industry_skill_library import build_industry_skill_context


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


def _delivery_evidence_links(report: ResearchReportDocument) -> list[ResearchEntityEvidenceOut]:
    rows: list[ResearchEntityEvidenceOut] = []
    seen_urls: set[str] = set()
    for section in report.sections:
        for link in section.evidence_links:
            if not link.url or link.url in seen_urls:
                continue
            seen_urls.add(link.url)
            rows.append(link)
    for source in report.sources:
        if not source.url or source.url in seen_urls:
            continue
        seen_urls.add(source.url)
        rows.append(
            ResearchEntityEvidenceOut(
                title=source.title,
                url=source.url,
                source_label=source.source_label,
                source_tier=source.source_tier,
                anchor_text=source.search_query,
                excerpt=source.snippet,
                confidence_tone="high" if source.source_tier == "official" else "low",
            )
        )
    return rows[:40]


def build_solution_delivery_pack(
    report: ResearchReportDocument,
    *,
    scenario: str = "",
    target_customer: str = "",
    vertical_scene: str = "",
    supplemental_context: str = "",
    use_industry_skills: bool = True,
    industry_skill_ids: list[str] | None = None,
    industry_knowledge_retrieval_strategy: IndustryKnowledgeRetrievalStrategy = DEFAULT_INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGY,
    industry_knowledge_retrieval_industries: Sequence[str] | None = None,
    industry_knowledge_retrieval_document_types: Sequence[str] | None = None,
) -> ResearchSolutionDeliveryPackOut:
    resolved_scenario, resolved_customer, resolved_scene, blocked_pack = evaluate_solution_delivery_guard(
        report,
        scenario=scenario,
        target_customer=target_customer,
        vertical_scene=vertical_scene,
    )
    industry_skill_context = build_industry_skill_context(
        scenario=resolved_scenario,
        target_customer=resolved_customer,
        vertical_scene=resolved_scene,
        supplemental_context=supplemental_context,
        selected_skill_ids=industry_skill_ids,
        enabled=use_industry_skills,
        retrieval_strategy=industry_knowledge_retrieval_strategy,
        retrieval_industries=industry_knowledge_retrieval_industries,
        retrieval_document_types=industry_knowledge_retrieval_document_types,
    )
    if blocked_pack is not None:
        return apply_industry_skill_context(blocked_pack, industry_skill_context)
    market_pack = build_market_intelligence_pack(
        report,
        scenario=resolved_scenario,
        target_customer=resolved_customer,
        vertical_scene=resolved_scene,
    )
    intelligence_summary = _dedupe_strings(
        [
            f"来源支撑度 {market_pack.source_support_score}/100，可直接采用来源 {market_pack.validated_source_count} 条，需复核来源 {market_pack.ambiguous_source_count} 条。",
            f"近三年公开招采候选 {len(market_pack.tender_projects)} 条，产品/能力线索 {len(market_pack.product_catalog)} 条，技术参数线索 {len(market_pack.technical_parameter_catalog)} 组。",
            report.executive_summary,
            report.commercial_summary.budget_signal,
            supplemental_context,
            *report.budget_signals[:2],
            *report.benchmark_cases[:2],
        ],
        limit=8,
    )
    clarification_questions = _dedupe_strings(
        [
            "目标客户是谁？如果暂不明确，请至少给出行业、区域和客户类型。",
            "更垂直的场景是什么？例如电商直播数字人、景区AIGC导览、政务热线AI助手、招商AI营销平台。",
            "本次材料面向谁审阅？内部立项、客户汇报、招采前交流还是正式申报？",
            "预算口径、建设周期、部署形态、数据安全边界是否已有硬约束？",
        ],
        limit=6,
    )
    evidence_policy = (
        "仅把已命中主题、客户或招采/技术参数的来源写成确定判断；其余内容保留为待核验假设。"
        if market_pack.source_support_score < 70
        else "当前来源可支撑初版方案大纲，正式对客前仍需确认预算、客户和交付边界。"
    )
    outlines = build_solution_delivery_outlines(
        report,
        market_pack=market_pack,
        scenario=resolved_scenario,
        target_customer=resolved_customer,
        vertical_scene=resolved_scene,
        evidence_policy=evidence_policy,
    )
    advisory_artifacts = build_advisory_artifacts(
        report,
        market_pack=market_pack,
        scenario=resolved_scenario,
        target_customer=resolved_customer,
        vertical_scene=resolved_scene,
        evidence_policy=evidence_policy,
    )
    quantitative_decision_model = build_quantitative_decision_model(
        report,
        market_pack=market_pack,
        scenario=resolved_scenario,
        target_customer=resolved_customer,
        vertical_scene=resolved_scene,
    )
    pack = ResearchSolutionDeliveryPackOut(
        scenario=resolved_scenario,
        target_customer=resolved_customer,
        vertical_scene=resolved_scene,
        source_support_score=market_pack.source_support_score,
        evidence_policy=evidence_policy,
        industry_skill_context=industry_skill_context,
        grounding_checks=_dedupe_strings(
            [
                f"已通过来源校正筛出 {market_pack.validated_source_count} 条高相关来源。",
                f"仍有 {market_pack.ambiguous_source_count} 条来源需要人工复核。",
                *market_pack.intelligence_gaps[:2],
            ],
            limit=6,
        ),
        clarification_questions=clarification_questions,
        intelligence_summary=intelligence_summary,
        compiled_documents=outlines.compiled_documents,
        quantitative_decision_model=quantitative_decision_model,
        feasibility_outline=outlines.feasibility_outline,
        project_proposal_outline=outlines.project_proposal_outline,
        client_ppt_outline=outlines.client_ppt_outline,
        advisory_artifacts=advisory_artifacts,
        review_checklist=_dedupe_strings(
            [
                "确认目标客户和业务牵头部门是否准确。",
                "确认近三年招采项目是否和目标场景同类、同区域或同采购路径。",
                "确认产品清单、技术参数和部署边界是否可对外表达。",
                "确认预算口径、实施周期和交付责任边界。",
                "确认哪些内容可进入客户版，哪些只保留内部版。",
            ],
            limit=8,
        ),
        next_steps=_dedupe_strings(
            [
                "用户确认目标客户/垂直场景后，补跑专项公开源检索并锁定材料版本。",
                "先审阅大纲，再细化为可研、项目建议书或对客汇报 PPT 完稿。",
                "导出前保留证据附录，避免对客材料出现无来源强结论。",
            ],
            limit=6,
        ),
    )
    pack = apply_industry_skill_context(pack, industry_skill_context)
    pack = review_and_improve_solution_delivery_pack(
        pack,
        evidence_links=_delivery_evidence_links(report),
        expected_entities=_dedupe_strings(
            [
                resolved_customer,
                *report.target_accounts[:3],
            ],
            limit=4,
        ),
    )
    pack = build_solution_architecture_delivery(report, market_pack=market_pack, pack=pack)
    pack = pack.model_copy(
        update={
            "customer_architecture_traceability": build_customer_architecture_traceability(
                report,
                pack=pack,
            )
        }
    )
    pack.export_markdown = build_solution_delivery_markdown(pack, market_pack=market_pack)
    return pack
