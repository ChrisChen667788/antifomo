from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from urllib import parse

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
    query_count: int = 0
    retry_count: int = 0
    zero_result_query_count: int = 0
    unique_domain_count: int = 0


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
    stability_min_hit_count = int(runtime.get("search_stability_min_hits", min(enough_hit_threshold, 8)))
    stability_min_unique_domains = int(runtime.get("search_stability_min_unique_domains", 5))
    empty_retry_limit = max(0, int(runtime.get("search_empty_retry_limit", 0)))
    official_query_indexes = [
        index
        for index, query in enumerate(effective_query_plan)
        if query.strip().lower().startswith("site:")
    ][:3]
    minimum_last_query_index = official_query_indexes[-1] if official_query_indexes else 0
    empty_queries: list[str] = []
    low_result_queries: list[str] = []
    minimum_per_query_hits = min(3, max(1, int(runtime["search_result_limit"]) // 2))
    query_count = 0
    for index, query in enumerate(effective_query_plan):
        query_count += 1
        try:
            results = search_public_web(
                query,
                timeout_seconds=int(runtime["search_timeout_seconds"]),
                limit=int(runtime["search_result_limit"]),
            )
        except Exception:
            results = []
        if not results:
            empty_queries.append(query)
        if len(results) < minimum_per_query_hits:
            low_result_queries.append(query)
        collected_hits.extend(results)
        deduped_hits = dedupe_hits(collected_hits)
        unique_domains = {
            domain.removeprefix("www.")
            for hit in deduped_hits
            if (domain := (parse.urlparse(hit.url).hostname or "").lower())
        }
        if (
            index >= minimum_last_query_index
            and len(deduped_hits) >= max(enough_hit_threshold, stability_min_hit_count)
            and len(unique_domains) >= stability_min_unique_domains
        ):
            break
    deduped_hits = dedupe_hits(collected_hits)
    unique_domains = {
        domain.removeprefix("www.")
        for hit in deduped_hits
        if (domain := (parse.urlparse(hit.url).hostname or "").lower())
    }
    retry_count = 0
    if (
        empty_retry_limit
        and low_result_queries
        and (
            len(deduped_hits) < stability_min_hit_count
            or len(unique_domains) < stability_min_unique_domains
        )
    ):
        priority_retry_queries = sorted(
            low_result_queries,
            key=lambda value: (not value.strip().lower().startswith("site:"), low_result_queries.index(value)),
        )
        for query in priority_retry_queries[:empty_retry_limit]:
            retry_count += 1
            try:
                collected_hits.extend(
                    search_public_web(
                        query,
                        timeout_seconds=int(runtime["search_timeout_seconds"]),
                        limit=int(runtime["search_result_limit"]),
                    )
                )
            except Exception:
                continue
    final_hits = dedupe_hits(collected_hits)
    final_unique_domains = {
        domain.removeprefix("www.")
        for hit in final_hits
        if (domain := (parse.urlparse(hit.url).hostname or "").lower())
    }
    return PublicSearchCollection(
        search_hits=final_hits,
        effective_query_plan=effective_query_plan,
        query_count=query_count,
        retry_count=retry_count,
        zero_result_query_count=len(empty_queries),
        unique_domain_count=len(final_unique_domains),
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
