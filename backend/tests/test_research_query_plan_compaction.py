from app.services.research_service import _build_query_plan, _infer_input_scope_hints


def test_long_culture_tourism_request_builds_concise_search_queries() -> None:
    keyword = "2026年长三角文旅文博行业AI潜在需求及商机情报调研分析"
    scope_hints = _infer_input_scope_hints(keyword, None)

    queries = _build_query_plan(
        keyword,
        None,
        False,
        scope_hints=scope_hints,
        limit=16,
    )

    assert queries
    assert all('""' not in query for query in queries)
    assert any(query == "长三角 景区 博物馆 数字化 招标 预算" for query in queries)
    assert "site:mct.gov.cn 文旅 数字化 人工智能" in queries[:6]
    assert any("site:ccgp.gov.cn 景区 博物馆 导览 招标" == query for query in queries)
    assert all("潜在需求及商机情报调研" not in query for query in queries)


def test_query_plan_rejects_tender_boilerplate_from_strategy_expansions() -> None:
    keyword = "2026年长三角文旅文博行业AI潜在需求及商机情报调研分析"
    scope_hints = _infer_input_scope_hints(keyword, None)
    scope_hints["strategy_query_expansions"] = [
        "潜在投标人须在递交投标文件截止时间前登录烟台市公共资源交易网",
        "长三角 文旅 AI 采购意向",
    ]

    queries = _build_query_plan(
        keyword,
        None,
        False,
        scope_hints=scope_hints,
        limit=24,
    )

    assert all("潜在投标人" not in query for query in queries)
    assert all("公共资源交易网" not in query for query in queries)
    assert "长三角 文旅 AI 采购意向" in queries
