from __future__ import annotations

from typing import Iterable

from app.schemas.research import (
    ResearchDeliveryCompiledDocumentOut,
    ResearchDeliveryCompiledSectionOut,
    ResearchIndustrySkillContextOut,
    ResearchSolutionDeliveryPackOut,
    ResearchSolutionOutlineSectionOut,
)
from app.services.content_extractor import normalize_text


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


def _industry_skill_outline_section(
    context: ResearchIndustrySkillContextOut,
    *,
    title: str,
) -> ResearchSolutionOutlineSectionOut:
    skill_names = "、".join(skill.name for skill in context.selected_skills[:3])
    return ResearchSolutionOutlineSectionOut(
        title=title,
        bullets=_dedupe_strings(
            [
                f"已调用本地行业资料技能：{skill_names}，覆盖 {context.source_document_count} 份分类资料。",
                f"本次检索策略：{context.retrieval_strategy_label or context.retrieval_strategy}。",
                *context.guidance_summary[:3],
                (
                    f"已定位 {len(context.retrieval_hits)} 条与当前场景匹配的全文分段，"
                    "其页码和原文摘要保留在方案智囊的本地资料检索面板。"
                ),
                "本地资料仅用于行业框架和规范性校验，不计入公开来源支撑度、客户事实或正式项目证据。",
            ],
            limit=8,
        ),
    )


def _append_industry_skill_section_to_documents(
    documents: list[ResearchDeliveryCompiledDocumentOut],
    context: ResearchIndustrySkillContextOut,
) -> list[ResearchDeliveryCompiledDocumentOut]:
    if context.status != "available":
        return documents
    rag_evidence = [
        f"本地全文 RAG 命中：{hit.title} {hit.locator}"
        for hit in context.retrieval_hits[:4]
    ]
    section = ResearchDeliveryCompiledSectionOut(
        title="行业资料技能与规范性要求",
        purpose="将本地行业资料沉淀的结构、约束和自检项纳入本次交付；不把资料目录中的观点直接写成项目事实。",
        bullets=_dedupe_strings(
            [
                *context.guidance_summary[:3],
                "本地全文命中仅作为带页码的待核验参考，不直接转写为项目事实或对客承诺。",
            ],
            limit=5,
        ),
        evidence=[
            *rag_evidence,
        ],
        assumptions=["本地行业资料未替代项目公开证据、客户确认或正式政策依据。"],
        validation_actions=_dedupe_strings(
            [
                "逐项回查代表资料和原始出处，确认其适用行业、年份与项目边界。",
                *[item for skill in context.selected_skills for item in skill.quality_checklist[:2]],
            ],
            limit=5,
        ),
    )
    return [
        document.model_copy(
            update={
                "sections": [*document.sections, section],
                "quality_gates": _dedupe_strings(
                    [
                        *document.quality_gates,
                        "本地行业资料仅作框架参考，项目事实和正式依据需单独核验。",
                    ],
                    limit=8,
                ),
            }
        )
        for document in documents
    ]


def apply_industry_skill_context(
    pack: ResearchSolutionDeliveryPackOut,
    context: ResearchIndustrySkillContextOut,
) -> ResearchSolutionDeliveryPackOut:
    if context.status != "available":
        return pack.model_copy(update={"industry_skill_context": context})
    skill_names = "、".join(skill.name for skill in context.selected_skills[:3])
    rag_status = context.knowledge_base
    feasibility_section = _industry_skill_outline_section(context, title="行业资料技能与规范性要求")
    proposal_section = _industry_skill_outline_section(context, title="行业资料技能与交付约束")
    ppt_section = _industry_skill_outline_section(context, title="行业资料参考与适用边界")
    industry_review_items = [
        item for skill in context.selected_skills for item in skill.quality_checklist
    ]
    return pack.model_copy(
        update={
            "industry_skill_context": context,
            "evidence_policy": normalize_text(
                f"{pack.evidence_policy} 本地行业资料仅用于结构和规范性校验，不计入公开来源支撑度或项目事实。"
            ),
            "grounding_checks": _dedupe_strings(
                [
                    *pack.grounding_checks,
                    f"已加载本地行业资料技能：{skill_names}。",
                    f"本次本地资料检索策略：{context.retrieval_strategy_label or context.retrieval_strategy}。",
                    (
                        f"本地全文 RAG 已检索 {len(context.retrieval_hits)} 条相关分段，"
                        f"关键词索引={rag_status.keyword_index_status}，向量索引={rag_status.vector_index_status}。"
                        if rag_status.status in {"ready", "partial"}
                        else "本地全文 RAG 当前不可用，未把目录或文件名当作内容证据。"
                    ),
                    "本地资料未计入项目证据数量；对外结论仍须回到原始出处、公开来源或客户确认。",
                ],
                limit=8,
            ),
            "intelligence_summary": _dedupe_strings(
                [
                    *pack.intelligence_summary,
                    f"已调用 {skill_names}，覆盖 {context.source_document_count} 份本地分类资料，用于补强行业表达与交付规范。",
                    "本地全文命中按场景范围过滤后保留在方案智囊检索面板，需回查原文后才能进入项目结论。",
                ],
                limit=10,
            ),
            "compiled_documents": _append_industry_skill_section_to_documents(pack.compiled_documents, context),
            "feasibility_outline": [*pack.feasibility_outline, feasibility_section],
            "project_proposal_outline": [*pack.project_proposal_outline, proposal_section],
            "client_ppt_outline": [*pack.client_ppt_outline, ppt_section],
            "review_checklist": _dedupe_strings(
                [
                    *pack.review_checklist,
                    *industry_review_items,
                    "核对本地资料的年份、适用范围和原始出处，避免将行业参考写成项目已证实事实。",
                ],
                limit=12,
            ),
            "next_steps": _dedupe_strings(
                [
                    *pack.next_steps,
                    "对需要对外引用的数据、机构、政策和案例回查本地原件及官方来源，并补充项目级证据。",
                ],
                limit=8,
            ),
        }
    )
