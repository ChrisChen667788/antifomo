from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.schemas.research import ResearchReportResponse
from app.services.content_extractor import normalize_text
from app.services.research.delivery_truth import apply_delivery_truth
from app.services.research.source_documents import SourceDocument


_READINESS_SUMMARY_NOTES = (
    "当前版本适合候选推进，关键预算、官方源或组织入口仍需继续核验。",
    "当前版本更适合作为待核验清单，不建议直接作为最终商业判断。",
)
_READINESS_ANGLE_NOTES = (
    "建议按轻量推进处理，并同步补关键证据。",
    "建议先补关键证据，再决定是否进入正式推进。",
)


def _without_readiness_notes(value: str, notes: tuple[str, ...]) -> str:
    cleaned = normalize_text(value)
    for note in notes:
        cleaned = normalize_text(cleaned.replace(note, ""))
    return cleaned.rstrip("。.!！")


@dataclass(frozen=True, slots=True)
class DeliveryEnrichmentDependencies:
    build_report_readiness: Callable[[ResearchReportResponse], Any]
    build_commercial_summary: Callable[[ResearchReportResponse], Any]
    build_technical_appendix: Callable[[ResearchReportResponse], Any]
    build_review_queue: Callable[[ResearchReportResponse], list[Any]]
    build_research_quality_profile: Callable[[ResearchReportResponse], Any]
    report_sources_to_source_documents: Callable[[list[Any]], list[SourceDocument]]
    load_runtime_research_retrieval_index: Callable[..., Any]
    attach_section_retrieval_packs: Callable[..., ResearchReportResponse]
    build_market_intelligence_pack: Callable[[ResearchReportResponse], Any]
    build_solution_delivery_pack: Callable[[ResearchReportResponse], Any]
    enrich_followup_diagnostics: Callable[[ResearchReportResponse], ResearchReportResponse]
    apply_report_readiness_guardrails: Callable[[ResearchReportResponse], ResearchReportResponse]
    build_account_pursuit_pack: Callable[[ResearchReportResponse], Any] | None = None
    build_commercial_bid_pack: Callable[[ResearchReportResponse], Any] | None = None


def apply_report_readiness_guardrails(report: ResearchReportResponse) -> ResearchReportResponse:
    readiness = report.report_readiness
    report = report.model_copy(
        update={
            "executive_summary": _without_readiness_notes(report.executive_summary, _READINESS_SUMMARY_NOTES),
            "consulting_angle": _without_readiness_notes(report.consulting_angle, _READINESS_ANGLE_NOTES),
        }
    )
    if readiness.status == "ready":
        return report
    if normalize_text(report.report_title).endswith(("待核验清单与补证路径", "待核驗清單與補證路徑", "Verification Backlog and Evidence Path")):
        return report
    executive_summary = normalize_text(report.executive_summary)
    consulting_angle = normalize_text(report.consulting_angle)
    if readiness.status == "degraded":
        summary_note = _READINESS_SUMMARY_NOTES[0]
        angle_note = _READINESS_ANGLE_NOTES[0]
    else:
        summary_note = _READINESS_SUMMARY_NOTES[1]
        angle_note = _READINESS_ANGLE_NOTES[1]

    def append_guardrail_note(text: str, note: str) -> str:
        normalized = normalize_text(text)
        if not normalized:
            return note
        if note in normalized:
            return normalized
        if normalized.endswith(("。", "！", "？")):
            return f"{normalized}{note}"
        if normalized.endswith((".", "!", "?")):
            return f"{normalized} {note}"
        return f"{normalized}。{note}"

    return report.model_copy(
        update={
            "executive_summary": append_guardrail_note(executive_summary, summary_note),
            "consulting_angle": append_guardrail_note(consulting_angle, angle_note),
        }
    )


def enrich_report_for_delivery(
    report: ResearchReportResponse,
    *,
    deps: DeliveryEnrichmentDependencies,
) -> ResearchReportResponse:
    readiness = deps.build_report_readiness(report)
    staged = report.model_copy(update={"report_readiness": readiness})
    if deps.build_account_pursuit_pack:
        account_pursuit_pack = deps.build_account_pursuit_pack(staged)
        staged = staged.model_copy(update={"account_pursuit_pack": account_pursuit_pack})
    staged = apply_delivery_truth(staged)
    commercial_bid_pack = (
        deps.build_commercial_bid_pack(staged)
        if deps.build_commercial_bid_pack
        else staged.commercial_bid_pack
    )
    commercial_summary = deps.build_commercial_summary(staged)
    enriched = staged.model_copy(
        update={
            "commercial_summary": commercial_summary,
            "commercial_bid_pack": commercial_bid_pack,
        }
    )
    enriched = enriched.model_copy(
        update={
            "technical_appendix": deps.build_technical_appendix(enriched),
            "review_queue": deps.build_review_queue(enriched),
        }
    )
    enriched = enriched.model_copy(update={"quality_profile": deps.build_research_quality_profile(enriched)})
    runtime_sources = deps.report_sources_to_source_documents(enriched.sources)
    if runtime_sources and enriched.sections:
        runtime_index = deps.load_runtime_research_retrieval_index(
            sources=runtime_sources,
            scope_hints={
                "regions": list(getattr(getattr(enriched, "source_diagnostics", None), "scope_regions", []) or []),
                "industries": list(getattr(getattr(enriched, "source_diagnostics", None), "scope_industries", []) or []),
            },
        )
        if runtime_index.chunks:
            enriched = deps.attach_section_retrieval_packs(enriched, runtime_index, limit_per_section=3)
    enriched = enriched.model_copy(
        update={
            "market_intelligence": deps.build_market_intelligence_pack(enriched),
            "solution_delivery_pack": deps.build_solution_delivery_pack(enriched),
        }
    )
    return deps.enrich_followup_diagnostics(deps.apply_report_readiness_guardrails(enriched))
