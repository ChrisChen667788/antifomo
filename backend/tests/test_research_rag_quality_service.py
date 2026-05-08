from __future__ import annotations

from dataclasses import dataclass

from app.services.research_rag_quality_service import (
    build_retrieval_correction_profile,
    rerank_sources_cross_encoder,
    review_generation_grounding,
)


@dataclass
class _Source:
    title: str
    url: str
    domain: str
    snippet: str
    search_query: str = ""
    source_type: str = "web"
    content_status: str = "fetched"
    excerpt: str = ""
    source_label: str = ""
    source_tier: str = "media"


@dataclass
class _Section:
    title: str
    items: list[str]


@dataclass
class _Report:
    report_title: str
    executive_summary: str
    consulting_angle: str
    sections: list[_Section]
    target_accounts: list[str]
    target_departments: list[str]
    budget_signals: list[str]
    project_distribution: list[str]
    strategic_directions: list[str]
    tender_timeline: list[str]
    ecosystem_partners: list[str]
    competitor_profiles: list[str]
    benchmark_cases: list[str]
    flagship_products: list[str]
    client_peer_moves: list[str]
    winner_peer_moves: list[str]
    competition_analysis: list[str]


def test_retrieval_correction_profile_scores_and_rewrites_low_signal_sources() -> None:
    profile = build_retrieval_correction_profile(
        [
            _Source(
                title="某市智慧文旅AIGC导览平台公开招标公告",
                url="https://ggzy.example.gov.cn/aigc-tourism",
                domain="ggzy.example.gov.cn",
                snippet="预算680万元，采购数字人导览、AIGC内容生成平台、接口API和等保要求。",
                source_type="procurement",
                source_tier="official",
            ),
            _Source(
                title="银行芯片新闻",
                url="https://media.example.com/bank-chip",
                domain="media.example.com",
                snippet="泛金融芯片行业动态，与文旅AIGC导览无关。",
            ),
        ],
        keyword="文旅AIGC平台",
        research_focus="景区数字人导览和AI营销",
        scope_hints={"regions": ["某市"], "industries": ["文旅"]},
        query_plan=["文旅AIGC平台"],
    )

    assert profile.accepted_source_count == 1
    assert profile.rejected_source_count == 1
    assert profile.status in {"ready", "needs_filtering"}
    assert any("site:ccgp.gov.cn" in query for query in profile.corrective_queries)


def test_sentence_transformers_cross_encoder_adapter_reranks_with_model_scores(monkeypatch) -> None:
    sources = [
        _Source(
            title="泛行业观察",
            url="https://media.example.cn/opinion",
            domain="media.example.cn",
            snippet="泛行业观察，缺少采购公告。",
            source_tier="media",
        ),
        _Source(
            title="南京市数据局电子政务云采购意向公告",
            url="https://www.nanjing.gov.cn/procurement",
            domain="www.nanjing.gov.cn",
            snippet="官方公告披露采购意向、预算安排和项目建设路径。",
            source_tier="official",
        ),
    ]

    class _FakeCrossEncoder:
        def predict(self, pairs):
            assert "南京市数据局" in pairs[0][0]
            return [0.1, 0.9]

    monkeypatch.setattr(
        "app.services.research_rag_quality_service._load_sentence_transformers_cross_encoder",
        lambda _model: _FakeCrossEncoder(),
    )

    reranked, profile = rerank_sources_cross_encoder(
        sources,
        query="南京市数据局 政务云 采购意向",
        model_name="fake-cross-encoder",
        top_k=2,
        backend="sentence_transformers",
    )

    assert reranked[0].url == "https://www.nanjing.gov.cn/procurement"
    assert profile.backend == "sentence-transformers"
    assert profile.reranked_count == 2
    assert profile.to_diagnostics_update()["reranker_backend"] == "sentence-transformers"


def test_auto_cross_encoder_adapter_falls_back_when_sentence_transformers_is_unavailable(monkeypatch) -> None:
    sources = [
        _Source(
            title="泛行业观察",
            url="https://media.example.cn/opinion",
            domain="media.example.cn",
            snippet="泛行业观察，缺少采购公告。",
            source_tier="media",
        ),
        _Source(
            title="南京市数据局电子政务云采购意向公告",
            url="https://www.nanjing.gov.cn/procurement",
            domain="www.nanjing.gov.cn",
            snippet="官方公告披露采购意向、预算安排和项目建设路径。",
            source_tier="official",
        ),
    ]

    def _raise_missing_model(_model_name: str):
        raise ImportError("sentence-transformers unavailable")

    monkeypatch.setattr(
        "app.services.research_rag_quality_service._load_sentence_transformers_cross_encoder",
        _raise_missing_model,
    )

    reranked, profile = rerank_sources_cross_encoder(
        sources,
        query="南京市数据局 政务云 采购意向",
        model_name="fake-cross-encoder",
        top_k=2,
        backend="auto",
    )

    assert reranked[0].url == "https://www.nanjing.gov.cn/procurement"
    assert profile.backend == "local-cross-encoder-style"
    assert profile.reranked_count == 2
    assert any("回退本地复排" in note for note in profile.notes)


def test_cross_encoder_adapter_falls_back_when_score_count_mismatches(monkeypatch) -> None:
    sources = [
        _Source(
            title="行业观察",
            url="https://media.example.cn/opinion",
            domain="media.example.cn",
            snippet="泛行业观察。",
            source_tier="media",
        ),
        _Source(
            title="官方采购意向公告",
            url="https://www.nanjing.gov.cn/procurement",
            domain="www.nanjing.gov.cn",
            snippet="官方采购意向公告披露预算安排。",
            source_tier="official",
        ),
    ]

    class _BadCrossEncoder:
        def predict(self, pairs):
            assert len(pairs) == 2
            return [0.5]

    monkeypatch.setattr(
        "app.services.research_rag_quality_service._load_sentence_transformers_cross_encoder",
        lambda _model: _BadCrossEncoder(),
    )

    reranked, profile = rerank_sources_cross_encoder(
        sources,
        query="南京 官方采购意向 预算",
        model_name="bad-cross-encoder",
        top_k=2,
        backend="auto",
    )

    assert len(reranked) == 2
    assert profile.backend == "local-cross-encoder-style"
    assert any("returned 1 scores" in note for note in profile.notes)


def test_generation_grounding_review_flags_unsupported_claims() -> None:
    report = _Report(
        report_title="某市文旅AIGC平台：预算与试点路径",
        executive_summary="公开来源显示某市正在采购文旅AIGC平台，预算680万元。另有结论称海外银行芯片项目已经中标。",
        consulting_angle="适合作为方案试点和投标准备底稿。",
        sections=[_Section(title="方案设计", items=["先做数字人导览试点，再扩展AI营销。"])],
        target_accounts=["某市文旅集团"],
        target_departments=["数字化部"],
        budget_signals=["预算680万元"],
        project_distribution=[],
        strategic_directions=["数字人导览"],
        tender_timeline=["2025年公开招标"],
        ecosystem_partners=[],
        competitor_profiles=[],
        benchmark_cases=[],
        flagship_products=[],
        client_peer_moves=[],
        winner_peer_moves=[],
        competition_analysis=[],
    )
    review = review_generation_grounding(
        report,
        [
            _Source(
                title="某市智慧文旅AIGC导览平台公开招标公告",
                url="https://ggzy.example.gov.cn/aigc-tourism",
                domain="ggzy.example.gov.cn",
                snippet="某市采购文旅AIGC平台，预算680万元，建设数字人导览和AI营销能力。",
                source_tier="official",
            )
        ],
    )

    assert review.grounding_score > 0
    assert any("海外银行芯片" in claim for claim in review.unsupported_claims)
