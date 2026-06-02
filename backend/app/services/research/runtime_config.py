from __future__ import annotations

from collections.abc import Callable

from app.core.config import get_settings
from app.schemas.research import ResearchReportRequest


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
                "url_timeout_seconds": 14,
                "llm_timeout_seconds": 24,
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
            "url_timeout_seconds": min(settings.url_fetch_timeout_seconds, 22),
            "llm_timeout_seconds": max(settings.research_llm_timeout_seconds, 45),
            "expansion_min_sources": min(effective_max_sources, 6),
            "expansion_min_dimensions": 5,
            "enable_expansion": True,
            "corrective_query_limit": 6,
        },
        payload,
        runtime_consumer_effective_config=runtime_consumer_effective_config,
        safe_int=safe_int,
    )
