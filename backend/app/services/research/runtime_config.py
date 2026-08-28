from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.core.config import get_settings
from app.schemas.research import ResearchReportRequest
from app.services.content_extractor import normalize_text


def apply_runtime_query_config(
    runtime: dict[str, int | bool],
    payload: ResearchReportRequest,
    *,
    runtime_consumer_effective_config: Callable[[ResearchReportRequest, str], dict[str, object]],
    safe_int: Callable[..., int],
) -> dict[str, int | bool]:
    query_config = runtime_consumer_effective_config(payload, "query_generation")
    if not bool(query_config.get("enabled") or query_config.get("query_recovery_enabled")):
        return runtime
    corrective_limit = safe_int(query_config.get("corrective_query_limit"), 4, minimum=1, maximum=12)
    next_runtime = dict(runtime)
    next_runtime["runtime_query_recovery_enabled"] = True
    next_runtime["corrective_query_limit"] = corrective_limit
    if bool(query_config.get("public_expansion_on_watch")):
        next_runtime["enable_expansion"] = True
        next_runtime["expanded_query_limit"] = max(int(next_runtime.get("expanded_query_limit", 3)), corrective_limit)
    return next_runtime


def build_research_runtime(
    payload: ResearchReportRequest,
    *,
    resolve_research_mode: Callable[[ResearchReportRequest], str],
    runtime_consumer_effective_config: Callable[[ResearchReportRequest, str], dict[str, object]],
    safe_int: Callable[..., int],
) -> dict[str, int | bool]:
    mode = resolve_research_mode(payload)
    if mode == "fast":
        effective_max_sources = min(max(6, int(payload.max_sources)), 8)
        return apply_runtime_query_config(
            {
                "mode": 0,
                "query_limit": 4,
                "expanded_query_limit": 3,
                "search_result_limit": 6,
                "effective_max_sources": effective_max_sources,
                "adapter_per_source_limit": 2,
                "expanded_adapter_per_source_limit": 2,
                "enough_hit_threshold": max(effective_max_sources + 2, 8),
                "expanded_selected_limit": min(10, effective_max_sources + 2),
                "search_timeout_seconds": 9,
                "search_stability_min_hits": 6,
                "search_stability_min_unique_domains": 3,
                "search_empty_retry_limit": 1,
                "url_timeout_seconds": 14,
                "llm_timeout_seconds": 24,
                "llm_max_output_tokens": 3000,
                "expansion_min_sources": 4,
                "expansion_min_dimensions": 3,
                "enable_expansion": True,
                "corrective_query_limit": 4,
            },
            payload,
            runtime_consumer_effective_config=runtime_consumer_effective_config,
            safe_int=safe_int,
        )
    effective_max_sources = min(max(8, int(payload.max_sources)), 18)
    settings = get_settings()
    return apply_runtime_query_config(
        {
            "mode": 1,
            "query_limit": min(12, max(6, settings.research_search_query_limit)),
            "expanded_query_limit": 8,
            "search_result_limit": min(12, max(8, settings.research_max_search_results)),
            "effective_max_sources": effective_max_sources,
            "adapter_per_source_limit": max(3, min(6, effective_max_sources // 2 or 1)),
            "expanded_adapter_per_source_limit": max(2, min(4, effective_max_sources // 2 or 1)),
            "enough_hit_threshold": max(effective_max_sources * 2, effective_max_sources + 2),
            "expanded_selected_limit": min(14, max(effective_max_sources + 2, effective_max_sources)),
            "search_timeout_seconds": min(settings.research_search_timeout_seconds, 15),
            "search_stability_min_hits": 12,
            "search_stability_min_unique_domains": 5,
            "search_empty_retry_limit": 3,
            "url_timeout_seconds": min(settings.url_fetch_timeout_seconds, 22),
            "llm_timeout_seconds": max(settings.research_llm_timeout_seconds, 45),
            "llm_max_output_tokens": max(3000, settings.research_llm_max_output_tokens),
            "expansion_min_sources": min(effective_max_sources, 6),
            "expansion_min_dimensions": 5,
            "enable_expansion": True,
            "corrective_query_limit": 6,
        },
        payload,
        runtime_consumer_effective_config=runtime_consumer_effective_config,
        safe_int=safe_int,
    )


def report_runtime_strategy_payload(payload: ResearchReportRequest) -> dict[str, Any]:
    data = getattr(payload, "runtime_strategy_config", {}) or {}
    return data if isinstance(data, dict) else {}


def runtime_consumer_payload(payload: ResearchReportRequest, consumer: str) -> dict[str, Any]:
    data = report_runtime_strategy_payload(payload).get(consumer)
    return data if isinstance(data, dict) else {}


def runtime_consumer_effective_config(payload: ResearchReportRequest, consumer: str) -> dict[str, Any]:
    data = runtime_consumer_payload(payload, consumer)
    effective = data.get("effective_config")
    return effective if isinstance(effective, dict) else {}


def runtime_consumer_list(
    payload: ResearchReportRequest,
    consumer: str,
    key: str,
    *,
    dedupe_strings: Callable[..., list[str]],
) -> list[str]:
    data = runtime_consumer_payload(payload, consumer)
    values = data.get(key)
    return dedupe_strings(values if isinstance(values, list) else [], 8)


def runtime_consumer_status(payload: ResearchReportRequest, consumer: str) -> str:
    return normalize_text(str(runtime_consumer_payload(payload, consumer).get("status") or ""))


def runtime_consumer_warnings(
    payload: ResearchReportRequest,
    consumer: str,
    *,
    dedupe_strings: Callable[..., list[str]],
) -> list[str]:
    return runtime_consumer_list(payload, consumer, "warnings", dedupe_strings=dedupe_strings)


def build_runtime_strategy_scope_hints(
    payload: ResearchReportRequest,
    *,
    dedupe_strings: Callable[..., list[str]],
    safe_int: Callable[..., int],
) -> dict[str, object]:
    query_config = runtime_consumer_effective_config(payload, "query_generation")
    reranker_config = runtime_consumer_effective_config(payload, "source_reranker")
    query_enabled = bool(query_config.get("enabled") or query_config.get("query_recovery_enabled"))
    reranker_enabled = bool(reranker_config.get("enabled"))
    applied_lanes = dedupe_strings(
        [
            *runtime_consumer_list(payload, "query_generation", "applied_lanes", dedupe_strings=dedupe_strings),
            *runtime_consumer_list(payload, "source_reranker", "applied_lanes", dedupe_strings=dedupe_strings),
        ],
        8,
    )
    fallback_lanes = dedupe_strings(
        [
            *runtime_consumer_list(payload, "query_generation", "fallback_lanes", dedupe_strings=dedupe_strings),
            *runtime_consumer_list(payload, "source_reranker", "fallback_lanes", dedupe_strings=dedupe_strings),
        ],
        8,
    )
    warnings = dedupe_strings(
        [
            *runtime_consumer_warnings(payload, "query_generation", dedupe_strings=dedupe_strings),
            *runtime_consumer_warnings(payload, "source_reranker", dedupe_strings=dedupe_strings),
        ],
        8,
    )
    statuses = [
        runtime_consumer_status(payload, "query_generation"),
        runtime_consumer_status(payload, "source_reranker"),
    ]
    runtime_status = "fallback"
    if "degraded" in statuses:
        runtime_status = "degraded"
    elif "ready" in statuses:
        runtime_status = "ready"

    reranker_adapter = normalize_text(str(reranker_config.get("reranker_adapter") or ""))
    reranker_backend = "local"
    if reranker_adapter == "sentence_transformers_cross_encoder":
        reranker_backend = "sentence_transformers"
    elif reranker_adapter and reranker_adapter != "local_rrf":
        reranker_backend = "auto"

    hints: dict[str, object] = {
        "runtime_strategy_status": runtime_status,
        "runtime_strategy_applied_lanes": applied_lanes,
        "runtime_strategy_fallback_lanes": fallback_lanes,
        "runtime_strategy_warnings": warnings,
        "runtime_query_recovery_enabled": query_enabled,
        "runtime_source_reranker_enabled": reranker_enabled,
    }
    if query_enabled:
        hints["runtime_corrective_query_limit"] = safe_int(
            query_config.get("corrective_query_limit"),
            4,
            minimum=1,
            maximum=12,
        )
        hints["runtime_public_expansion_on_watch"] = bool(query_config.get("public_expansion_on_watch"))
    if reranker_enabled:
        hints.update(
            {
                "enable_cross_encoder_rerank": reranker_adapter != "local_rrf",
                "cross_encoder_rerank": reranker_adapter != "local_rrf",
                "runtime_reranker_adapter": reranker_adapter or "local_rrf",
                "runtime_reranker_backend": reranker_backend,
                "runtime_reranker_top_k": safe_int(reranker_config.get("recall_at_k"), 5, minimum=3, maximum=20),
                "runtime_reranker_fallback_adapter": normalize_text(
                    str(reranker_config.get("fallback_adapter") or "local_rrf")
                ),
                "runtime_official_source_bias": bool(reranker_config.get("official_source_bias", True)),
            }
        )
    return hints
