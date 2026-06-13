from __future__ import annotations

import json
import logging
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from app.schemas.research import ResearchReportRequest, ResearchReportResponse
from app.services.research.run_metrics import ResearchRunMetrics, activate_research_run_metrics
from app.services.research.workflow_engine import (
    DeterministicResearchWorkflowDependencies,
    ResearchProgressCallback,
    ResearchSnapshotCallback,
    ResearchWorkflowExecution,
)


logger = logging.getLogger("anti_fomo.research.workflow")


class LangGraphResearchWorkflowState(TypedDict, total=False):
    payload: ResearchReportRequest
    setup: Any
    report: ResearchReportResponse


class LangGraphResearchWorkflowEngine:
    """Shadow graph adapter that preserves the framework-neutral workflow contract."""

    name = "langgraph_shadow"

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

        def prepare_node(state: LangGraphResearchWorkflowState) -> dict[str, Any]:
            with run_metrics.measure_node("workflow.setup"):
                setup = self._deps.prepare_setup(
                    state["payload"],
                    deps=self._deps.setup_dependencies(),
                )
            return {"setup": setup}

        def generate_node(state: LangGraphResearchWorkflowState) -> dict[str, Any]:
            with run_metrics.measure_node("workflow.generate"):
                report = self._deps.run_workflow(
                    state["payload"],
                    setup=state["setup"],
                    progress_callback=emit_progress,
                    snapshot_callback=snapshot_callback,
                    deps=self._deps.workflow_dependencies(),
                )
            return {"report": report}

        def finalize_node(state: LangGraphResearchWorkflowState) -> dict[str, Any]:
            report = state.get("report")
            if report is None:
                raise RuntimeError("LangGraph workflow completed without a report")
            return {"report": report}

        builder = StateGraph(LangGraphResearchWorkflowState)
        builder.add_node("prepare", prepare_node)
        builder.add_node("generate", generate_node)
        builder.add_node("finalize", finalize_node)
        builder.add_edge(START, "prepare")
        builder.add_edge("prepare", "generate")
        builder.add_edge("generate", "finalize")
        builder.add_edge("finalize", END)
        graph = builder.compile()

        try:
            with activate_research_run_metrics(run_metrics):
                with run_metrics.measure_node("workflow.graph"):
                    result = graph.invoke({"payload": payload})
        except Exception:
            run_metrics.finish("failed")
            logger.warning("research_run_metrics=%s", json.dumps(run_metrics.snapshot(), ensure_ascii=False))
            raise

        report = result.get("report")
        if report is None:
            run_metrics.finish("failed")
            raise RuntimeError("LangGraph workflow returned an invalid final state")
        run_metrics.set_gauge("source_count", float(report.source_count))
        run_metrics.set_gauge("section_count", float(len(report.sections)))
        run_metrics.finish("succeeded")
        logger.info("research_run_metrics=%s", json.dumps(run_metrics.snapshot(), ensure_ascii=False))
        return ResearchWorkflowExecution(report=report, metrics=run_metrics)
