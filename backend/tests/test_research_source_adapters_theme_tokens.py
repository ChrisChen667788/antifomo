from app.services.research.web_search import SearchHit
from app.services import research_source_adapters
from app.services.research_source_adapters import _build_match_tokens, _search_domain_hits


def test_long_culture_tourism_keyword_expands_specific_adapter_tokens() -> None:
    tokens = _build_match_tokens(
        "2026年长三角文旅文博行业AI潜在需求及商机情报调研分析",
        None,
    )

    assert "文旅" in tokens
    assert "文博" in tokens
    assert "博物馆" in tokens
    assert "导览" in tokens


def test_domain_adapter_uses_so360_direct_results(monkeypatch) -> None:
    monkeypatch.setattr(
        research_source_adapters,
        "_search_so360",
        lambda *_args, **_kwargs: [
            SearchHit(
                title="上海博物馆数字化导览项目公开招标公告",
                url="https://www.ccgp.gov.cn/project/1",
                snippet="采购人发布项目预算。",
                search_query="query",
            )
        ],
    )
    monkeypatch.setattr(research_source_adapters, "_fetch_html", lambda *_args, **_kwargs: "")

    hits = _search_domain_hits(
        "site:ccgp.gov.cn 上海 博物馆 数字化 招标",
        timeout_seconds=5,
        limit=4,
        source_label="政府采购合规聚合",
        source_hint="compliant_procurement_aggregate",
        allowed_domains=("ccgp.gov.cn",),
        tokens=["博物馆", "数字化"],
    )

    assert len(hits) == 1
    assert hits[0].url == "https://www.ccgp.gov.cn/project/1"
