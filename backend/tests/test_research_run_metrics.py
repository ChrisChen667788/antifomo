from __future__ import annotations

from datetime import datetime, timezone

import pytest

from app.schemas.research import ResearchJobCreateRequest, ResearchReportResponse
from app.services.llm_runtime import LLMRunResult, LLMUsage
from app.services import research_job_store
from app.services.research.run_metrics import (
    CostLedgerEntry,
    ResearchRunMetrics,
    activate_research_run_metrics,
    instrument_llm_service,
)
from app.services.research.workflow_engine import ResearchWorkflowExecution


class _StaticLLM:
    model = "fixture-model"

    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        return '{"ok": true}'


class _BrokenLLM:
    model = "broken-model"

    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        raise RuntimeError("provider unavailable")


class _UsageAwareLLM:
    def run_prompt_result(self, prompt_name: str, variables: dict[str, str]) -> LLMRunResult:
        return LLMRunResult(
            content='{"ok": true}',
            provider="langchain_openai",
            model="gpt-test-2026",
            usage=LLMUsage(
                input_tokens=90,
                output_tokens=10,
                total_tokens=100,
                cached_input_tokens=30,
                source="provider",
            ),
            estimated_cost_usd=0.00042,
            attempts=2,
            metadata={"structured_output_method": "json_mode"},
        )


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


def test_metered_llm_prefers_provider_usage_and_pricing() -> None:
    metrics = ResearchRunMetrics(run_id="run-provider-usage")
    with activate_research_run_metrics(metrics):
        service = instrument_llm_service(_UsageAwareLLM(), role="generation")
        assert service.run_prompt("missing-test-prompt.txt", {}) == '{"ok": true}'
        assert service.last_run_result is not None
        assert service.last_run_result.model == "gpt-test-2026"

    entry = metrics.cost_ledger.snapshot()["entries"][0]
    assert entry["provider"] == "langchain_openai"
    assert entry["model"] == "gpt-test-2026"
    assert entry["input_tokens"] == 90
    assert entry["output_tokens"] == 10
    assert entry["attempts"] == 2
    assert entry["cache_hit"] is True
    assert entry["estimated_cost_usd"] == 0.00042
    assert entry["metadata"]["token_counting"] == "provider"
    assert entry["metadata"]["cached_input_tokens"] == 30


def test_historical_job_report_infers_generation_fallback_from_cost_ledger() -> None:
    report = {
        "source_diagnostics": {},
        "report_readiness": {"status": "ready", "score": 88, "actionable": True},
        "quality_profile": {"overall_score": 72, "status": "usable", "headline": "可交付"},
    }
    metrics = {
        "cost_ledger": {
            "entries": [
                {
                    "operation": "research_report.txt",
                    "provider": "mock",
                    "model": "deterministic-mock",
                    "status": "fallback",
                    "metadata": {"fallback_used": True, "primary_error": "RuntimeError"},
                }
            ]
        }
    }

    enriched = research_job_store._enrich_report_with_generation_metrics(
        report,
        metrics,
        output_language="zh-CN",
    )

    assert enriched is not None
    assert enriched["source_diagnostics"]["generation_fallback_used"] is True
    assert enriched["source_diagnostics"]["generation_model"] == "deterministic-mock"
    assert enriched["report_readiness"]["status"] == "needs_evidence"
    assert enriched["report_readiness"]["score"] == 45
    assert enriched["report_readiness"]["actionable"] is False
    assert enriched["quality_profile"]["overall_score"] == 45


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


def test_research_job_failure_persists_finished_metrics(monkeypatch) -> None:
    updates: list[dict[str, object]] = []

    def fail_workflow(*args, **kwargs):
        raise RuntimeError("fixture failure")

    monkeypatch.setattr(research_job_store, "execute_research_report_workflow", fail_workflow)
    monkeypatch.setattr(
        research_job_store,
        "update_research_job",
        lambda job_id, **changes: updates.append(changes),
    )

    research_job_store._run_research_job(
        "00000000-0000-0000-0000-000000000001",
        ResearchJobCreateRequest(keyword="测试任务", research_mode="fast"),
    )

    final_update = updates[-1]
    assert final_update["status"] == "failed"
    metrics = final_update["metrics_payload"]
    assert isinstance(metrics, dict)
    assert metrics["status"] == "failed"
    assert metrics["finished_at"]


def test_research_job_does_not_mark_an_empty_evidence_report_as_succeeded(monkeypatch) -> None:
    updates: list[dict[str, object]] = []
    report = ResearchReportResponse(
        keyword="通用主题测试",
        report_title="证据缺口",
        executive_summary="当前没有可用证据。",
        consulting_angle="仅用于补证。",
        source_count=0,
        generated_at=datetime.now(timezone.utc),
    )

    def blocked_workflow(*args, **kwargs):
        return ResearchWorkflowExecution(report=report, metrics=kwargs["metrics"])

    monkeypatch.setattr(research_job_store, "execute_research_report_workflow", blocked_workflow)
    monkeypatch.setattr(
        research_job_store,
        "update_research_job",
        lambda job_id, **changes: updates.append(changes),
    )

    research_job_store._run_research_job(
        "00000000-0000-0000-0000-000000000002",
        ResearchJobCreateRequest(keyword="通用主题测试", research_mode="fast"),
    )

    final_update = updates[-1]
    assert final_update["status"] == "needs_evidence"
    assert final_update["stage_key"] == "needs_evidence"
    assert "正式研报未生成" in str(final_update["message"])
