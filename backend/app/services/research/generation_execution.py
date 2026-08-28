from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
from typing import Any

from app.schemas.research import (
    ResearchEntityGraphOut,
    ResearchFollowupContextOut,
    ResearchFollowupDiagnosticsOut,
    ResearchQuestionTreeOut,
    ResearchReportResponse,
    ResearchSourceDiagnosticsOut,
)
from app.services.llm_parser import ResearchReportResult
from app.services.research.source_documents import SourceDocument


@dataclass(frozen=True, slots=True)
class ResearchGenerationExecutionDependencies:
    build_partial_report_result: Callable[..., ResearchReportResult]
    render_followup_diagnostics_prompt_context: Callable[[ResearchFollowupDiagnosticsOut], str]
    emit_research_progress: Callable[..., None]
    build_progress_message: Callable[..., str]
    build_partial_report_response: Callable[..., ResearchReportResponse]
    build_section_retrieval_runtime_context: Callable[..., Any]
    emit_research_snapshot: Callable[..., None]
    render_source_digest: Callable[[list[SourceDocument]], str]
    render_followup_prompt_context: Callable[[ResearchFollowupContextOut], str]
    render_retrieval_correction_context: Callable[[Any], str]
    render_industry_methodology_context: Callable[[dict[str, object]], str]
    parse_research_report_response: Callable[..., ResearchReportResult]
    merge_result_with_intelligence: Callable[[ResearchReportResult, dict[str, list[str]]], ResearchReportResult]
    apply_topic_specific_overrides: Callable[..., ResearchReportResult]
    apply_strategy_llm_refinement: Callable[..., ResearchReportResult]
    render_question_tree_prompt_context: Callable[[ResearchQuestionTreeOut], str] = lambda _tree: ""
    enforce_entity_authenticity: Callable[..., tuple[ResearchReportResult, dict[str, object]]] = (
        lambda parsed, **_kwargs: (parsed, {})
    )


@dataclass(frozen=True, slots=True)
class ResearchGenerationExecutionResult:
    parsed: ResearchReportResult
    draft_report: ResearchReportResponse
    generation_provider: str = ""
    generation_model: str = ""
    generation_status: str = ""
    generation_fallback_used: bool = False
    generation_notes: tuple[str, ...] = ()
    entity_authenticity_audit: dict[str, object] | None = None


def _is_fallback_run(result: Any | None) -> bool:
    if result is None:
        return False
    metadata = getattr(result, "metadata", {}) or {}
    return bool(
        getattr(result, "status", "") == "fallback"
        or getattr(result, "provider", "") == "mock"
        or getattr(result, "model", "") == "deterministic-mock"
        or metadata.get("fallback_used")
    )


def _fallback_messages(output_language: str) -> tuple[str, str]:
    if output_language == "en":
        return (
            "The formal report model timed out; this is an evidence-backed degraded draft, not a deliverable report.",
            "Restore model quota and connectivity, then regenerate the formal report before delivery.",
        )
    if output_language == "zh-TW":
        return (
            "正式研報模型逾時，當前內容為證據支撐的降級草稿，不可作為正式交付稿。",
            "恢復模型額度與連線後重新生成正式研報，再進入交付。",
        )
    return (
        "正式研报模型超时，当前内容为有证据支撑的降级草稿，不可作为正式交付稿。",
        "恢复模型额度与连接后重新生成正式研报，再进入交付。",
    )


def _append_unique(values: list[str], value: str) -> list[str]:
    return [*values, value] if value and value not in values else list(values)


def execute_research_generation(
    *,
    keyword: str,
    research_focus: str | None,
    report_research_focus: str | None,
    output_language: str,
    research_mode: str,
    archive_context: str,
    followup_context: ResearchFollowupContextOut,
    followup_diagnostics: ResearchFollowupDiagnosticsOut,
    source_intelligence: dict[str, list[str]],
    scope_hints: dict[str, object],
    llm: Any,
    runtime: dict[str, int | str | bool],
    effective_query_plan: list[str],
    adapter_query_plan: list[str],
    sources: list[SourceDocument],
    source_diagnostics: ResearchSourceDiagnosticsOut,
    entity_graph: ResearchEntityGraphOut,
    retrieval_correction_profile: Any,
    progress_callback: Any | None,
    snapshot_callback: Any | None,
    section_retrieval_dependencies: dict[str, Any],
    deps: ResearchGenerationExecutionDependencies,
    research_question_tree: ResearchQuestionTreeOut | None = None,
) -> ResearchGenerationExecutionResult:
    outline_result = deps.build_partial_report_result(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        research_mode=research_mode,
        archive_context=archive_context,
        followup_diagnostics=deps.render_followup_diagnostics_prompt_context(followup_diagnostics),
        source_intelligence=source_intelligence,
        scope_hints=scope_hints,
        llm=llm,
        llm_timeout_seconds=int(runtime["llm_timeout_seconds"]),
    )
    outline_run_result = getattr(llm, "last_run_result", None)
    outline_is_remote = bool(outline_run_result is not None and not _is_fallback_run(outline_run_result))
    deps.emit_research_progress(
        progress_callback,
        "synthesizing",
        82,
        deps.build_progress_message("正在综合多源证据生成研报", keyword=keyword, research_focus=research_focus, mode=research_mode),
    )
    draft_report = deps.build_partial_report_response(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        research_mode=research_mode,
        parsed=outline_result,
        query_plan=effective_query_plan + adapter_query_plan,
        sources=sources,
        source_diagnostics=source_diagnostics,
        entity_graph=entity_graph,
    )
    section_runtime_context = deps.build_section_retrieval_runtime_context(
        draft_report=draft_report,
        sources=sources,
        scope_hints=scope_hints,
        followup_enabled=followup_diagnostics.enabled,
        **section_retrieval_dependencies,
    )
    deps.emit_research_snapshot(snapshot_callback, draft_report)
    source_digest = deps.render_source_digest(sources)
    source_summary = json.dumps(
        [
            {
                "title": source.title,
                "url": source.url,
                "domain": source.domain,
                "source_type": source.source_type,
                "source_label": source.source_label,
                "source_tier": source.source_tier,
                "content_status": source.content_status,
            }
            for source in sources
        ],
        ensure_ascii=False,
    )
    raw = llm.run_prompt(
        "research_report.txt",
        {
            "keyword": keyword,
            "research_focus": report_research_focus or research_focus or "",
            "output_language": output_language,
            "research_mode": research_mode,
            "query_plan": " | ".join(effective_query_plan),
            "__timeout_seconds": str(int(runtime["llm_timeout_seconds"])),
            "__stream_response": "true",
            "__max_output_tokens": str(int(runtime.get("llm_max_output_tokens", 7000))),
            "source_count": str(len(sources)),
            "archive_context": archive_context,
            "source_summary": source_summary,
            "source_digest": source_digest,
            "followup_context": deps.render_followup_prompt_context(followup_context),
            "followup_diagnostics": deps.render_followup_diagnostics_prompt_context(followup_diagnostics),
            "followup_section_focus_context": section_runtime_context.followup_section_focus_context,
            "followup_report_title": followup_context.followup_report_title,
            "followup_report_summary": followup_context.followup_report_summary,
            "supplemental_context": followup_context.supplemental_context,
            "supplemental_evidence": followup_context.supplemental_evidence,
            "supplemental_requirements": followup_context.supplemental_requirements,
            "outline_hint": json.dumps(
                {
                    "report_title": outline_result.report_title,
                    "executive_summary": outline_result.executive_summary,
                    "consulting_angle": outline_result.consulting_angle,
                },
                ensure_ascii=False,
            ),
            "scope_hints": json.dumps(scope_hints, ensure_ascii=False),
            "source_intelligence": json.dumps(source_intelligence, ensure_ascii=False),
            "section_retrieval_context": section_runtime_context.section_retrieval_context,
            "retrieval_correction_context": deps.render_retrieval_correction_context(retrieval_correction_profile),
            "industry_methodology_context": deps.render_industry_methodology_context(scope_hints),
            "research_question_tree_context": deps.render_question_tree_prompt_context(
                research_question_tree or ResearchQuestionTreeOut()
            ),
        },
    )
    generation_run_result = getattr(llm, "last_run_result", None)
    generation_provider = str(getattr(generation_run_result, "provider", "") or "")
    generation_model = str(getattr(generation_run_result, "model", "") or "")
    generation_status = str(getattr(generation_run_result, "status", "") or "succeeded")
    generation_fallback_used = _is_fallback_run(generation_run_result)
    parsed = deps.merge_result_with_intelligence(
        deps.parse_research_report_response(raw, output_language=output_language),
        source_intelligence,
        scope_hints=scope_hints,
    )
    parsed = deps.apply_topic_specific_overrides(
        parsed,
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        scope_hints=scope_hints,
        intelligence=source_intelligence,
    )
    generation_notes: tuple[str, ...] = ()
    if generation_fallback_used:
        risk, next_action = _fallback_messages(output_language)
        update: dict[str, object] = {
            "risks": _append_unique(parsed.risks, risk),
            "next_actions": _append_unique(parsed.next_actions, next_action),
        }
        if outline_is_remote:
            update.update(
                report_title=outline_result.report_title,
                executive_summary=outline_result.executive_summary,
                consulting_angle=outline_result.consulting_angle,
            )
        parsed = parsed.model_copy(update=update)
        generation_notes = (risk, next_action)
    else:
        parsed = deps.apply_strategy_llm_refinement(
            parsed,
            keyword=keyword,
            research_focus=research_focus,
            output_language=output_language,
            scope_hints=scope_hints,
            intelligence=source_intelligence,
        )
    parsed, entity_authenticity_audit = deps.enforce_entity_authenticity(
        parsed,
        sources=sources,
        scope_hints=scope_hints,
        output_language=output_language,
    )
    return ResearchGenerationExecutionResult(
        parsed=parsed,
        draft_report=draft_report,
        generation_provider=generation_provider,
        generation_model=generation_model,
        generation_status=generation_status,
        generation_fallback_used=generation_fallback_used,
        generation_notes=generation_notes,
        entity_authenticity_audit=entity_authenticity_audit,
    )
