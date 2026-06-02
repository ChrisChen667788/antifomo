from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.schemas.research import ResearchReportResponse
from app.services.research.source_documents import SourceDocument


@dataclass(frozen=True, slots=True)
class SectionRetrievalRuntimeContext:
    draft_report_for_followup: ResearchReportResponse
    section_retrieval_context: str
    followup_section_focus_context: str


def build_section_retrieval_runtime_context(
    *,
    draft_report: ResearchReportResponse,
    sources: list[SourceDocument],
    scope_hints: dict[str, object],
    followup_enabled: bool,
    load_runtime_research_retrieval_index: Callable[..., Any],
    attach_section_retrieval_packs: Callable[..., ResearchReportResponse],
    render_section_retrieval_prompt_context: Callable[..., str],
    render_followup_section_focus_prompt_context: Callable[[ResearchReportResponse], str],
    limit_per_section: int = 3,
) -> SectionRetrievalRuntimeContext:
    runtime_retrieval_index = load_runtime_research_retrieval_index(
        sources=sources,
        scope_hints=scope_hints,
    )
    draft_report_for_followup = draft_report
    if runtime_retrieval_index.chunks and followup_enabled:
        draft_report_for_followup = attach_section_retrieval_packs(
            draft_report,
            runtime_retrieval_index,
            limit_per_section=limit_per_section,
        )
    section_retrieval_context = (
        render_section_retrieval_prompt_context(
            draft_report,
            index=runtime_retrieval_index,
            limit_per_section=limit_per_section,
        )
        if runtime_retrieval_index.chunks
        else ""
    )
    followup_section_focus_context = (
        render_followup_section_focus_prompt_context(draft_report_for_followup)
        if followup_enabled
        else "无"
    )
    return SectionRetrievalRuntimeContext(
        draft_report_for_followup=draft_report_for_followup,
        section_retrieval_context=section_retrieval_context,
        followup_section_focus_context=followup_section_focus_context,
    )
