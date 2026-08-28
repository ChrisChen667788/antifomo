from __future__ import annotations

from app.services.research import web_search


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *_args) -> None:
        return None

    def read(self) -> bytes:
        return self.payload


def test_bing_rss_search_parses_structured_results(monkeypatch) -> None:
    payload = b"""<?xml version="1.0" encoding="utf-8"?>
    <rss><channel>
      <item><title>Culture tourism AI procurement</title><link>https://example.gov.cn/a</link><description>Official &amp; current</description></item>
      <item><title>Museum digital guide</title><link>https://museum.example/b</link><description>Tourism project notice</description></item>
    </channel></rss>"""
    monkeypatch.setattr(web_search, "_safe_urlopen", lambda *_args, **_kwargs: _Response(payload))

    hits = web_search._search_bing_rss("Culture tourism procurement", timeout_seconds=5, limit=5)

    assert [hit.url for hit in hits] == ["https://example.gov.cn/a", "https://museum.example/b"]
    assert hits[0].snippet == "Official & current"
    assert all(hit.source_hint == "bing_rss" for hit in hits)


def test_rss_search_requires_two_topic_markers_for_multi_axis_queries() -> None:
    generic = web_search.SearchHit(
        "国家政务服务平台",
        "https://example.gov.cn/",
        "政务服务入口",
        "上海 数字政府 人工智能 政务服务",
    )
    topical = web_search.SearchHit(
        "上海数字政府人工智能行动方案",
        "https://example.gov.cn/policy/ai",
        "政务服务智能化应用",
        "上海 数字政府 人工智能 政务服务",
    )

    assert web_search._rss_hit_matches_query(generic, generic.search_query) is False
    assert web_search._rss_hit_matches_query(topical, topical.search_query) is True


def test_so360_search_uses_direct_result_urls(monkeypatch) -> None:
    payload = """
    <ul class="result"><li class="res-list">
      <h3 class="res-title"><a href="https://www.so.com/link?m=redirect" data-mdurl="https://www.ccgp.gov.cn/project/1">
        上海<em>博物馆数字化</em>项目公开招标公告
      </a></h3>
      <span class="res-list-summary">采购人发布数字化导览项目预算与招标安排。</span>
    </li></ul>
    """.encode()
    monkeypatch.setattr(web_search, "_safe_urlopen", lambda *_args, **_kwargs: _Response(payload))

    hits = web_search._search_so360("上海 博物馆 数字化 招标", timeout_seconds=5, limit=5)

    assert len(hits) == 1
    assert hits[0].url == "https://www.ccgp.gov.cn/project/1"
    assert "采购人" in hits[0].snippet
    assert hits[0].source_hint == "so360"


def test_brave_search_parses_direct_result_urls_and_snippets(monkeypatch) -> None:
    payload = """
    <div class="result-wrapper svelte-test"><div class="result-content">
      <a href="https://www.mct.gov.cn/article/1.htm" target="_self" class="result-link">
        <div class="site-name-wrapper">文化和旅游部</div>
        <div class="title search-snippet-title line-clamp-1" title="文旅大模型技术创新中心简介">
          文旅大模型技术创新中心简介
        </div>
      </a>
      <div class="generic-snippet"><div class="content desktop-default-regular line-clamp-dynamic">
        <span>July 14, 2026 -</span> 面向公共文化服务建设文旅人工智能能力。
      </div></div>
    </div></div>
    """.encode()
    monkeypatch.setattr(web_search, "_safe_urlopen", lambda *_args, **_kwargs: _Response(payload))

    hits = web_search._search_brave("site:mct.gov.cn 文旅 人工智能", timeout_seconds=5, limit=5)

    assert len(hits) == 1
    assert hits[0].url == "https://www.mct.gov.cn/article/1.htm"
    assert hits[0].title == "文旅大模型技术创新中心简介"
    assert "公共文化服务" in hits[0].snippet
    assert hits[0].source_hint == "brave"


def test_yahoo_search_unwraps_original_result_url(monkeypatch) -> None:
    payload = """
    <div class="dd fst algo algo-sr relsrch Sr">
      <div class="compTitle"><a href="https://r.search.yahoo.com/path/RU=https%3A%2F%2Fwww.mct.gov.cn%2Farticle%2F2.htm/RK=2/RS=x">
        <h3 class="title"><span>江苏省印发“人工智能+文化旅游”行动方案</span></h3>
      </a></div>
      <div class="compText"><p class="fc-dustygray fz-14"><span>May 11, 2026 -</span> 江苏推进人工智能与文化旅游融合。</p></div>
    </div>
    """.encode()
    monkeypatch.setattr(web_search, "_safe_urlopen", lambda *_args, **_kwargs: _Response(payload))

    hits = web_search._search_yahoo("site:mct.gov.cn 文旅 人工智能", timeout_seconds=5, limit=5)

    assert len(hits) == 1
    assert hits[0].url == "https://www.mct.gov.cn/article/2.htm"
    assert hits[0].title == "江苏省印发“人工智能+文化旅游”行动方案"
    assert "江苏推进" in hits[0].snippet
    assert hits[0].source_hint == "yahoo"


def test_google_news_search_resolves_original_official_url(monkeypatch) -> None:
    payload = """<?xml version="1.0" encoding="utf-8"?>
    <rss><channel><item>
      <title>文旅大模型技术创新中心简介 - 文化和旅游部</title>
      <link>https://news.google.com/rss/articles/token</link>
      <description>文旅人工智能技术创新与公共文化服务</description>
      <pubDate>Tue, 14 Jul 2026 08:00:00 GMT</pubDate>
      <source url="https://www.mct.gov.cn">中华人民共和国文化和旅游部</source>
    </item></channel></rss>""".encode()
    monkeypatch.setattr(web_search, "_safe_urlopen", lambda *_args, **_kwargs: _Response(payload))
    monkeypatch.setattr(
        web_search,
        "_decode_google_news_url",
        lambda *_args, **_kwargs: "https://www.mct.gov.cn/article/1.htm",
    )

    hits = web_search._search_google_news("site:mct.gov.cn 文旅 人工智能", timeout_seconds=5, limit=5)

    assert len(hits) == 1
    assert hits[0].url == "https://www.mct.gov.cn/article/1.htm"
    assert hits[0].source_hint == "policy"
    assert hits[0].source_label == "中华人民共和国文化和旅游部"


def test_google_news_does_not_mark_unresolved_wrapper_as_official(monkeypatch) -> None:
    payload = """<?xml version="1.0" encoding="utf-8"?>
    <rss><channel><item>
      <title>文旅人工智能行动方案 - 文化和旅游部</title>
      <link>https://news.google.com/rss/articles/unresolved-token</link>
      <description>文化旅游人工智能政策与公共文化服务</description>
      <source url="https://www.mct.gov.cn">中华人民共和国文化和旅游部</source>
    </item></channel></rss>""".encode()
    monkeypatch.setattr(web_search, "_safe_urlopen", lambda *_args, **_kwargs: _Response(payload))
    monkeypatch.setattr(web_search, "_decode_google_news_url", lambda url, *_args, **_kwargs: url)
    monkeypatch.setattr(web_search, "_recover_google_news_direct_url", lambda *_args, **_kwargs: "")

    hits = web_search._search_google_news("文旅 人工智能", timeout_seconds=5, limit=5)

    assert len(hits) == 1
    assert hits[0].url.startswith("https://news.google.com/")
    assert hits[0].source_hint is None


def test_google_news_recovers_a_direct_publisher_url_when_wrapper_decode_is_blocked(monkeypatch) -> None:
    payload = """<?xml version="1.0" encoding="utf-8"?>
    <rss><channel><item>
      <title>上海数字政府人工智能行动方案 - 上海市人民政府</title>
      <link>https://news.google.com/rss/articles/blocked-token</link>
      <description>数字政府人工智能应用、政策规划和数据安全。</description>
      <source url="https://www.sh.gov.cn">上海市人民政府</source>
    </item></channel></rss>""".encode()
    monkeypatch.setattr(web_search, "_safe_urlopen", lambda *_args, **_kwargs: _Response(payload))
    monkeypatch.setattr(web_search, "_decode_google_news_url", lambda url, *_args, **_kwargs: url)
    monkeypatch.setattr(
        web_search,
        "_recover_google_news_direct_url",
        lambda title, source_url, *_args: "https://www.sh.gov.cn/policy/ai.html"
        if "行动方案" in title and source_url == "https://www.sh.gov.cn"
        else "",
    )

    hits = web_search._search_google_news("site:gov.cn 上海 数字政府 人工智能", timeout_seconds=5, limit=5)

    assert hits[0].url == "https://www.sh.gov.cn/policy/ai.html"
    assert hits[0].source_hint == "policy"
    assert hits[0].source_label == "上海市人民政府"


def test_publisher_recovery_requires_a_direct_result_from_the_publisher_domain(monkeypatch) -> None:
    web_search._recover_google_news_direct_url.cache_clear()
    captured_queries: list[str] = []

    def fake_so360(query: str, **_kwargs):
        captured_queries.append(query)
        return [
            web_search.SearchHit("转载", "https://news.example.com/a", "", query),
            web_search.SearchHit("原文", "https://www.njjy.gov.cn/article/1", "", query),
        ]

    monkeypatch.setattr(web_search, "_search_so360", fake_so360)

    resolved = web_search._recover_google_news_direct_url(
        "中国移动大模型产业创新基地落户南京建邺 - njjy.gov.cn",
        "https://www.njjy.gov.cn",
        5,
    )

    assert resolved == "https://www.njjy.gov.cn/article/1"
    assert captured_queries == ["site:njjy.gov.cn 中国移动大模型产业创新基地落户南京建邺"]
    web_search._recover_google_news_direct_url.cache_clear()


def test_public_search_continues_until_results_cover_multiple_domains(monkeypatch) -> None:
    yahoo_hits = [
        web_search.SearchHit(str(index), f"https://same.example.com/{index}", "文旅", "query")
        for index in range(6)
    ]
    brave_hits = [
        web_search.SearchHit("A", "https://first.example.cn/a", "文旅", "query"),
        web_search.SearchHit("B", "https://second.example.cn/b", "文旅", "query"),
    ]
    monkeypatch.setattr(web_search, "_search_yahoo", lambda *_args, **_kwargs: yahoo_hits)
    monkeypatch.setattr(web_search, "_search_brave", lambda *_args, **_kwargs: brave_hits)
    monkeypatch.setattr(
        web_search,
        "_search_so360",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected")),
    )

    hits = web_search._search_public_web("长三角 文旅 人工智能", timeout_seconds=5, limit=8)

    assert len(hits) == 8
    assert {web_search.parse.urlparse(hit.url).hostname for hit in hits} == {
        "same.example.com",
        "first.example.cn",
        "second.example.cn",
    }


def test_site_query_requires_a_result_from_the_requested_domain(monkeypatch) -> None:
    unrelated_hits = [
        web_search.SearchHit(str(index), f"https://news.example.com/{index}", "文旅", "query")
        for index in range(4)
    ]
    official_hit = web_search.SearchHit("政策", "https://www.mct.gov.cn/policy", "文旅", "query")
    monkeypatch.setattr(web_search, "_search_yahoo", lambda *_args, **_kwargs: unrelated_hits)
    monkeypatch.setattr(web_search, "_search_brave", lambda *_args, **_kwargs: [official_hit])
    monkeypatch.setattr(
        web_search,
        "_search_so360",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected")),
    )

    hits = web_search._search_public_web("site:mct.gov.cn 文旅 人工智能", timeout_seconds=5, limit=5)

    assert official_hit in hits
    assert hits[0] == official_hit


def test_public_search_uses_rss_when_html_engines_are_blocked(monkeypatch) -> None:
    rss_hits = [
        web_search.SearchHit("A", "https://example.com/a", "one", "query", source_hint="bing_rss"),
        web_search.SearchHit("B", "https://another.example/b", "two", "query", source_hint="bing_rss"),
    ]
    monkeypatch.setattr(web_search, "_search_yahoo", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(web_search, "_search_brave", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(web_search, "_search_so360", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(web_search, "_search_google_news", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(web_search, "_search_bing_rss", lambda *_args, **_kwargs: rss_hits)
    monkeypatch.setattr(web_search, "_search_duckduckgo", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected")))
    monkeypatch.setattr(web_search, "_search_bing", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("unexpected")))

    hits = web_search._search_public_web("query", timeout_seconds=5, limit=4)

    assert [hit.url for hit in hits] == ["https://example.com/a", "https://another.example/b"]
