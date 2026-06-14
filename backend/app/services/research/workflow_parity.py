from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.research import (
    ResearchReportRequest,
    ResearchReportResponse,
    ResearchReportSectionOut,
    ResearchSourceOut,
)
from app.services.research.evaluation_dataset import (
    ResearchEvaluationCase,
    ResearchEvaluationDatasetManifest,
)
from app.services.research.langgraph_workflow_engine import LangGraphResearchWorkflowEngine
from app.services.research.run_metrics import ResearchRunMetrics
from app.services.research.workflow_engine import (
    DeterministicResearchWorkflowDependencies,
    DeterministicResearchWorkflowEngine,
    ResearchWorkflowEngine,
)


_FIXED_GENERATED_AT = datetime(2026, 6, 14, tzinfo=timezone.utc)


class ResearchWorkflowParityCaseResult(BaseModel):
    case_id: str
    passed: bool
    differences: list[str] = Field(default_factory=list)


class ResearchWorkflowParityResult(BaseModel):
    dataset_id: str
    dataset_version: str
    dataset_status: str
    dataset_content_sha256: str
    selected_case_count: int
    passed_case_count: int
    failed_case_count: int
    parity_rate: float
    production_gate_eligible: bool
    production_gate_passed: bool
    gate_blockers: list[str] = Field(default_factory=list)
    cases: list[ResearchWorkflowParityCaseResult]

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(self.model_dump(mode="json"), ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )


def _offline_report(case: ResearchEvaluationCase, payload: ResearchReportRequest) -> ResearchReportResponse:
    source_domain = case.expected_source_domains[0]
    behavior_summary = {
        "answer": "已按锁定评测要求生成离线编排基准。",
        "guard": "合规边界：需授权后才能处理受限信息。",
        "refuse": "无法提供受限信息，仅保留公开资料核验建议。",
    }[case.expected_behavior]
    answer_terms = case.reference_answer_terms or case.required_terms
    sections = [
        ResearchReportSectionOut(
            title=title,
            items=[behavior_summary, *answer_terms],
            status="ready",
            evidence_density="high",
            source_quality="high",
            confidence_tone="high",
            evidence_count=1,
            evidence_quota=1,
            meets_evidence_quota=True,
        )
        for title in case.required_sections
    ]
    sources = [
        ResearchSourceOut(
            title=f"{case.keyword} 官方来源",
            url=f"https://{source_domain}/offline-parity/{case.case_id}",
            domain=source_domain,
            snippet=case.source_relevance_notes,
            search_query=case.keyword,
            source_type="offline_parity_fixture",
            content_status="fixture",
            source_label=source_domain,
            source_tier="official",
        )
    ]
    return ResearchReportResponse(
        keyword=payload.keyword,
        research_focus=payload.research_focus,
        output_language=payload.output_language,
        research_mode=payload.research_mode,
        report_title=f"{case.keyword} 编排等价性基准",
        executive_summary=" ".join([behavior_summary, *answer_terms]),
        consulting_angle=case.expected_methodology,
        sections=sections,
        source_count=len(sources),
        query_plan=[case.keyword, case.research_focus],
        sources=sources,
        generated_at=_FIXED_GENERATED_AT,
    )


def _offline_dependencies(case: ResearchEvaluationCase) -> DeterministicResearchWorkflowDependencies:
    setup_dependencies = {"case_id": case.case_id}
    workflow_dependencies = {"dataset_id": case.dataset_id}

    def prepare_setup(payload: ResearchReportRequest, *, deps: object) -> dict[str, Any]:
        if deps is not setup_dependencies:
            raise RuntimeError("offline parity setup dependency identity changed")
        return {
            "keyword": payload.keyword,
            "focus": payload.research_focus,
            "case_id": case.case_id,
        }

    def run_workflow(
        payload: ResearchReportRequest,
        *,
        setup: object,
        progress_callback: Any,
        snapshot_callback: Any,
        deps: object,
    ) -> ResearchReportResponse:
        if deps is not workflow_dependencies:
            raise RuntimeError("offline parity workflow dependency identity changed")
        if setup != {
            "keyword": payload.keyword,
            "focus": payload.research_focus,
            "case_id": case.case_id,
        }:
            raise RuntimeError("offline parity setup payload changed")
        progress_callback("planning", 15, "offline planning complete")
        progress_callback("retrieval", 60, "offline evidence fixture ready")
        report = _offline_report(case, payload)
        if snapshot_callback is not None:
            snapshot_callback(report)
        progress_callback("completed", 100, "offline workflow complete")
        return report

    return DeterministicResearchWorkflowDependencies(
        prepare_setup=prepare_setup,
        setup_dependencies=lambda: setup_dependencies,
        run_workflow=run_workflow,
        workflow_dependencies=lambda: workflow_dependencies,
    )


def _normalized_metrics(snapshot: dict[str, object]) -> dict[str, object]:
    gauges = snapshot.get("gauges")
    nodes = snapshot.get("nodes")
    normalized_nodes: dict[str, object] = {}
    if isinstance(nodes, dict):
        for name, raw_metric in nodes.items():
            if name == "workflow.graph" or not isinstance(raw_metric, dict):
                continue
            normalized_nodes[name] = {
                key: raw_metric.get(key)
                for key in ("attempts", "succeeded", "failed", "last_error")
            }
    return {
        "status": snapshot.get("status"),
        "counters": snapshot.get("counters"),
        "gauges": {
            key: gauges.get(key)
            for key in ("progress_percent", "section_count", "source_count")
        }
        if isinstance(gauges, dict)
        else {},
        "nodes": normalized_nodes,
        "cost_ledger": snapshot.get("cost_ledger"),
    }


def _execute_engine(
    engine: ResearchWorkflowEngine,
    case: ResearchEvaluationCase,
) -> tuple[dict[str, Any], list[tuple[str, int, str]], list[dict[str, Any]], dict[str, object]]:
    progress_events: list[tuple[str, int, str]] = []
    snapshots: list[dict[str, Any]] = []
    metrics = ResearchRunMetrics(run_id=f"offline-parity-{engine.name}-{case.case_id}")
    execution = engine.execute(
        ResearchReportRequest(
            keyword=case.keyword,
            research_focus=case.research_focus,
            output_language=case.language,
            include_wechat=False,
            research_mode="deep",
            max_sources=14,
        ),
        progress_callback=lambda stage, percent, message: progress_events.append(
            (stage, percent, message)
        ),
        snapshot_callback=lambda report: snapshots.append(report.model_dump(mode="json")),
        metrics=metrics,
    )
    return (
        execution.report.model_dump(mode="json"),
        progress_events,
        snapshots,
        _normalized_metrics(execution.metrics.snapshot()),
    )


def _compare_case(case: ResearchEvaluationCase) -> ResearchWorkflowParityCaseResult:
    dependencies = _offline_dependencies(case)
    deterministic = _execute_engine(DeterministicResearchWorkflowEngine(dependencies), case)
    langgraph = _execute_engine(LangGraphResearchWorkflowEngine(dependencies), case)
    labels = ("report", "progress_events", "snapshots", "metrics")
    differences = [
        label
        for label, deterministic_value, langgraph_value in zip(labels, deterministic, langgraph)
        if deterministic_value != langgraph_value
    ]
    return ResearchWorkflowParityCaseResult(
        case_id=case.case_id,
        passed=not differences,
        differences=differences,
    )


def run_research_workflow_parity(
    manifest: ResearchEvaluationDatasetManifest,
    cases: Sequence[ResearchEvaluationCase],
) -> ResearchWorkflowParityResult:
    results = [_compare_case(case) for case in cases]
    passed_case_count = sum(1 for result in results if result.passed)
    gate_blockers: list[str] = []
    if manifest.status != "locked":
        gate_blockers.append(f"dataset status is {manifest.status}, expected locked")
    if len(cases) != manifest.expected_case_count:
        gate_blockers.append(
            f"selected {len(cases)} of {manifest.expected_case_count} required cases"
        )
    if passed_case_count != len(cases):
        gate_blockers.append(f"{len(cases) - passed_case_count} workflow parity cases failed")
    production_gate_eligible = not gate_blockers
    return ResearchWorkflowParityResult(
        dataset_id=manifest.dataset_id,
        dataset_version=manifest.version,
        dataset_status=manifest.status,
        dataset_content_sha256=manifest.content_sha256,
        selected_case_count=len(cases),
        passed_case_count=passed_case_count,
        failed_case_count=len(cases) - passed_case_count,
        parity_rate=round(passed_case_count / len(cases), 8) if cases else 0.0,
        production_gate_eligible=production_gate_eligible,
        production_gate_passed=production_gate_eligible,
        gate_blockers=gate_blockers,
        cases=results,
    )
