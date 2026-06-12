from __future__ import annotations

from types import SimpleNamespace

from app.schemas.research import ResearchReportRequest
from app.services.research.run_metrics import ResearchRunMetrics
from app.services.research.workflow_engine import (
    DeterministicResearchWorkflowDependencies,
    DeterministicResearchWorkflowEngine,
    ResearchWorkflowExecution,
)
from app.services.research_service import execute_research_report_workflow


def test_deterministic_engine_preserves_callbacks_and_returns_metrics() -> None:
    progress_events: list[tuple[str, int, str]] = []
    snapshots: list[object] = []
    setup_dependency = object()
    workflow_dependency = object()

    def prepare_setup(payload: ResearchReportRequest, *, deps: object) -> object:
        assert deps is setup_dependency
        return {"keyword": payload.keyword}

    def run_workflow(
        payload: ResearchReportRequest,
        *,
        setup: object,
        progress_callback: object,
        snapshot_callback: object,
        deps: object,
    ) -> object:
        assert deps is workflow_dependency
        assert setup == {"keyword": payload.keyword}
        progress_callback("search", 26, "searching")
        report = SimpleNamespace(source_count=3, sections=["a", "b"])
        snapshot_callback(report)
        progress_callback("completed", 100, "complete")
        return report

    engine = DeterministicResearchWorkflowEngine(
        DeterministicResearchWorkflowDependencies(
            prepare_setup=prepare_setup,
            setup_dependencies=lambda: setup_dependency,
            run_workflow=run_workflow,
            workflow_dependencies=lambda: workflow_dependency,
        )
    )
    metrics = ResearchRunMetrics(run_id="engine-run")
    execution = engine.execute(
        ResearchReportRequest(keyword="政务云预算"),
        progress_callback=lambda stage, percent, message: progress_events.append((stage, percent, message)),
        snapshot_callback=snapshots.append,
        metrics=metrics,
    )

    assert execution.report.source_count == 3
    assert execution.metrics is metrics
    assert progress_events == [("search", 26, "searching"), ("completed", 100, "complete")]
    assert len(snapshots) == 1
    snapshot = execution.metrics.snapshot()
    assert snapshot["workflow_engine"] == "deterministic"
    assert snapshot["status"] == "succeeded"
    assert snapshot["gauges"]["source_count"] == 3.0
    assert snapshot["gauges"]["section_count"] == 2.0
    assert snapshot["nodes"]["workflow.setup"]["succeeded"] == 1
    assert snapshot["nodes"]["workflow.generate"]["succeeded"] == 1


def test_research_facade_executes_through_injected_engine() -> None:
    report = SimpleNamespace(source_count=1, sections=[])
    metrics = ResearchRunMetrics(run_id="facade-run")

    class _Engine:
        name = "fixture"

        def execute(self, payload: ResearchReportRequest, **kwargs: object) -> ResearchWorkflowExecution:
            assert payload.keyword == "智算中心"
            assert kwargs["metrics"] is metrics
            return ResearchWorkflowExecution(report=report, metrics=metrics)

    execution = execute_research_report_workflow(
        ResearchReportRequest(keyword="智算中心"),
        metrics=metrics,
        engine=_Engine(),
    )

    assert execution.report is report
    assert execution.metrics is metrics
