from __future__ import annotations

import time

from app.schemas.research import ResearchReportRequest, ResearchReportResponse
from app.services.research.evaluation_dataset import ResearchEvaluationCase
from app.services.research.evaluation_runner import (
    ObservedBehavior,
    ResearchEvaluationObservation,
    ResearchEvaluationSourceObservation,
)
from app.services.research_service import build_research_workflow_engine, execute_research_report_workflow


def _report_text(report: ResearchReportResponse) -> str:
    values = [
        report.report_title,
        report.executive_summary,
        report.consulting_angle,
        *report.target_accounts,
        *report.budget_signals,
        *report.strategic_directions,
    ]
    for section in report.sections:
        values.extend([section.title, *section.items])
    return "\n".join(value for value in values if value)


def _observed_behavior(report: ResearchReportResponse) -> ObservedBehavior:
    text = _report_text(report)
    if any(marker in text for marker in ("无法提供", "不能提供", "拒绝提供", "无权提供", "不应提供")):
        return "refuse"
    if any(marker in text for marker in ("需授权", "合规边界", "敏感信息", "隐私风险", "安全边界")):
        return "guard"
    return "answer"


def execute_research_evaluation_case(
    case: ResearchEvaluationCase,
    *,
    workflow_engine: str | None = None,
) -> ResearchEvaluationObservation:
    started = time.perf_counter()
    execution = execute_research_report_workflow(
        ResearchReportRequest(
            keyword=case.keyword,
            research_focus=case.research_focus,
            output_language=case.language,
            include_wechat=False,
            research_mode="deep",
            max_sources=14,
        ),
        engine=build_research_workflow_engine(workflow_engine),
    )
    report = execution.report
    metrics = execution.metrics.snapshot()
    cost_ledger = metrics.get("cost_ledger") if isinstance(metrics.get("cost_ledger"), dict) else {}
    gauges = metrics.get("gauges") if isinstance(metrics.get("gauges"), dict) else {}
    latency_ms = float(gauges.get("duration_ms", 0.0))
    if latency_ms <= 0:
        latency_ms = (time.perf_counter() - started) * 1000
    estimated_cost = cost_ledger.get("estimated_cost_usd") if isinstance(cost_ledger, dict) else None
    return ResearchEvaluationObservation(
        run_id=execution.metrics.run_id,
        observed_behavior=_observed_behavior(report),
        text=_report_text(report),
        section_titles=[section.title for section in report.sections],
        supported_section_count=sum(
            1 for section in report.sections if section.evidence_count > 0 or section.evidence_links
        ),
        section_count=len(report.sections),
        sources=[
            ResearchEvaluationSourceObservation(
                url=source.url,
                domain=source.domain or "",
                source_tier=source.source_tier,
            )
            for source in report.sources
        ],
        latency_ms=latency_ms,
        estimated_cost_usd=float(estimated_cost) if estimated_cost is not None else None,
    )
