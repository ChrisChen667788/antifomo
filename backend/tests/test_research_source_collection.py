from __future__ import annotations

from app.services.research.source_collection import collect_public_search_hits
from app.services.research.web_search import SearchHit


def _hit(url: str, query: str) -> SearchHit:
    return SearchHit(
        title=query,
        url=url,
        snippet=query,
        search_query=query,
    )


def test_public_search_does_not_stop_before_priority_official_queries() -> None:
    calls: list[str] = []
    query_plan = [
        "长三角 文旅 文博 人工智能",
        "长三角 景区 博物馆 数字化 招标 预算",
        "site:mct.gov.cn 文旅 数字化 人工智能",
        "site:gov.cn 文旅 文博 人工智能 试点 规划",
        "site:ccgp.gov.cn 景区 博物馆 导览 招标",
        "不会执行的扩展查询",
    ]

    def search(query: str, **_kwargs) -> list[SearchHit]:
        calls.append(query)
        return [_hit(f"https://example.com/{len(calls)}", query)]

    result = collect_public_search_hits(
        search_hits=[_hit("https://example.com/seed", "seed")],
        query_plan=query_plan,
        runtime={
            "query_limit": 6,
            "enough_hit_threshold": 2,
            "search_timeout_seconds": 5,
            "search_result_limit": 5,
            "search_stability_min_unique_domains": 1,
        },
        search_public_web=search,
        dedupe_hits=lambda hits: list({hit.url: hit for hit in hits}.values()),
    )

    assert calls == query_plan[:5]
    assert len(result.search_hits) == 6


def test_public_search_retries_low_result_official_query_when_stability_is_weak() -> None:
    calls: list[str] = []
    official_query = "site:gov.cn 长三角 文旅 人工智能"
    broad_query = "长三角 文旅 人工智能"

    def search(query: str, **_kwargs) -> list[SearchHit]:
        calls.append(query)
        if query == official_query and calls.count(query) == 1:
            return []
        if query == official_query:
            return [
                _hit("https://www.mct.gov.cn/a", query),
                _hit("https://whhlyt.zj.gov.cn/b", query),
            ]
        return [_hit("https://culture.example.com/c", query)]

    result = collect_public_search_hits(
        search_hits=[],
        query_plan=[broad_query, official_query],
        runtime={
            "query_limit": 2,
            "enough_hit_threshold": 4,
            "search_timeout_seconds": 5,
            "search_result_limit": 6,
            "search_stability_min_hits": 4,
            "search_stability_min_unique_domains": 3,
            "search_empty_retry_limit": 2,
        },
        search_public_web=search,
        dedupe_hits=lambda hits: list({hit.url: hit for hit in hits}.values()),
    )

    assert calls == [broad_query, official_query, official_query, broad_query]
    assert result.query_count == 2
    assert result.retry_count == 2
    assert result.zero_result_query_count == 1
    assert result.unique_domain_count == 3
    assert len(result.search_hits) == 3
