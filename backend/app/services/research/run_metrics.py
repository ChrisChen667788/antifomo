from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
from threading import RLock
import time
from typing import Any
from uuid import uuid4

from app.services.prompt_loader import render_prompt


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True, slots=True)
class CostLedgerEntry:
    category: str
    operation: str
    provider: str
    model: str
    status: str
    latency_ms: int
    attempts: int = 1
    input_tokens: int = 0
    output_tokens: int = 0
    estimated_cost_usd: float | None = None
    cache_hit: bool = False
    metadata: dict[str, object] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


class CostLedger:
    """Thread-safe per-run ledger for model and external-service costs."""

    def __init__(self) -> None:
        self._entries: list[CostLedgerEntry] = []
        self._lock = RLock()

    def record(self, entry: CostLedgerEntry) -> None:
        with self._lock:
            self._entries.append(entry)

    @property
    def entries(self) -> tuple[CostLedgerEntry, ...]:
        with self._lock:
            return tuple(self._entries)

    def snapshot(self) -> dict[str, object]:
        entries = self.entries
        priced_entries = [entry for entry in entries if entry.estimated_cost_usd is not None]
        return {
            "entry_count": len(entries),
            "model_call_count": sum(1 for entry in entries if entry.category == "llm"),
            "failed_call_count": sum(1 for entry in entries if entry.status == "failed"),
            "cache_hit_count": sum(1 for entry in entries if entry.cache_hit),
            "input_tokens": sum(entry.input_tokens for entry in entries),
            "output_tokens": sum(entry.output_tokens for entry in entries),
            "total_tokens": sum(entry.total_tokens for entry in entries),
            "estimated_cost_usd": (
                round(sum(entry.estimated_cost_usd or 0.0 for entry in priced_entries), 8)
                if priced_entries
                else None
            ),
            "priced_entry_count": len(priced_entries),
            "unpriced_entry_count": len(entries) - len(priced_entries),
            "entries": [
                {
                    "category": entry.category,
                    "operation": entry.operation,
                    "provider": entry.provider,
                    "model": entry.model,
                    "status": entry.status,
                    "latency_ms": entry.latency_ms,
                    "attempts": entry.attempts,
                    "input_tokens": entry.input_tokens,
                    "output_tokens": entry.output_tokens,
                    "total_tokens": entry.total_tokens,
                    "estimated_cost_usd": entry.estimated_cost_usd,
                    "cache_hit": entry.cache_hit,
                    "metadata": dict(entry.metadata),
                }
                for entry in entries
            ],
        }


@dataclass(slots=True)
class ResearchNodeMetric:
    name: str
    attempts: int = 0
    succeeded: int = 0
    failed: int = 0
    total_latency_ms: int = 0
    max_latency_ms: int = 0
    last_error: str = ""

    def record(self, *, latency_ms: int, succeeded: bool, error: str = "") -> None:
        self.attempts += 1
        self.total_latency_ms += max(0, latency_ms)
        self.max_latency_ms = max(self.max_latency_ms, max(0, latency_ms))
        if succeeded:
            self.succeeded += 1
        else:
            self.failed += 1
            self.last_error = error[:500]


@dataclass(slots=True)
class ResearchRunMetrics:
    workflow_engine: str = "deterministic"
    run_id: str = field(default_factory=lambda: str(uuid4()))
    started_at: datetime = field(default_factory=_utc_now)
    finished_at: datetime | None = None
    status: str = "running"
    counters: dict[str, int] = field(default_factory=dict)
    gauges: dict[str, float] = field(default_factory=dict)
    nodes: dict[str, ResearchNodeMetric] = field(default_factory=dict)
    cost_ledger: CostLedger = field(default_factory=CostLedger)
    _active_stage: str = field(default="", init=False, repr=False)
    _active_stage_started: float = field(default=0.0, init=False, repr=False)
    _lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def increment(self, key: str, amount: int = 1) -> None:
        with self._lock:
            self.counters[key] = self.counters.get(key, 0) + amount

    def set_gauge(self, key: str, value: float) -> None:
        with self._lock:
            self.gauges[key] = float(value)

    def record_node(self, name: str, *, latency_ms: int, succeeded: bool, error: str = "") -> None:
        with self._lock:
            metric = self.nodes.setdefault(name, ResearchNodeMetric(name=name))
            metric.record(latency_ms=latency_ms, succeeded=succeeded, error=error)

    @contextmanager
    def measure_node(self, name: str) -> Iterator[None]:
        started = time.perf_counter()
        try:
            yield
        except Exception as exc:
            self.record_node(
                name,
                latency_ms=round((time.perf_counter() - started) * 1000),
                succeeded=False,
                error=exc.__class__.__name__,
            )
            raise
        else:
            self.record_node(
                name,
                latency_ms=round((time.perf_counter() - started) * 1000),
                succeeded=True,
            )

    def observe_progress(self, stage_key: str, progress_percent: int) -> None:
        now = time.perf_counter()
        with self._lock:
            if self._active_stage and self._active_stage_started:
                elapsed_ms = round((now - self._active_stage_started) * 1000)
                self.nodes.setdefault(self._active_stage, ResearchNodeMetric(name=self._active_stage)).record(
                    latency_ms=elapsed_ms,
                    succeeded=True,
                )
            self._active_stage = f"stage.{stage_key}"
            self._active_stage_started = now
            self.gauges["progress_percent"] = float(max(0, min(100, progress_percent)))

    def finish(self, status: str) -> None:
        now = time.perf_counter()
        with self._lock:
            if self._active_stage and self._active_stage_started:
                elapsed_ms = round((now - self._active_stage_started) * 1000)
                self.nodes.setdefault(self._active_stage, ResearchNodeMetric(name=self._active_stage)).record(
                    latency_ms=elapsed_ms,
                    succeeded=status == "succeeded",
                    error="workflow failed" if status != "succeeded" else "",
                )
            self._active_stage = ""
            self._active_stage_started = 0.0
            self.status = status
            self.finished_at = _utc_now()
            self.gauges["duration_ms"] = float(
                max(0, round((self.finished_at - self.started_at).total_seconds() * 1000))
            )

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            nodes = {
                name: {
                    "attempts": metric.attempts,
                    "succeeded": metric.succeeded,
                    "failed": metric.failed,
                    "total_latency_ms": metric.total_latency_ms,
                    "max_latency_ms": metric.max_latency_ms,
                    "last_error": metric.last_error,
                }
                for name, metric in sorted(self.nodes.items())
            }
            return {
                "run_id": self.run_id,
                "workflow_engine": self.workflow_engine,
                "status": self.status,
                "started_at": self.started_at.isoformat(),
                "finished_at": self.finished_at.isoformat() if self.finished_at else None,
                "counters": dict(sorted(self.counters.items())),
                "gauges": dict(sorted(self.gauges.items())),
                "nodes": nodes,
                "cost_ledger": self.cost_ledger.snapshot(),
            }


_ACTIVE_RESEARCH_RUN_METRICS: ContextVar[ResearchRunMetrics | None] = ContextVar(
    "active_research_run_metrics",
    default=None,
)


@contextmanager
def activate_research_run_metrics(metrics: ResearchRunMetrics) -> Iterator[ResearchRunMetrics]:
    token: Token[ResearchRunMetrics | None] = _ACTIVE_RESEARCH_RUN_METRICS.set(metrics)
    try:
        yield metrics
    finally:
        _ACTIVE_RESEARCH_RUN_METRICS.reset(token)


def active_research_run_metrics() -> ResearchRunMetrics | None:
    return _ACTIVE_RESEARCH_RUN_METRICS.get()


def _estimate_tokens(value: str) -> int:
    if not value:
        return 0
    return max(1, math.ceil(len(value) / 4))


def _service_metadata(service: Any) -> tuple[str, str]:
    provider = service.__class__.__name__
    model = str(getattr(service, "model", "") or "")
    primary = getattr(service, "primary", None)
    if primary is not None:
        provider = primary.__class__.__name__
        model = str(getattr(primary, "model", "") or model)
    return provider, model or "unspecified"


class MeteredLLMService:
    def __init__(self, service: Any, metrics: ResearchRunMetrics, *, role: str) -> None:
        self._service = service
        self._metrics = metrics
        self._role = role

    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        started = time.perf_counter()
        provider, model = _service_metadata(self._service)
        try:
            rendered = render_prompt(
                prompt_name,
                {key: value for key, value in variables.items() if not key.startswith("__")},
            )
        except Exception:
            rendered = "\n".join(str(value) for key, value in variables.items() if not key.startswith("__"))
        try:
            output = self._service.run_prompt(prompt_name, variables)
        except Exception:
            self._metrics.cost_ledger.record(
                CostLedgerEntry(
                    category="llm",
                    operation=prompt_name,
                    provider=provider,
                    model=model,
                    status="failed",
                    latency_ms=round((time.perf_counter() - started) * 1000),
                    input_tokens=_estimate_tokens(rendered),
                    metadata={
                        "role": self._role,
                        "token_counting": "estimated",
                        "attempt_counting": "outer_call",
                    },
                )
            )
            raise
        self._metrics.cost_ledger.record(
            CostLedgerEntry(
                category="llm",
                operation=prompt_name,
                provider=provider,
                model=model,
                status="succeeded",
                latency_ms=round((time.perf_counter() - started) * 1000),
                input_tokens=_estimate_tokens(rendered),
                output_tokens=_estimate_tokens(output),
                metadata={
                    "role": self._role,
                    "token_counting": "estimated",
                    "attempt_counting": "outer_call",
                },
            )
        )
        return output


def instrument_llm_service(service: Any | None, *, role: str) -> Any | None:
    metrics = active_research_run_metrics()
    if service is None or metrics is None:
        return service
    if isinstance(service, MeteredLLMService) and service._metrics is metrics:
        return service
    return MeteredLLMService(service, metrics, role=role)
