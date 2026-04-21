from __future__ import annotations

from app.services.research_service import (
    SourceDocument,
    _build_entity_graph,
    _company_intent_summary_needs_override,
    _extract_rank_entity_candidates,
    _filter_sources_by_theme_relevance,
    _filter_theme_aligned_rows,
    _rank_top_entities,
)


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


def test_filter_sources_by_theme_relevance_prefers_company_like_sources_for_company_queries() -> None:
    sources = [
        _source(
            title="爱奇艺发布 AI 漫剧平台合作计划",
            snippet="围绕动漫 IP、内容发行与 AIGC 短剧商业化开放合作。",
            url="https://www.iqiyi.com/aigc-comic",
            source_tier="official",
            source_label="爱奇艺官网",
        ),
        _source(
            title="广州大学推进漫剧课程建设",
            snippet="高校围绕课程实验开展建设，并非头部公司名单。",
            url="https://news.gzhu.edu.cn/comic-course",
        ),
        _source(
            title="内容及服务升级建议",
            snippet="泛化内容服务描述，没有对应具体公司主体。",
            url="https://example.com/content-service",
        ),
    ]
    scope_hints = {
        "regions": [],
        "industries": ["AI漫剧"],
        "prefer_company_entities": True,
        "prefer_head_companies": True,
        "seed_companies": ["爱奇艺", "腾讯动漫", "快看漫画"],
    }

    filtered = _filter_sources_by_theme_relevance(
        sources,
        theme_terms=["ai漫剧", "漫剧", "动画", "ip", "短剧"],
        scope_hints=scope_hints,
        company_anchor_terms=[],
    )

    titles = [item.title for item in filtered]
    assert "爱奇艺发布 AI 漫剧平台合作计划" in titles
    assert "广州大学推进漫剧课程建设" not in titles
    assert "内容及服务升级建议" not in titles


def test_company_query_summary_override_triggers_when_summary_lacks_company_anchor() -> None:
    scope_hints = {
        "industries": ["AI漫剧"],
        "prefer_company_entities": True,
        "prefer_head_companies": True,
        "seed_companies": ["爱奇艺", "腾讯动漫", "快看漫画"],
    }

    needs_override = _company_intent_summary_needs_override(
        scope_hints=scope_hints,
        summary="当前围绕行业趋势、内容服务与课程建设做了泛化判断，但没有收敛到具体公司。",
        accounts=["爱奇艺", "腾讯动漫"],
        competitors=["快看漫画"],
    )

    assert needs_override is True


def test_rank_top_entities_skips_phrase_only_fallback_values_without_source_support() -> None:
    sources = [
        _source(
            title="百联集团披露数字化建设与会员运营规划",
            snippet="百联集团公开提到数字化建设、会员运营与项目统筹。",
            url="https://www.bailian.com/digital-plan",
            source_tier="official",
            source_label="百联集团官网",
        ),
        _source(
            title="某区域商圈集团推进会员体系升级",
            snippet="行业动态围绕会员运营与数字化建设展开。",
            url="https://example.com/retail-upgrade",
        ),
    ]

    top_targets, pending_targets = _rank_top_entities(
        sources,
        role="target",
        output_language="zh-CN",
        scope_hints={"regions": [], "industries": [], "clients": []},
        theme_terms=["百联", "数字化", "会员运营"],
        fallback_values=[
            "围绕预算窗口与进入路径",
            "内容及服务",
            "百联集团",
        ],
        limit=3,
    )

    names = [item.name for item in [*top_targets, *pending_targets]]

    assert "百联集团" in names
    assert "围绕预算窗口与进入路径" not in names
    assert "内容及服务" not in names


def test_extract_rank_entity_candidates_links_scope_seed_alias_to_canonical_name() -> None:
    candidates = _extract_rank_entity_candidates(
        "百联将推进会员运营与数字化建设。",
        scope_hints={"seed_companies": ["百联集团"]},
    )

    assert "百联集团" in candidates
    assert "百联" not in candidates


def test_build_entity_graph_merges_scope_alias_mentions_under_canonical_company() -> None:
    sources = [
        _source(
            title="百联披露会员运营与数字化升级节奏",
            snippet="百联围绕会员运营、数字化建设与商业化协同持续推进。",
            url="https://www.bailian.com/digital-plan",
            source_tier="official",
            source_label="百联官网",
        )
    ]

    graph = _build_entity_graph(
        sources,
        scope_hints={"regions": [], "industries": [], "clients": [], "seed_companies": ["百联集团"]},
    )

    canonical_names = [entity.canonical_name for entity in graph.entities]
    aliases_by_name = {entity.canonical_name: entity.aliases for entity in graph.entities}

    assert "百联集团" in canonical_names
    assert "百联" in aliases_by_name["百联集团"]


def test_rank_top_entities_uses_scope_alias_canonicalization_for_company_seed() -> None:
    sources = [
        _source(
            title="百联启动会员与数字化建设规划",
            snippet="百联围绕会员体系、数字化建设与项目统筹展开布局。",
            url="https://www.bailian.com/member-plan",
            source_tier="official",
            source_label="百联官网",
        ),
    ]
    scope_hints = {
        "regions": [],
        "industries": ["零售数字化"],
        "clients": [],
        "prefer_company_entities": True,
        "prefer_head_companies": True,
        "seed_companies": ["百联集团"],
    }

    top_targets, pending_targets = _rank_top_entities(
        sources,
        role="target",
        output_language="zh-CN",
        scope_hints=scope_hints,
        theme_terms=["百联", "数字化", "会员运营"],
        limit=3,
    )

    names = [item.name for item in [*top_targets, *pending_targets]]

    assert "百联集团" in names
    assert "百联" not in names
