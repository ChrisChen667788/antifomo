from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import json
import logging
from typing import Any, Protocol

from app.schemas.research import ResearchReportRequest, ResearchReportResponse
from app.services.research.run_metrics import ResearchRunMetrics, activate_research_run_metrics


ResearchProgressCallback = Callable[[str, int, str], None]
ResearchSnapshotCallback = Callable[[ResearchReportResponse], None]

logger = logging.getLogger("anti_fomo.research.workflow")


@dataclass(frozen=True, slots=True)
class ResearchWorkflowExecution:
    report: ResearchReportResponse
    metrics: ResearchRunMetrics


class ResearchWorkflowEngine(Protocol):
    name: str

    def execute(
        self,
        payload: ResearchReportRequest,
        *,
        progress_callback: ResearchProgressCallback | None = None,
        snapshot_callback: ResearchSnapshotCallback | None = None,
        metrics: ResearchRunMetrics | None = None,
    ) -> ResearchWorkflowExecution:
        """Execute a research workflow without exposing its orchestration framework."""


@dataclass(frozen=True, slots=True)
class DeterministicResearchWorkflowDependencies:
    prepare_setup: Callable[..., Any]
    setup_dependencies: Callable[[], Any]
    run_workflow: Callable[..., ResearchReportResponse]
    workflow_dependencies: Callable[[], Any]


class DeterministicResearchWorkflowEngine:
    name = "deterministic"

    def __init__(self, deps: DeterministicResearchWorkflowDependencies) -> None:
        self._deps = deps

    def execute(
        self,
        payload: ResearchReportRequest,
        *,
        progress_callback: ResearchProgressCallback | None = None,
        snapshot_callback: ResearchSnapshotCallback | None = None,
        metrics: ResearchRunMetrics | None = None,
    ) -> ResearchWorkflowExecution:
        run_metrics = metrics or ResearchRunMetrics(workflow_engine=self.name)
        run_metrics.workflow_engine = self.name

        def emit_progress(stage_key: str, progress_percent: int, message: str) -> None:
            run_metrics.observe_progress(stage_key, progress_percent)
            if progress_callback is not None:
                progress_callback(stage_key, progress_percent, message)

        try:
            with activate_research_run_metrics(run_metrics):
                with run_metrics.measure_node("workflow.setup"):
                    setup = self._deps.prepare_setup(
                        payload,
                        deps=self._deps.setup_dependencies(),
                    )
                with run_metrics.measure_node("workflow.generate"):
                    report = self._deps.run_workflow(
                        payload,
                        setup=setup,
                        progress_callback=emit_progress,
                        snapshot_callback=snapshot_callback,
                        deps=self._deps.workflow_dependencies(),
                    )
        except Exception:
            run_metrics.finish("failed")
            logger.warning("research_run_metrics=%s", json.dumps(run_metrics.snapshot(), ensure_ascii=False))
            raise

        run_metrics.set_gauge("source_count", float(report.source_count))
        run_metrics.set_gauge("section_count", float(len(report.sections)))
        run_metrics.finish("succeeded")
        logger.info("research_run_metrics=%s", json.dumps(run_metrics.snapshot(), ensure_ascii=False))
        return ResearchWorkflowExecution(report=report, metrics=run_metrics)
