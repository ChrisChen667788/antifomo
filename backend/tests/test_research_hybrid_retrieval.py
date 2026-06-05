from __future__ import annotations

from app.services import research_service
from app.services.research.source_query_plans import (
    build_company_profile_query_plan,
    build_corrective_query_plan,
    build_expanded_query_plan,
    build_query_plan,
)
from app.services.research.tender_detail_enrichment import build_tender_detail_query_plan
from app.schemas.research import (
    ResearchEntityGraphOut,
    ResearchRankedEntityOut,
    ResearchReportDocument,
    ResearchReportRequest,
    ResearchReportSectionOut,
)


def _source_query_plan_dependencies():
    return research_service._source_query_plan_dependencies()


def test_hybrid_rank_prefers_company_official_hits_for_company_intent() -> None:
    keyword = "AI漫剧头部公司"
    research_focus = "分析快手可灵、阅文、中文在线这些公司的AI商机、合作平台与商业化路径"
    scope_hints = {
        "industries": ["AI漫剧"],
        "prefer_company_entities": True,
        "company_anchors": ["快手可灵", "阅文", "中文在线"],
    }
    hits = [
        research_service.SearchHit(
            title="广州大学 AIGC 研究中心年度论坛",
            url="https://news.gzhu.edu.cn/aigc-forum",
            snippet="AIGC 动画、教学与研究活动。",
            search_query=keyword,
            source_hint="web",
        ),
        research_service.SearchHit(
            title="快手可灵 内容平台与 AI 漫剧合作",
            url="https://www.kuaishou.com/brand/kling-ai-comic",
            snippet="快手可灵开放 AIGC 漫剧内容平台、合作与商业化入口。",
            search_query=keyword,
            source_hint="web",
            source_label="官网",
        ),
        research_service.SearchHit(
            title="AI漫剧行业趋势观察",
            url="https://36kr.com/p/ai-comic-market",
            snippet="行业趋势与多家公司布局概览。",
            search_query=keyword,
            source_hint="web",
            source_label="36氪",
        ),
    ]

    ranked = research_service._hybrid_rank_hits(
        hits,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
    )

    assert ranked
    assert ranked[0].url == "https://www.kuaishou.com/brand/kling-ai-comic"
    assert all("广州大学" not in hit.title for hit in ranked[:2])


def test_hybrid_rank_does_not_promote_search_query_only_overlap_noise() -> None:
    keyword = "政务云预算窗口"
    research_focus = "梳理江苏重点甲方、采购意向和预算路径"
    scope_hints = {
        "regions": ["江苏"],
        "industries": ["政务云"],
        "clients": ["南京市数据局"],
    }
    hits = [
        research_service.SearchHit(
            title="某高校论坛圆桌回顾",
            url="https://news.example.edu.cn/forum-roundtable",
            snippet="围绕 AI 教学、论坛活动和研究分享。",
            search_query='site:gov.cn "南京市数据局" 政务云预算窗口 规划 预算',
            source_hint="web",
        ),
        research_service.SearchHit(
            title="南京市数据局电子政务云平台采购意向公告",
            url="https://www.nanjing.gov.cn/data/procurement-intent",
            snippet="公告披露电子政务云平台采购意向、预算安排与项目建设路径。",
            search_query='site:ccgp.gov.cn "南京市数据局" 政务云预算窗口 采购意向 中标',
            source_hint="policy",
            source_label="中国政府网政策/讲话",
        ),
    ]

    ranked = research_service._hybrid_rank_hits(
        hits,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
    )

    assert ranked
    assert ranked[0].url == "https://www.nanjing.gov.cn/data/procurement-intent"
    assert all("论坛" not in hit.title for hit in ranked[:1])


def test_source_rerank_prefers_official_browser_extracted_sources() -> None:
    keyword = "AI漫剧头部公司"
    research_focus = "分析快手可灵、阅文、中文在线这些公司的AI商机"
    scope_hints = {
        "industries": ["AI漫剧"],
        "prefer_company_entities": True,
        "company_anchors": ["快手可灵"],
    }
    sources = [
        research_service.SourceDocument(
            title="AI漫剧行业趋势",
            url="https://36kr.com/p/ai-comic-market",
            domain="36kr.com",
            snippet="行业趋势综述",
            search_query=keyword,
            source_type="web",
            content_status="snippet_only",
            excerpt="AI漫剧市场趋势与行业观察。",
            source_label="36氪",
            source_tier="media",
            source_origin="search",
        ),
        research_service.SourceDocument(
            title="快手可灵 AI 漫剧合作平台",
            url="https://www.kuaishou.com/brand/kling-ai-comic",
            domain="www.kuaishou.com",
            snippet="官方合作平台介绍",
            search_query=keyword,
            source_type="web",
            content_status="browser_extracted",
            excerpt="快手可灵面向AI漫剧内容合作提供开放平台、商业化能力、合作入口与团队信息。",
            source_label="官网",
            source_tier="official",
            source_origin="search",
        ),
    ]

    ranked = research_service._rerank_sources_hybrid(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
    )

    assert ranked[0].url == "https://www.kuaishou.com/brand/kling-ai-comic"
    assert ranked[0].content_status == "browser_extracted"


def test_source_rerank_does_not_promote_query_only_overlap_noise() -> None:
    keyword = "政务云预算窗口"
    research_focus = "梳理江苏重点甲方、采购意向和预算路径"
    scope_hints = {
        "regions": ["江苏"],
        "industries": ["政务云"],
        "clients": ["南京市数据局"],
    }
    sources = [
        research_service.SourceDocument(
            title="某高校数字化论坛纪要",
            url="https://news.example.edu.cn/forum-roundtable",
            domain="news.example.edu.cn",
            snippet="论坛讨论 AI 教学、数字化趋势和经验分享。",
            search_query='site:gov.cn "南京市数据局" 政务云预算窗口 规划 预算',
            source_type="web",
            content_status="body_acquired",
            excerpt="内容主要围绕高校数字化论坛与教学案例，并未涉及南京市数据局采购意向。",
            source_label="互联网公开网页",
            source_tier="media",
            source_origin="search",
        ),
        research_service.SourceDocument(
            title="南京市数据局电子政务云平台采购意向公告",
            url="https://www.nanjing.gov.cn/data/procurement-intent",
            domain="www.nanjing.gov.cn",
            snippet="公告披露电子政务云平台采购意向、预算安排与项目建设路径。",
            search_query='site:ccgp.gov.cn "南京市数据局" 政务云预算窗口 采购意向 中标',
            source_type="policy",
            content_status="browser_extracted",
            excerpt="公告明确电子政务云平台采购意向、预算安排和后续项目建设路径。",
            source_label="中国政府网政策/讲话",
            source_tier="official",
            source_origin="search",
        ),
    ]

    ranked = research_service._rerank_sources_hybrid(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
    )

    assert ranked
    assert ranked[0].url == "https://www.nanjing.gov.cn/data/procurement-intent"
    assert "论坛" not in ranked[0].title


def test_cross_encoder_style_reranker_is_feature_flagged_and_records_scope_diagnostics() -> None:
    keyword = "南京市数据局 政务云 预算"
    research_focus = "核验采购意向、预算窗口和官方来源"
    scope_hints = {
        "regions": ["江苏"],
        "industries": ["政务云"],
        "clients": ["南京市数据局"],
        "enable_cross_encoder_rerank": True,
    }
    sources = [
        research_service.SourceDocument(
            title="政务云预算行业观察",
            url="https://media.example.cn/gov-cloud-opinion",
            domain="media.example.cn",
            snippet="泛行业观点，提到政务云预算。",
            search_query=keyword,
            source_type="web",
            content_status="snippet_only",
            excerpt="泛行业观点，缺少南京市数据局采购意向原文。",
            source_label="行业媒体",
            source_tier="media",
            source_origin="search",
        ),
        research_service.SourceDocument(
            title="南京市数据局电子政务云采购意向公告",
            url="https://www.nanjing.gov.cn/data/procurement-intent",
            domain="www.nanjing.gov.cn",
            snippet="官方公告披露采购意向、预算安排和后续项目建设路径。",
            search_query=keyword,
            source_type="policy",
            content_status="browser_extracted",
            excerpt="南京市数据局电子政务云采购意向公告披露预算安排、采购意向、项目建设路径和后续方案比选窗口。",
            source_label="官网",
            source_tier="official",
            source_origin="search",
        ),
    ]

    ranked = research_service._rerank_sources_hybrid(
        sources,
        keyword=keyword,
        research_focus=research_focus,
        scope_hints=scope_hints,
    )

    assert ranked[0].url == "https://www.nanjing.gov.cn/data/procurement-intent"
    assert scope_hints["reranker_used"] is True
    assert scope_hints["reranker_model"]
    assert scope_hints["reranker_top_k"] >= 1
    assert scope_hints["reranker_notes"]


def test_runtime_strategy_config_feeds_query_and_reranker_scope_hints(monkeypatch) -> None:
    payload = ResearchReportRequest(
        keyword="南京市数据局 政务云",
        research_focus="核验采购意向、预算窗口和官方来源",
        runtime_strategy_config={
            "query_generation": {
                "status": "ready",
                "applied_lanes": ["query_recovery"],
                "fallback_lanes": [],
                "warnings": [],
                "effective_config": {
                    "enabled": True,
                    "query_recovery_enabled": True,
                    "public_expansion_on_watch": True,
                    "corrective_query_limit": 7,
                },
            },
            "source_reranker": {
                "status": "ready",
                "applied_lanes": ["reranker_official_recall"],
                "fallback_lanes": [],
                "warnings": [],
                "effective_config": {
                    "enabled": True,
                    "reranker_adapter": "sentence_transformers_cross_encoder",
                    "official_source_bias": True,
                    "recall_at_k": 7,
                    "fallback_adapter": "local_rrf",
                },
            },
        },
    )

    runtime = research_service._build_research_runtime(payload)
    hints = research_service._runtime_strategy_scope_hints(payload)

    assert runtime["runtime_query_recovery_enabled"] is True
    assert runtime["corrective_query_limit"] == 7
    assert hints["runtime_strategy_status"] == "ready"
    assert hints["runtime_query_recovery_enabled"] is True
    assert hints["runtime_source_reranker_enabled"] is True
    assert hints["enable_cross_encoder_rerank"] is True
    assert hints["runtime_reranker_backend"] == "sentence_transformers"
    assert hints["runtime_reranker_top_k"] == 7

    captured: dict[str, object] = {}

    class _FakeRerankProfile:
        def to_diagnostics_update(self) -> dict[str, object]:
            return {
                "reranker_used": True,
                "reranker_model": "cross-encoder/ms-marco-MiniLM-L-6-v2",
                "reranker_top_k": 7,
                "reranker_backend": "sentence-transformers",
                "reranker_notes": ["runtime strategy test"],
            }

    def _fake_rerank(sources, *, query, model_name, top_k=20, backend="auto"):
        captured.update({"top_k": top_k, "backend": backend})
        return list(sources), _FakeRerankProfile()

    monkeypatch.setattr(research_service, "rerank_sources_cross_encoder", _fake_rerank)
    scope_hints = {
        "enable_cross_encoder_rerank": True,
        "runtime_reranker_backend": "sentence_transformers",
        "runtime_reranker_top_k": 7,
    }
    research_service._rerank_sources_hybrid(
        [
            research_service.SourceDocument(
                title="南京市数据局电子政务云采购意向公告",
                url="https://www.nanjing.gov.cn/data/procurement-intent",
                domain="www.nanjing.gov.cn",
                snippet="官方公告披露采购意向、预算安排和后续项目建设路径。",
                search_query=payload.keyword,
                source_type="policy",
                content_status="browser_extracted",
                excerpt="南京市数据局电子政务云采购意向公告披露预算安排、采购意向和项目建设路径。",
                source_label="官网",
                source_tier="official",
                source_origin="search",
            )
        ],
        keyword=payload.keyword,
        research_focus=payload.research_focus,
        scope_hints=scope_hints,
    )

    assert captured == {"top_k": 7, "backend": "sentence_transformers"}


def test_source_diagnostics_exposes_fetch_clean_analyze_pipeline() -> None:
    sources = [
        research_service.SourceDocument(
            title="快手可灵 AI 漫剧合作平台",
            url="https://www.kuaishou.com/brand/kling-ai-comic",
            domain="www.kuaishou.com",
            snippet="官方合作平台介绍",
            search_query="AI漫剧头部公司",
            source_type="web",
            content_status="browser_extracted",
            excerpt="快手可灵开放 AIGC 漫剧平台与合作入口。",
            source_label="官网",
            source_tier="official",
            source_origin="search",
        ),
        research_service.SourceDocument(
            title="AI漫剧行业趋势观察",
            url="https://36kr.com/p/ai-comic-market",
            domain="36kr.com",
            snippet="行业趋势综述",
            search_query="AI漫剧头部公司",
            source_type="web",
            content_status="body_acquired",
            excerpt="行业趋势与多家公司布局。",
            source_label="36氪",
            source_tier="media",
            source_origin="adapter",
        ),
    ]

    diagnostics = research_service._build_source_diagnostics(
        sources,
        enabled_source_labels=["官网", "36氪"],
        scope_hints={"industries": ["AI漫剧"], "clients": ["快手可灵"]},
        recency_window_years=7,
        filtered_old_source_count=1,
        filtered_region_conflict_count=1,
        retained_source_count=2,
        strict_topic_source_count=2,
        topic_anchor_terms=["AI漫剧", "快手可灵"],
        matched_theme_labels=["AI漫剧"],
        entity_graph=ResearchEntityGraphOut(),
        expansion_triggered=False,
        corrective_triggered=True,
        candidate_profile_companies=["快手可灵"],
        candidate_profile_hit_count=2,
        candidate_profile_official_hit_count=1,
        candidate_profile_source_labels=["官网"],
    )

    assert diagnostics.pipeline_stages[0].key == "fetch"
    assert diagnostics.pipeline_stages[0].value == 2
    assert diagnostics.pipeline_stages[1].key == "clean"
    assert diagnostics.pipeline_stages[1].value == 2
    assert diagnostics.pipeline_stages[2].key == "analyze"
    assert "官方源占比" in diagnostics.pipeline_stages[2].summary
    assert "保留 2 条可用来源" in diagnostics.pipeline_summary


def test_company_profile_query_plan_adds_official_profile_queries() -> None:
    queries = build_company_profile_query_plan(
        ["阅文集团"],
        keyword="AI漫剧头部公司",
        research_focus="分析商业化路径与合作窗口",
        limit=12,
        deps=_source_query_plan_dependencies(),
    )

    assert any("关于我们" in query for query in queries)
    assert any("公司简介" in query for query in queries)
    assert any("投资者关系" in query for query in queries)


def test_query_plan_adds_scoped_official_queries_for_narrow_buyer_scope() -> None:
    scope_hints = {
        "regions": ["江苏"],
        "industries": ["政务云"],
        "clients": ["南京市数据局"],
    }

    queries = build_query_plan(
        "政务云预算窗口",
        "梳理重点甲方、预算窗口和采购路径",
        False,
        scope_hints=scope_hints,
        preferred_wechat_accounts=None,
        limit=24,
        deps=_source_query_plan_dependencies(),
    )

    assert any('site:gov.cn 江苏 政务云 政务云预算窗口 规划 预算 战略' == query for query in queries)
    assert any('site:ggzy.gov.cn "南京市数据局" 政务云预算窗口 招标 项目' == query for query in queries)
    assert any('site:ccgp.gov.cn "南京市数据局" 政务云预算窗口 采购意向 中标' == query for query in queries)


def test_expanded_and_corrective_query_plans_add_scoped_official_queries() -> None:
    scope_hints = {
        "regions": ["江苏"],
        "industries": ["政务云"],
        "clients": ["南京市数据局"],
    }

    expanded_queries = build_expanded_query_plan(
        "政务云预算窗口",
        "梳理重点甲方、预算窗口和采购路径",
        scope_hints=scope_hints,
        include_wechat=False,
        preferred_wechat_accounts=None,
        limit=24,
        deps=_source_query_plan_dependencies(),
    )
    corrective_queries = build_corrective_query_plan(
        keyword="政务云预算窗口",
        research_focus="梳理重点甲方、预算窗口和采购路径",
        scope_hints=scope_hints,
        include_wechat=False,
        preferred_wechat_accounts=None,
        limit=24,
        deps=_source_query_plan_dependencies(),
    )

    assert any('site:gov.cn 江苏 "南京市数据局" 规划 战略' == query for query in expanded_queries)
    assert any('site:ggzy.gov.cn 江苏 政务云 政务云预算窗口 招标 项目 中标' == query for query in expanded_queries)
    assert any('site:gov.cn "南京市数据局" 政务云预算窗口 规划 预算' == query for query in corrective_queries)
    assert any('site:ccgp.gov.cn 江苏 政务云 政务云预算窗口 采购意向 招标 中标' == query for query in corrective_queries)


def test_tender_detail_query_plan_targets_confirmed_project_fields() -> None:
    source = research_service.SourceDocument(
        title="某市智慧文旅AIGC导览平台公开招标公告",
        url="https://ggzy.example.gov.cn/tender/aigc-tourism",
        domain="ggzy.example.gov.cn",
        snippet="采购人：某文旅集团，预算金额 680万元，建设数字人导览、接口API、等保二级。",
        search_query="文旅AIGC平台 招标",
        source_type="procurement",
        content_status="fetched",
        excerpt="招标代理：某招标代理公司；投标人需提供大模型相关软件著作权证书。",
        source_label="公共资源交易平台",
        source_tier="official",
    )

    queries = build_tender_detail_query_plan(
        [source],
        keyword="文旅AIGC平台",
        research_focus="景区数字人导览",
        scope_hints={"regions": ["华东"], "industries": ["文旅"], "clients": ["某文旅集团"]},
        limit=8,
        deps=research_service._tender_detail_dependencies(),
    )

    assert queries
    assert any("招标人" in query and "投标人" in query and "招标代理" in query for query in queries)
    assert any("site:ggzy.gov.cn" in query for query in queries)


def test_query_plans_include_curated_wechat_accounts_when_enabled() -> None:
    preferred_accounts = ("云技术", "智能超参数")

    queries = build_query_plan(
        "算力大模型商机",
        "关注采购路径和生态伙伴",
        True,
        scope_hints={},
        preferred_wechat_accounts=preferred_accounts,
        limit=24,
        deps=_source_query_plan_dependencies(),
    )
    expanded_queries = build_expanded_query_plan(
        "算力大模型商机",
        "关注采购路径和生态伙伴",
        scope_hints={},
        include_wechat=True,
        preferred_wechat_accounts=preferred_accounts,
        limit=24,
        deps=_source_query_plan_dependencies(),
    )
    corrective_queries = build_corrective_query_plan(
        keyword="算力大模型商机",
        research_focus="关注采购路径和生态伙伴",
        scope_hints={},
        include_wechat=True,
        preferred_wechat_accounts=preferred_accounts,
        limit=24,
        deps=_source_query_plan_dependencies(),
    )

    assert any('site:mp.weixin.qq.com "云技术"' in query and "算力大模型" in query for query in queries)
    assert any('site:mp.weixin.qq.com "智能超参数"' in query and "算力大模型" in query for query in expanded_queries)
    assert any('site:mp.weixin.qq.com "云技术"' in query and "算力大模型" in query for query in corrective_queries)


def test_scope_hints_attach_industry_methodology_profile_for_medical_topics() -> None:
    scope_hints = research_service._infer_input_scope_hints(
        "上海医疗 AI 影像商机",
        "关注三甲医院信息科、医务处、预算批次和试点扩面",
    )

    assert scope_hints["industry_methodology_profile"] == "医疗"
    assert "临床场景 -> 信息科与医务线 -> 合规安全 -> 系统集成 -> 投入产出" in scope_hints["industry_methodology_framework"]
    assert any("医院" in query and "信息化" in query for query in scope_hints["strategy_query_expansions"])
    assert any("信息科" in item for item in scope_hints["industry_methodology_questions"])


def test_query_plan_prioritizes_industry_methodology_expansions() -> None:
    scope_hints = research_service._infer_input_scope_hints(
        "上海医疗 AI 影像商机",
        "关注三甲医院信息科、医务处、预算批次和试点扩面",
    )

    queries = build_query_plan(
        "上海医疗 AI 影像商机",
        "关注三甲医院信息科、医务处、预算批次和试点扩面",
        False,
        scope_hints=scope_hints,
        limit=12,
        preferred_wechat_accounts=None,
        deps=_source_query_plan_dependencies(),
    )

    assert any("医院" in query and "采购" in query for query in queries[:8])
    assert any("卫健" in query or "信息科" in query for query in queries[:10])


def test_candidate_profile_support_promotes_entity_from_official_profile_query() -> None:
    profile_sources = [
        research_service.SourceDocument(
            title="Kling AI | Kuaishou",
            url="https://www.kuaishou.com/brand/kling-ai",
            domain="www.kuaishou.com",
            snippet="Official creator platform and business profile.",
            search_query="AI漫剧头部公司 快手可灵 官方公开入口",
            source_type="web",
            content_status="browser_extracted",
            excerpt="Kling AI is an official creative platform for video and comic generation.",
            source_label="快手官网",
            source_tier="official",
            source_origin="search",
        )
    ]
    pending = [
        ResearchRankedEntityOut(
            name="快手可灵",
            score=38,
            reasoning="待补证候选",
            entity_mode="pending",
        )
    ]

    support = research_service._build_candidate_profile_support(profile_sources, ["快手可灵"])
    promoted, remaining = research_service._promote_pending_entities_with_candidate_profiles(
        [],
        pending,
        candidate_profile_support=support,
        limit=3,
    )

    assert support["快手可灵"]["hit_count"] == 1
    assert support["快手可灵"]["official_hit_count"] == 1
    assert len(promoted) == 1
    assert promoted[0].name == "快手可灵"
    assert promoted[0].entity_mode == "instance"
    assert remaining == []


def test_report_readiness_and_commercial_summary_enforce_business_slots() -> None:
    report = ResearchReportDocument(
        keyword="AI漫剧头部公司",
        research_focus="分析头部公司的商业化路径、预算窗口与合作机会",
        output_language="zh-CN",
        research_mode="deep",
        report_title="AI漫剧头部公司商业化研判",
        executive_summary="优先围绕快手可灵和阅文集团推进预算与平台合作切入。",
        consulting_angle="先锁定头部平台和内容方，再围绕预算、入口和伙伴关系收敛销售路径。",
        sections=[
            ResearchReportSectionOut(
                title="重点甲方",
                items=["快手可灵", "阅文集团"],
                evidence_density="high",
                source_quality="high",
                official_source_ratio=0.5,
                evidence_count=2,
                evidence_quota=2,
                meets_evidence_quota=True,
            ),
            ResearchReportSectionOut(
                title="预算与投资信号",
                items=["2026 年内容平台合作预算已释放", "未来两个季度是首轮签约窗口"],
                evidence_density="medium",
                source_quality="high",
                official_source_ratio=0.4,
                evidence_count=2,
                evidence_quota=2,
                meets_evidence_quota=True,
            ),
            ResearchReportSectionOut(
                title="公开业务联系方式",
                items=["官网商务合作入口", "公开 BD 邮箱"],
                evidence_density="medium",
                source_quality="medium",
                official_source_ratio=0.5,
                evidence_count=2,
                evidence_quota=1,
                meets_evidence_quota=True,
            ),
            ResearchReportSectionOut(
                title="竞争分析",
                items=["公开线索对竞品进入窗口存在分歧，需继续核验。"],
                evidence_density="low",
                source_quality="medium",
                confidence_tone="conflict",
                contradiction_detected=True,
                contradiction_note="两类来源对竞品推进节奏表述相互矛盾。",
                official_source_ratio=0.0,
                evidence_count=1,
                evidence_quota=2,
                meets_evidence_quota=False,
            ),
        ],
        target_accounts=["快手可灵", "阅文集团"],
        top_target_accounts=[
            {
                "name": "快手可灵",
                "score": 84,
                "reasoning": "官方平台与合作入口明确。",
                "score_breakdown": [],
                "evidence_links": [],
            }
        ],
        target_departments=["商务合作", "内容平台"],
        public_contact_channels=["官网商务合作入口", "公开 BD 邮箱"],
        budget_signals=["2026 年内容平台合作预算已释放"],
        strategic_directions=["先从平台合作和联合发行切入"],
        tender_timeline=["未来两个季度是重点进入窗口"],
        ecosystem_partners=["内容分发平台"],
        competitor_profiles=["中文在线"],
        source_count=7,
        evidence_density="high",
        source_quality="high",
        query_plan=["AI漫剧头部公司 商业化", "快手可灵 合作 平台"],
        sources=[],
        source_diagnostics={
            "official_source_ratio": 0.43,
            "pipeline_summary": "取数 -> 清洗 -> 分析",
            "pipeline_stages": [],
        },
        entity_graph=ResearchEntityGraphOut(),
    )

    readiness = research_service._build_report_readiness(report)
    commercial_summary = research_service._build_commercial_summary(report)
    report = report.model_copy(
        update={
            "report_readiness": readiness,
            "commercial_summary": commercial_summary,
        }
    )
    technical_appendix = research_service._build_technical_appendix(report)
    review_queue = research_service._build_review_queue(report)

    assert readiness.status == "ready"
    assert readiness.actionable is True
    assert readiness.evidence_gate_passed is True
    assert commercial_summary.account_focus == ["快手可灵", "阅文集团"]
    assert "预算" in commercial_summary.budget_signal
    assert "窗口" in commercial_summary.entry_window
    assert "快手可灵" in commercial_summary.next_action
    assert "预算" in commercial_summary.next_action or "窗口" in commercial_summary.next_action
    assert technical_appendix.key_assumptions
    assert technical_appendix.scenario_comparison
    assert technical_appendix.technical_appendix
    assert review_queue
    assert review_queue[0].severity == "high"


def test_report_readiness_guardrails_keep_title_clean() -> None:
    report = ResearchReportDocument(
        keyword="政务云商机",
        research_focus="关注预算和采购窗口",
        output_language="zh-CN",
        research_mode="deep",
        report_title="华东｜政务云：账户优先级与推进路径",
        executive_summary="优先围绕省级客户与预算窗口继续收敛目标名单。",
        consulting_angle="先轻量推进，同时继续补官方源与预算归口。",
        sections=[],
        target_accounts=["省级客户"],
        source_count=3,
        evidence_density="low",
        source_quality="medium",
        query_plan=["政务云 预算", "政务云 采购"],
        sources=[],
        source_diagnostics={
            "official_source_ratio": 0.1,
            "pipeline_summary": "取数 -> 清洗 -> 分析",
            "pipeline_stages": [],
        },
        entity_graph=ResearchEntityGraphOut(),
    )

    readiness = research_service._build_report_readiness(report)
    guarded = research_service._apply_report_readiness_guardrails(
        report.model_copy(update={"report_readiness": readiness})
    )

    assert guarded.report_title == "华东｜政务云：账户优先级与推进路径"
    assert "待补证研判" not in guarded.report_title
    assert "候选推进版" not in guarded.report_title
    assert "待核验" in guarded.executive_summary or "候选推进" in guarded.executive_summary
