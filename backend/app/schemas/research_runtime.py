from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ResearchRunNodeMetricOut(BaseModel):
    attempts: int = 0
    succeeded: int = 0
    failed: int = 0
    total_latency_ms: int = 0
    max_latency_ms: int = 0
    last_error: str = ""


class ResearchRunCostLedgerOut(BaseModel):
    entry_count: int = 0
    model_call_count: int = 0
    failed_call_count: int = 0
    cache_hit_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_cost_usd: float | None = None
    priced_entry_count: int = 0
    unpriced_entry_count: int = 0
    entries: list[dict[str, object]] = Field(default_factory=list)


class ResearchRunMetricsOut(BaseModel):
    run_id: str = ""
    workflow_engine: str = "deterministic"
    status: str = "pending"
    started_at: datetime | None = None
    finished_at: datetime | None = None
    counters: dict[str, int] = Field(default_factory=dict)
    gauges: dict[str, float] = Field(default_factory=dict)
    nodes: dict[str, ResearchRunNodeMetricOut] = Field(default_factory=dict)
    cost_ledger: ResearchRunCostLedgerOut = Field(default_factory=ResearchRunCostLedgerOut)
    billing: dict[str, object] = Field(default_factory=dict)
