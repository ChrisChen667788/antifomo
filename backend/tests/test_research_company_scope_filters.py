from __future__ import annotations

from app.services.research_service import SourceDocument, _filter_theme_aligned_rows, _rank_top_entities


def _source(
    *,
    title: str,
    snippet: str,
    url: str,
    source_tier: str = "media",
    source_type: str = "web",
    source_label: str | None = None,
) -> SourceDocument:
    return SourceDocument(
        title=title,
        url=url,
        domain=url.split("/")[2],
        snippet=snippet,
        search_query="AI漫剧 行业头部公司",
        source_type=source_type,
        content_status="body_acquired",
        excerpt=f"{title}。{snippet}",
        source_label=source_label,
        source_tier=source_tier,
    )


def test_company_intent_filters_non_company_rows_for_ai_comic_queries() -> None:
    scope_hints = {
        "prefer_company_entities": True,
        "prefer_head_companies": True,
        "seed_companies": ["爱奇艺", "腾讯动漫", "快看漫画"],
    }
    rows = [
        "广州大学：布局漫剧课程与实验内容",
        "爱奇艺：AIGC 动画平台与 IP 商业化持续推进",
        "内容及服务：优化运营与交付流程",
    ]

    filtered = _filter_theme_aligned_rows(
        rows,
        role="target",
        theme_labels=["AI漫剧"],
        scope_hints=scope_hints,
    )

    assert filtered == ["爱奇艺：AIGC 动画平台与 IP 商业化持续推进"]


def test_rank_top_entities_prefers_theme_companies_over_school_like_candidates() -> None:
    sources = [
        _source(
            title="爱奇艺发布 AIGC 动画与短剧平台合作计划",
            snippet="爱奇艺围绕动漫 IP、短剧内容和商业化发行开放生态合作。",
            url="https://www.iqiyi.com/aigc-animation",
            source_tier="official",
            source_label="爱奇艺官网",
        ),
        _source(
            title="腾讯动漫探索 AI 漫剧内容工业化",
            snippet="腾讯动漫披露动画、漫画 IP 与 AI 短剧生产能力布局。",
            url="https://ac.qq.com/ai-comic",
            source_tier="official",
            source_label="腾讯动漫官网",
        ),
        _source(
            title="广州大学推进漫剧课程建设",
            snippet="高校围绕数字内容课程开展实验教学，与头部公司排序无关。",
            url="https://news.gzhu.edu.cn/comic-course",
        ),
        _source(
            title="内容及服务优化运营方案",
            snippet="泛化的内容与服务描述，不对应具体公司主体。",
            url="https://example.com/content-service",
        ),
    ]
    scope_hints = {
        "regions": [],
        "industries": ["AI漫剧"],
        "clients": [],
        "prefer_company_entities": True,
        "prefer_head_companies": True,
        "seed_companies": ["爱奇艺", "腾讯动漫", "快看漫画", "哔哩哔哩"],
    }

    top_targets, pending_targets = _rank_top_entities(
        sources,
        role="target",
        output_language="zh-CN",
        scope_hints=scope_hints,
        theme_terms=["ai漫剧", "漫剧", "ai短剧", "aigc动画", "动漫", "短剧"],
        limit=3,
    )

    names = [item.name for item in [*top_targets, *pending_targets]]

    assert "爱奇艺" in names
    assert "腾讯动漫" in names
    assert all("大学" not in name for name in names)
    assert "内容及服务" not in names
