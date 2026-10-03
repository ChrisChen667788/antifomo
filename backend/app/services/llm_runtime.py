from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import math
from typing import Literal

from pydantic import BaseModel

from app.services.llm_parser import (
    InsightResult,
    ResearchReportResult,
    ResearchStrategyRefinementResult,
    ResearchStrategyScopePlanResult,
    ScoreResult,
    SessionSummaryResult,
    SummarizeResult,
    TagsResult,
)
from app.services.prompt_loader import load_prompt, render_prompt


TokenCountingSource = Literal["provider", "estimated", "unavailable"]


@dataclass(frozen=True, slots=True)
class LLMUsage:
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0
    cache_creation_input_tokens: int = 0
    source: TokenCountingSource = "unavailable"


@dataclass(frozen=True, slots=True)
class ModelPricing:
    input_cost_per_million: float | None = None
    output_cost_per_million: float | None = None
    cached_input_cost_per_million: float | None = None

    @property
    def configured(self) -> bool:
        return self.input_cost_per_million is not None and self.output_cost_per_million is not None

    def estimate_cost_usd(self, usage: LLMUsage) -> float | None:
        if not self.configured:
            return None
        cached_tokens = max(0, min(usage.input_tokens, usage.cached_input_tokens))
        regular_input_tokens = usage.input_tokens
        input_cost = float(self.input_cost_per_million or 0.0)
        if self.cached_input_cost_per_million is not None:
            regular_input_tokens -= cached_tokens
            cached_cost = cached_tokens * float(self.cached_input_cost_per_million) / 1_000_000
        else:
            cached_cost = 0.0
        total = (
            regular_input_tokens * input_cost / 1_000_000
            + cached_cost
            + usage.output_tokens * float(self.output_cost_per_million or 0.0) / 1_000_000
        )
        return round(total, 10)


@dataclass(frozen=True, slots=True)
class LLMRunResult:
    content: str
    provider: str
    model: str
    usage: LLMUsage = field(default_factory=LLMUsage)
    estimated_cost_usd: float | None = None
    status: str = "succeeded"
    attempts: int = 1
    response_id: str = ""
    finish_reason: str = ""
    metadata: dict[str, object] = field(default_factory=dict)


PROMPT_RESULT_SCHEMAS: dict[str, type[BaseModel]] = {
    "summarize.txt": SummarizeResult,
    "tags.txt": TagsResult,
    "score.txt": ScoreResult,
    "session_summary.txt": SessionSummaryResult,
    "interpret.txt": InsightResult,
    "research_report.txt": ResearchReportResult,
    "research_report_outline.txt": ResearchStrategyRefinementResult,
    "research_strategy_refine.txt": ResearchStrategyRefinementResult,
    "research_strategy_scope.txt": ResearchStrategyScopePlanResult,
}


def schema_for_prompt(prompt_name: str) -> type[BaseModel] | None:
    return PROMPT_RESULT_SCHEMAS.get(prompt_name)


def serialize_llm_run_result(
    result: LLMRunResult,
    *,
    prompt_name: str,
    parse_degraded: bool = False,
    prompt_variables: dict[str, str] | None = None,
) -> dict[str, object]:
    schema = schema_for_prompt(prompt_name)
    schema_payload = schema.model_json_schema() if schema is not None else {}
    schema_json = json.dumps(schema_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    runtime_variables = {
        key: value
        for key, value in dict(prompt_variables or {}).items()
        if not key.startswith("__")
    }
    prompt_template = load_prompt(prompt_name)
    rendered_prompt = render_prompt(prompt_name, runtime_variables)
    return {
        "prompt_name": prompt_name,
        "prompt_template_sha256": hashlib.sha256(prompt_template.encode("utf-8")).hexdigest(),
        "prompt_sha256": hashlib.sha256(rendered_prompt.encode("utf-8")).hexdigest(),
        "prompt_schema_sha256": hashlib.sha256(schema_json.encode("utf-8")).hexdigest(),
        "output_sha256": hashlib.sha256(result.content.encode("utf-8")).hexdigest(),
        "provider": result.provider,
        "model": result.model,
        "status": result.status,
        "attempts": result.attempts,
        "response_id": result.response_id,
        "finish_reason": result.finish_reason,
        "parse_status": "fallback" if parse_degraded else "valid",
        "usage": {
            "input_tokens": result.usage.input_tokens,
            "output_tokens": result.usage.output_tokens,
            "total_tokens": result.usage.total_tokens,
            "cached_input_tokens": result.usage.cached_input_tokens,
            "cache_creation_input_tokens": result.usage.cache_creation_input_tokens,
            "source": result.usage.source,
        },
        "estimated_cost_usd": result.estimated_cost_usd,
        "metadata": dict(result.metadata),
    }


def serialize_llm_failure(
    error: Exception,
    *,
    prompt_name: str,
    prompt_variables: dict[str, str],
    provider: str = "unknown",
    model: str = "unknown",
) -> dict[str, object]:
    """Create a non-secret failure receipt before a stage re-raises."""

    return serialize_llm_run_result(
        LLMRunResult(
            content=f"failure:{type(error).__name__}",
            provider=provider or "unknown",
            model=model or "unknown",
            status="failed",
            attempts=1,
            metadata={"error_type": type(error).__name__},
        ),
        prompt_name=prompt_name,
        prompt_variables=prompt_variables,
    )


def estimate_tokens(value: str) -> int:
    if not value:
        return 0
    return max(1, math.ceil(len(value) / 4))


def estimated_usage(prompt: str, output: str) -> LLMUsage:
    input_tokens = estimate_tokens(prompt)
    output_tokens = estimate_tokens(output)
    return LLMUsage(
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=input_tokens + output_tokens,
        source="estimated",
    )
