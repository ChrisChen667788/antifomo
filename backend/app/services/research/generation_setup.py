from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.schemas.research import ResearchReportRequest
from app.services.content_extractor import normalize_text


@dataclass(frozen=True, slots=True)
class ResearchGenerationSetup:
    settings: Any
    llm: Any
    keyword: str
    report_research_focus: str | None
    followup_context: Any
    base_input_scope_hints: dict[str, object]
    followup_scope_hints: dict[str, object]
    followup_diagnostics: Any
    research_focus: str | None
    output_language: str
    research_mode: str
    runtime: dict[str, object]
    source_settings: Any
    preferred_wechat_accounts: tuple[str, ...]
    input_scope_hints: dict[str, object]
    archive_context_items: list[dict[str, object]]
    archive_context: str


@dataclass(frozen=True, slots=True)
class ResearchGenerationSetupDependencies:
    get_settings: Callable[[], Any]
    get_llm_service: Callable[[], Any]
    build_followup_context: Callable[[ResearchReportRequest], Any]
    infer_input_scope_hints: Callable[[str, str | None], dict[str, object]]
    build_followup_research_diagnostics: Callable[..., tuple[dict[str, object], Any]]
    build_followup_planning_focus: Callable[..., str | None]
    resolve_research_mode: Callable[[ResearchReportRequest], str]
    build_research_runtime: Callable[[ResearchReportRequest], dict[str, object]]
    read_research_source_settings: Callable[[], Any]
    merge_scope_hints_with_followup_context: Callable[[dict[str, object], dict[str, object]], dict[str, object]]
    merge_scope_hints: Callable[[dict[str, object], dict[str, object]], dict[str, object]]
    runtime_strategy_scope_hints: Callable[[ResearchReportRequest], dict[str, object]]
    apply_strategy_scope_planning: Callable[..., dict[str, object]]
    load_research_archive_context: Callable[..., list[dict[str, object]]]
    render_archive_prompt_context: Callable[[list[dict[str, object]]], str]
    merge_scope_hints_with_archive_context: Callable[..., dict[str, object]]
    curated_wechat_channels: tuple[str, ...]


def prepare_research_generation_setup(
    payload: ResearchReportRequest,
    *,
    deps: ResearchGenerationSetupDependencies,
) -> ResearchGenerationSetup:
    settings = deps.get_settings()
    llm = deps.get_llm_service()

    keyword = normalize_text(payload.keyword)
    report_research_focus = normalize_text(payload.research_focus or "") or None
    followup_context = deps.build_followup_context(payload)
    base_input_scope_hints = deps.infer_input_scope_hints(keyword, report_research_focus)
    followup_scope_hints, followup_diagnostics = deps.build_followup_research_diagnostics(
        keyword=keyword,
        report_research_focus=report_research_focus,
        followup_context=followup_context,
        include_wechat=payload.include_wechat,
        base_scope_hints=base_input_scope_hints,
    )
    research_focus = deps.build_followup_planning_focus(
        report_research_focus,
        followup_context=followup_context,
    ) or report_research_focus
    output_language = payload.output_language
    research_mode = deps.resolve_research_mode(payload)
    runtime = deps.build_research_runtime(payload)
    source_settings = deps.read_research_source_settings()
    preferred_wechat_accounts = (
        deps.curated_wechat_channels
        if payload.include_wechat and source_settings.enable_curated_wechat_channels
        else ()
    )
    input_scope_hints = deps.infer_input_scope_hints(keyword, research_focus)
    input_scope_hints = deps.merge_scope_hints_with_followup_context(input_scope_hints, followup_scope_hints)
    input_scope_hints = deps.merge_scope_hints(input_scope_hints, deps.runtime_strategy_scope_hints(payload))
    input_scope_hints = deps.apply_strategy_scope_planning(
        keyword=keyword,
        research_focus=research_focus,
        output_language=output_language,
        input_scope_hints=input_scope_hints,
    )
    archive_context_items = deps.load_research_archive_context(
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=input_scope_hints,
        limit=3 if research_mode == "fast" else 5,
    )
    archive_context = deps.render_archive_prompt_context(archive_context_items)
    input_scope_hints = deps.merge_scope_hints_with_archive_context(
        input_scope_hints,
        archive_context_items,
        keyword=keyword,
        research_focus=research_focus,
    )

    return ResearchGenerationSetup(
        settings=settings,
        llm=llm,
        keyword=keyword,
        report_research_focus=report_research_focus,
        followup_context=followup_context,
        base_input_scope_hints=base_input_scope_hints,
        followup_scope_hints=followup_scope_hints,
        followup_diagnostics=followup_diagnostics,
        research_focus=research_focus,
        output_language=output_language,
        research_mode=research_mode,
        runtime=runtime,
        source_settings=source_settings,
        preferred_wechat_accounts=tuple(preferred_wechat_accounts),
        input_scope_hints=input_scope_hints,
        archive_context_items=archive_context_items,
        archive_context=archive_context,
    )
