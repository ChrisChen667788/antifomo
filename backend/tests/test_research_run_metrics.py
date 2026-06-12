from __future__ import annotations

import pytest

from app.services.research.run_metrics import (
    CostLedgerEntry,
    ResearchRunMetrics,
    activate_research_run_metrics,
    instrument_llm_service,
)


class _StaticLLM:
    model = "fixture-model"

    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        return '{"ok": true}'


class _BrokenLLM:
    model = "broken-model"

    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        raise RuntimeError("provider unavailable")


def test_cost_ledger_aggregates_tokens_cost_and_status() -> None:
    metrics = ResearchRunMetrics(run_id="run-1")
    metrics.cost_ledger.record(
        CostLedgerEntry(
            category="llm",
            operation="research_report.txt",
            provider="fixture",
            model="fixture-model",
            status="succeeded",
            latency_ms=42,
            input_tokens=120,
            output_tokens=30,
            estimated_cost_usd=0.0125,
        )
    )
    metrics.cost_ledger.record(
        CostLedgerEntry(
            category="llm",
            operation="research_strategy_refine.txt",
            provider="fixture",
            model="fixture-model",
            status="failed",
            latency_ms=12,
            input_tokens=20,
        )
    )

    snapshot = metrics.cost_ledger.snapshot()

    assert snapshot["entry_count"] == 2
    assert snapshot["model_call_count"] == 2
    assert snapshot["failed_call_count"] == 1
    assert snapshot["total_tokens"] == 170
    assert snapshot["estimated_cost_usd"] == 0.0125
    assert snapshot["priced_entry_count"] == 1
    assert snapshot["unpriced_entry_count"] == 1


def test_metered_llm_records_success_and_failure_without_changing_protocol() -> None:
    metrics = ResearchRunMetrics(run_id="run-2")
    with activate_research_run_metrics(metrics):
        service = instrument_llm_service(_StaticLLM(), role="generation")
        assert service.run_prompt("missing-test-prompt.txt", {"keyword": "政务云"}) == '{"ok": true}'

        broken = instrument_llm_service(_BrokenLLM(), role="strategy")
        with pytest.raises(RuntimeError, match="provider unavailable"):
            broken.run_prompt("missing-test-prompt.txt", {"keyword": "智算中心"})

    snapshot = metrics.cost_ledger.snapshot()
    assert snapshot["model_call_count"] == 2
    assert snapshot["failed_call_count"] == 1
    assert snapshot["total_tokens"] > 0
    assert snapshot["estimated_cost_usd"] is None
    assert snapshot["entries"][0]["metadata"]["token_counting"] == "estimated"


def test_run_metrics_records_nodes_progress_and_completion() -> None:
    metrics = ResearchRunMetrics(run_id="run-3")
    with metrics.measure_node("workflow.setup"):
        metrics.increment("queries", 3)
    metrics.observe_progress("search", 26)
    metrics.observe_progress("extracting", 42)
    metrics.finish("succeeded")

    snapshot = metrics.snapshot()
    assert snapshot["status"] == "succeeded"
    assert snapshot["finished_at"]
    assert snapshot["counters"]["queries"] == 3
    assert snapshot["gauges"]["progress_percent"] == 42.0
    assert snapshot["nodes"]["workflow.setup"]["succeeded"] == 1
    assert snapshot["nodes"]["stage.search"]["succeeded"] == 1
    assert snapshot["nodes"]["stage.extracting"]["succeeded"] == 1
