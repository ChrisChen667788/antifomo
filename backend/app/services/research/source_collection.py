from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.services.research.source_documents import SourceDocument
from app.services.research.web_search import SearchHit


@dataclass(frozen=True, slots=True)
class AdapterHitCollection:
    adapter_settings: Any
    adapter_query_plan: list[str]
    search_hits: list[SearchHit]


@dataclass(frozen=True, slots=True)
class PublicSearchCollection:
    search_hits: list[SearchHit]
    effective_query_plan: list[str]


@dataclass(frozen=True, slots=True)
class InitialSourceExtraction:
    sources: list[SourceDocument]
    filtered_old_source_count: int


def collect_adapter_hits(
    *,
    keyword: str,
    research_focus: str | None,
    runtime: dict[str, int | bool],
    collect_enabled_source_hits: Callable[..., tuple[Any, list[SearchHit]]],
) -> AdapterHitCollection:
    adapter_settings, adapter_hits = collect_enabled_source_hits(
        keyword,
        research_focus,
        timeout_seconds=int(runtime["search_timeout_seconds"]),
        per_source_limit=int(runtime["adapter_per_source_limit"]),
    )
    return AdapterHitCollection(
        adapter_settings=adapter_settings,
        adapter_query_plan=[f"source:{label}" for label in adapter_settings.enabled_labels()],
        search_hits=list(adapter_hits),
    )


def collect_public_search_hits(
    *,
    search_hits: list[SearchHit],
    query_plan: list[str],
    runtime: dict[str, int | bool],
    search_public_web: Callable[..., list[SearchHit]],
    dedupe_hits: Callable[[list[SearchHit]], list[SearchHit]],
) -> PublicSearchCollection:
    collected_hits = list(search_hits)
    effective_query_plan = query_plan[: max(1, int(runtime["query_limit"]))]
    enough_hit_threshold = int(runtime["enough_hit_threshold"])
    for query in effective_query_plan:
        try:
            results = search_public_web(
                query,
                timeout_seconds=int(runtime["search_timeout_seconds"]),
                limit=int(runtime["search_result_limit"]),
            )
        except Exception:
            results = []
        collected_hits.extend(results)
        if len(dedupe_hits(collected_hits)) >= enough_hit_threshold:
            break
    return PublicSearchCollection(
        search_hits=collected_hits,
        effective_query_plan=effective_query_plan,
    )


def extract_initial_sources(
    *,
    search_hits: list[SearchHit],
    keyword: str,
    research_focus: str | None,
    scope_hints: dict[str, object],
    runtime: dict[str, int | bool],
    max_sources: int,
    excerpt_chars: int,
    hybrid_rank_hits: Callable[..., list[SearchHit]],
    select_hits_with_source_balance: Callable[..., list[SearchHit]],
    extract_source_document: Callable[..., SourceDocument],
    filter_recent_sources: Callable[[list[SourceDocument]], list[SourceDocument]],
) -> InitialSourceExtraction:
    ranked_hits = [
        hit
        for hit in hybrid_rank_hits(
            search_hits,
            keyword=keyword,
            research_focus=research_focus,
            scope_hints=scope_hints,
        )
    ]
    selected_hits = select_hits_with_source_balance(
        ranked_hits,
        limit=min(int(runtime["effective_max_sources"]), max_sources),
    )
    sources = [
        extract_source_document(
            hit,
            timeout_seconds=int(runtime["url_timeout_seconds"]),
            excerpt_chars=excerpt_chars,
        )
        for hit in selected_hits
    ]
    recent_filter_input_count = len(sources)
    sources = filter_recent_sources(sources)
    return InitialSourceExtraction(
        sources=sources,
        filtered_old_source_count=max(recent_filter_input_count - len(sources), 0),
    )
