from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models.entities import KnowledgeEntry, User
from app.models.research_entities import (
    ResearchReportVersion,
    ResearchTrackingTopic,
    ResearchWatchlist,
    ResearchWatchlistChangeEvent,
)
from app.schemas.research import ResearchActionCardOut, ResearchReportDocument
from app.services.knowledge_intelligence_service import (
    _canonicalize_account_name,
    apply_review_queue_resolutions,
    backfill_research_knowledge_intelligence,
    build_knowledge_commercial_dashboard,
    build_report_knowledge_intelligence,
    build_research_report_metadata,
    get_knowledge_account_detail,
    list_knowledge_accounts,
    list_knowledge_opportunities,
    update_review_queue_resolution,
)


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def _sample_report() -> ResearchReportDocument:
    return ResearchReportDocument(
        keyword="长三角 AI 文旅商机",
        research_focus="关注预算、甲方、部门和公开联系人",
        output_language="zh-CN",
        research_mode="deep",
        report_title="长三角｜AI 文旅：预算窗口与进入路径",
        executive_summary="围绕百联集团与区域文旅集团形成首批高价值目标名单。",
        consulting_angle="先围绕预算窗口、部门映射和生态伙伴形成销售推进路径。",
        sections=[],
        target_accounts=["百联集团", "上海文旅集团"],
        top_target_accounts=[
            {
                "name": "百联集团",
                "score": 82,
                "reasoning": "已有公开场景、数字化和预算信号。",
                "entity_mode": "instance",
                "score_breakdown": [],
                "evidence_links": [
                    {
                        "title": "百联集团官网",
                        "url": "https://www.bailian.com/",
                        "source_label": "官网",
                        "source_tier": "official",
                        "anchor_text": "数字化",
                    }
                ],
            }
        ],
        pending_target_candidates=[],
        target_departments=["数字化部", "采购中心"],
        public_contact_channels=["官网联系我们", "IR 邮箱"],
        account_team_signals=["区域团队近期推进文旅与商圈类项目"],
        budget_signals=["2026 年有平台统建与应用试点预算"],
        project_distribution=["上海与无锡双区域观察"],
        strategic_directions=["先从导览、客服和商圈运营切入"],
        tender_timeline=["未来 1-2 个季度是关键预算窗口"],
        leadership_focus=["领导关注 AI 提升运营效率与消费体验"],
        ecosystem_partners=["腾讯云", "华为云"],
        top_ecosystem_partners=[],
        pending_partner_candidates=[],
        competitor_profiles=["火山引擎"],
        top_competitors=[],
        pending_competitor_candidates=[],
        benchmark_cases=["某头部商圈集团数字导览项目"],
        flagship_products=["AI 导览", "智能客服"],
        key_people=[],
        five_year_outlook=["文旅行业会从单点试点走向平台统建"],
        client_peer_moves=["同类集团开始评估大模型导览和会员运营"],
        winner_peer_moves=[],
        competition_analysis=["云厂商与集成商都在抢占入口"],
        source_count=8,
        evidence_density="high",
        source_quality="high",
        query_plan=["长三角 AI 文旅 预算", "site:gov.cn 文旅 AI 采购"],
        sources=[
            {
                "title": "百联集团官网",
                "url": "https://www.bailian.com/",
                "domain": "bailian.com",
                "snippet": "数字化升级",
                "search_query": "百联 AI",
                "source_type": "company",
                "content_status": "ready",
                "source_label": "官网",
                "source_tier": "official",
            }
        ],
        source_diagnostics={
            "enabled_source_labels": ["官网", "政策"],
            "matched_source_labels": ["官网", "政策"],
            "scope_regions": ["长三角"],
            "scope_industries": ["文旅"],
            "scope_clients": ["百联集团"],
            "source_type_counts": {"company": 3},
            "source_tier_counts": {"official": 3, "media": 2},
            "adapter_hit_count": 2,
            "search_hit_count": 8,
            "recency_window_years": 5,
            "filtered_old_source_count": 1,
            "filtered_region_conflict_count": 0,
            "retained_source_count": 8,
            "strict_topic_source_count": 6,
            "topic_anchor_terms": ["AI", "文旅"],
            "matched_theme_labels": ["预算", "采购"],
            "retrieval_quality": "high",
            "evidence_mode": "strong",
            "evidence_mode_label": "强证据",
            "strict_match_ratio": 0.72,
            "official_source_ratio": 0.38,
            "unique_domain_count": 6,
            "normalized_entity_count": 5,
            "normalized_target_count": 2,
            "normalized_competitor_count": 1,
            "normalized_partner_count": 2,
            "expansion_triggered": False,
            "corrective_triggered": False,
            "candidate_profile_companies": [],
            "candidate_profile_hit_count": 0,
            "candidate_profile_official_hit_count": 0,
            "candidate_profile_source_labels": [],
            "strategy_model_used": True,
            "strategy_scope_summary": "围绕长三角文旅集团、预算与采购窗口展开。",
            "strategy_query_expansion_count": 2,
            "strategy_exclusion_terms": [],
            "pipeline_summary": "取数 -> 清洗 -> 分析",
            "pipeline_stages": [
                {"key": "fetch", "label": "取数", "value": 8, "summary": "8 条有效来源"},
                {"key": "clean", "label": "清洗", "value": 6, "summary": "6 条高相关来源"},
                {"key": "analyze", "label": "分析", "value": 4, "summary": "4 条高价值判断"},
            ],
        },
        entity_graph={"entities": [], "target_entities": [], "competitor_entities": [], "partner_entities": []},
    )


def test_build_report_knowledge_intelligence_emits_accounts_and_opportunities() -> None:
    report = _sample_report()
    cards = [
        ResearchActionCardOut(
            action_type="account_plan",
            priority="high",
            title="百联集团建联行动卡",
            summary="优先推进百联集团预算与部门映射。",
            recommended_steps=["先联系数字化部并确认预算归口。"],
            evidence=["官网与公开预算线索"],
            target_persona="销售经理",
            execution_window="未来两周",
            deliverable="会前简报",
        )
    ]

    intelligence = build_report_knowledge_intelligence(report, action_cards=cards)

    assert intelligence["confidence"]["score"] >= 70
    assert intelligence["accounts"]
    assert intelligence["accounts"][0]["name"] == "百联集团"
    assert intelligence["opportunities"]
    assert intelligence["opportunities"][0]["account_name"] == "百联集团"
    assert intelligence["benchmark"]["cases"]


def test_build_report_knowledge_intelligence_productizes_action_fields() -> None:
    report = _sample_report()
    report.budget_signals = [
        "[Image 1](http://example.com/a.png)",
        "2026 年平台统建与应用试点预算",
    ]
    report.client_peer_moves = [
        "优先核验公开触达入口：百联集团：优先核验官网“联系我们”、商务合作入口、采购公告联系人和投资者关系邮箱。"
    ]
    report.benchmark_cases = [
        "某头部商圈集团数字导览项目；官网/公开入口 https://example.com/case"
    ]
    cards = [
        ResearchActionCardOut(
            action_type="account_plan",
            priority="high",
            title="百联集团建联行动卡",
            summary="优先推进百联集团预算与部门映射。",
            recommended_steps=[
                "短期（1-2周）：优先围绕 百联集团 建立首轮名单，先确认业务牵头人与信息化接口人。；优先核验公开触达入口：百联集团：优先核验官网“联系我们”、商务合作入口、采购公告联系人和投资者关系邮箱。"
            ],
            evidence=["官网与公开预算线索"],
            target_persona="销售经理",
            execution_window="未来两周",
            deliverable="会前简报",
        )
    ]

    intelligence = build_report_knowledge_intelligence(report, action_cards=cards)
    account = next(item for item in intelligence["accounts"] if item["name"] == "百联集团")
    opportunity = intelligence["opportunities"][0]

    assert "公开触达入口" not in account["next_best_action"]
    assert "http" not in account["next_best_action"]
    assert "；" not in account["next_best_action"]
    assert "[Image" not in "".join(account["why_now"])
    assert "http" not in "".join(account["why_now"])
    assert "官网/公开入口" not in "".join(account["benchmark_cases"])
    assert "http" not in str(opportunity["benchmark_case"])


def test_canonicalize_account_name_drops_phrase_like_non_org_candidates() -> None:
    assert _canonicalize_account_name("围绕预算窗口与进入路径", role="target") == ""
    assert _canonicalize_account_name("内容及服务", role="target") == ""
    assert _canonicalize_account_name("百联集团", role="target") == "百联集团"


def test_backfill_and_account_aggregation() -> None:
    db = _new_session()
    try:
        settings = get_settings()
        user = User(id=uuid.UUID(str(settings.single_user_id)), name="demo")
        db.add(user)
        db.flush()

        report = _sample_report()
        metadata = build_research_report_metadata(report, action_cards=[])
        metadata.pop("commercial_intelligence", None)
        entry = KnowledgeEntry(
            user_id=user.id,
            title=report.report_title,
            content="demo",
            source_domain="research.report",
            metadata_payload=metadata,
        )
        db.add(entry)
        watchlist = ResearchWatchlist(
            user_id=user.id,
            name="百联集团预算观察",
            watch_type="company",
            query="百联集团",
            alert_level="high",
            status="active",
        )
        db.add(watchlist)
        db.flush()
        db.add(
            ResearchWatchlistChangeEvent(
                watchlist_id=watchlist.id,
                change_type="risk",
                summary="百联集团预算窗口出现新增变化",
                payload={
                    "accounts": ["百联集团"],
                    "why_now": ["预算窗口需要优先核验"],
                    "top_budget_probability": 78,
                },
                severity="high",
            )
        )
        db.commit()

        result = backfill_research_knowledge_intelligence(db)
        assert result["updated"] == 1

        accounts = list_knowledge_accounts(db)
        assert accounts
        assert accounts[0]["name"] == "百联集团"

        detail = get_knowledge_account_detail(db, accounts[0]["slug"])
        assert detail is not None
        assert detail["opportunities"]
        assert detail["account_plan"]["objective"]
        assert detail["stakeholder_map"]
        assert detail["close_plan"]
        assert detail["pipeline_risks"]

        opportunities = list_knowledge_opportunities(db)
        assert opportunities
        assert opportunities[0]["account_name"] == "百联集团"

        dashboard = build_knowledge_commercial_dashboard(db)
        assert dashboard["role_views"]
        assert dashboard["top_alerts"]
    finally:
        db.close()


def test_backfill_rewrites_stored_report_entities_for_entries_and_versions() -> None:
    db = _new_session()
    try:
        settings = get_settings()
        user = User(id=uuid.UUID(str(settings.single_user_id)), name="demo")
        db.add(user)
        db.flush()

        report = _sample_report()
        report.target_accounts = ["百联"]
        report.top_target_accounts = [
            {
                "name": "百联",
                "score": 82,
                "reasoning": "已有官网与预算线索。",
                "entity_mode": "instance",
                "score_breakdown": [],
                "evidence_links": [
                    {
                        "title": "百联集团官网",
                        "url": "https://www.bailian.com/",
                        "source_label": "百联官网",
                        "source_tier": "official",
                    }
                ],
            }
        ]
        report.source_diagnostics.scope_clients = ["百联"]
        metadata = build_research_report_metadata(report, action_cards=[])
        entry = KnowledgeEntry(
            user_id=user.id,
            title=report.report_title,
            content="demo",
            source_domain="research.report",
            metadata_payload=metadata,
        )
        db.add(entry)
        topic = ResearchTrackingTopic(
            user_id=user.id,
            name="百联专题",
            keyword="百联",
            research_focus="关注预算与数字化建设",
        )
        db.add(topic)
        db.flush()

        version = ResearchReportVersion(
            topic_id=topic.id,
            knowledge_entry_id=entry.id,
            report_title=report.report_title,
            report_payload=metadata["report"],
            action_cards_payload=metadata["action_cards"],
            source_count=report.source_count,
            evidence_density=report.evidence_density,
            source_quality=report.source_quality,
            new_targets=["百联"],
            new_competitors=[],
            new_budget_signals=[],
        )
        db.add(version)
        db.commit()

        result = backfill_research_knowledge_intelligence(db)
        db.refresh(entry)
        db.refresh(version)

        assert result["updated"] == 1
        assert result["updated_versions"] == 1
        assert entry.metadata_payload["report"]["target_accounts"] == ["百联集团"]
        assert version.report_payload["target_accounts"] == ["百联集团"]
        assert version.new_targets == ["百联集团"]
    finally:
        db.close()


def test_backfill_research_knowledge_intelligence_supports_checkpoint_resume(tmp_path) -> None:
    db = _new_session()
    try:
        checkpoint_path = tmp_path / "research-report-backfill.json"
        settings = get_settings()
        user = User(id=uuid.UUID(str(settings.single_user_id)), name="demo")
        db.add(user)
        db.flush()

        topic = ResearchTrackingTopic(
            user_id=user.id,
            name="百联专题",
            keyword="百联",
            research_focus="关注预算与数字化建设",
        )
        db.add(topic)
        db.flush()

        first_report = _sample_report()
        first_report.target_accounts = ["百联"]
        first_report.top_target_accounts = [
            {
                "name": "百联",
                "score": 82,
                "reasoning": "已有官网与预算线索。",
                "entity_mode": "instance",
                "score_breakdown": [],
                "evidence_links": [
                    {
                        "title": "百联集团官网",
                        "url": "https://www.bailian.com/",
                        "source_label": "百联官网",
                        "source_tier": "official",
                    }
                ],
            }
        ]
        first_report.source_diagnostics.scope_clients = ["百联"]
        first_metadata = build_research_report_metadata(first_report, action_cards=[])
        first_entry = KnowledgeEntry(
            user_id=user.id,
            title=first_report.report_title,
            content="demo-1",
            source_domain="research.report",
            metadata_payload=first_metadata,
        )
        db.add(first_entry)
        db.flush()

        version = ResearchReportVersion(
            topic_id=topic.id,
            knowledge_entry_id=first_entry.id,
            report_title=first_report.report_title,
            report_payload=first_metadata["report"],
            action_cards_payload=first_metadata["action_cards"],
            source_count=first_report.source_count,
            evidence_density=first_report.evidence_density,
            source_quality=first_report.source_quality,
            new_targets=["百联"],
            new_competitors=[],
            new_budget_signals=[],
        )
        db.add(version)

        second_report = _sample_report()
        second_report.report_title = "长三角｜AI 文旅：第二批回填"
        second_report.target_accounts = ["百联"]
        second_report.top_target_accounts = [
            {
                "name": "百联",
                "score": 76,
                "reasoning": "仍是同一组织的旧别名。",
                "entity_mode": "instance",
                "score_breakdown": [],
                "evidence_links": [
                    {
                        "title": "百联集团官网",
                        "url": "https://www.bailian.com/about",
                        "source_label": "百联官网",
                        "source_tier": "official",
                    }
                ],
            }
        ]
        second_report.source_diagnostics.scope_clients = ["百联"]
        second_entry = KnowledgeEntry(
            user_id=user.id,
            title=second_report.report_title,
            content="demo-2",
            source_domain="research.report",
            metadata_payload=build_research_report_metadata(second_report, action_cards=[]),
        )
        db.add(second_entry)
        db.commit()

        partial_result = backfill_research_knowledge_intelligence(
            db,
            batch_size=1,
            commit_every=2,
            checkpoint_path=checkpoint_path,
            max_rows=1,
        )
        checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

        assert partial_result["completed"] is False
        assert partial_result["stage"] == "entries"
        assert partial_result["processed_this_run"] == 1
        assert partial_result["commits"] == 1
        assert checkpoint["entries"]["scanned"] == 1
        assert checkpoint["entries"]["updated"] == 1
        assert checkpoint["entries"]["last_id"]

        final_result = backfill_research_knowledge_intelligence(
            db,
            batch_size=1,
            commit_every=2,
            checkpoint_path=checkpoint_path,
            resume=True,
        )
        db.refresh(first_entry)
        db.refresh(second_entry)
        db.refresh(version)
        final_checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))

        assert final_result["completed"] is True
        assert final_result["scanned"] == 2
        assert final_result["updated"] == 2
        assert final_result["scanned_versions"] == 1
        assert final_result["updated_versions"] == 1
        assert final_result["commits"] == 3
        assert first_entry.metadata_payload["report"]["target_accounts"] == ["百联集团"]
        assert second_entry.metadata_payload["report"]["target_accounts"] == ["百联集团"]
        assert version.report_payload["target_accounts"] == ["百联集团"]
        assert final_checkpoint["stage"] == "done"
        assert final_checkpoint["completed_at"]
    finally:
        db.close()


def test_build_report_knowledge_intelligence_filters_low_signal_and_canonicalizes_accounts() -> None:
    report = _sample_report()
    report.keyword = "2026年AI漫剧行业头部公司调研"
    report.top_target_accounts = [
        {
            "name": "上海市文旅局：AI漫剧风向已定：仿真人、互动剧、游戏IP成三大风口",
            "score": 74,
            "reasoning": "官方文旅口径已出现 AI 漫剧大会与行业方向。",
            "evidence_links": [
                {
                    "title": "AI如何重塑微短剧生产？2026上海微短剧大会在沪举行_文旅要闻_上海市文化和旅游局",
                    "url": "https://whlyj.sh.gov.cn/wlyw/20260310/example.html",
                    "source_label": "中国政府网政策/讲话",
                    "source_tier": "official",
                }
            ],
        },
        {
            "name": "科技数码",
            "score": 75,
            "reasoning": "该线索实际来自站内官方主页，原始实体抽取过泛。",
            "evidence_links": [
                {
                    "title": "哔哩哔哩 (゜-゜)つロ 干杯~-bilibili",
                    "url": "https://www.bilibili.com/",
                    "source_label": "哔哩哔哩官网",
                    "source_tier": "official",
                }
            ],
        },
        {
            "name": "微短剧服务中心",
            "score": 68,
            "reasoning": "媒体稿中的栏目词，不应作为账户保留。",
            "evidence_links": [
                {
                    "title": "AI漫剧风向已定：仿真人、互动剧、游戏IP成三大风口_技术_内容_行业",
                    "url": "https://www.sohu.com/a/example",
                    "source_label": "互联网公开网页",
                    "source_tier": "media",
                }
            ],
        },
    ]

    intelligence = build_report_knowledge_intelligence(report, action_cards=[])
    account_names = [item["name"] for item in intelligence["accounts"] if item["role"] == "target"]

    assert "上海市文化和旅游局" in account_names
    assert "哔哩哔哩" in account_names
    assert "微短剧服务中心" not in account_names
    assert "科技数码" not in account_names


def test_account_aggregation_merges_aliases_and_dedupes_opportunities() -> None:
    db = _new_session()
    try:
        settings = get_settings()
        user = User(id=uuid.UUID(str(settings.single_user_id)), name="demo")
        db.add(user)
        db.flush()

        base_card = ResearchActionCardOut(
            action_type="account_plan",
            priority="high",
            title="哔哩哔哩建联行动卡",
            summary="统一推进内容工具链采购线索。",
            recommended_steps=["先联系商业化团队并确认预算归口。"],
            evidence=["官网与行业公开线索"],
            target_persona="销售经理",
            execution_window="未来两周",
            deliverable="会前简报",
        )
        for title in ("哔哩哔哩（粤港澳区域业务/创新中心）：重点跟进其AIGC内容生成工具链的采购与内部管线改造项目。", "哔哩哔哩（华东商业化团队）：重点跟进其AIGC内容生成工具链的采购与内部管线改造项目。"):
            report = _sample_report()
            report.keyword = "全国AI漫剧行业头部机构及工具链采购"
            report.report_title = f"{title} 研判"
            report.top_target_accounts = []
            report.target_accounts = [title]
            report.top_ecosystem_partners = []
            report.ecosystem_partners = []
            report.top_competitors = []
            report.competitor_profiles = []
            metadata = build_research_report_metadata(report, action_cards=[base_card])
            db.add(
                KnowledgeEntry(
                    user_id=user.id,
                    title=report.report_title,
                    content="demo",
                    source_domain="research.report",
                    metadata_payload=metadata,
                )
            )
        db.commit()

        accounts = list_knowledge_accounts(db, limit=10)
        bilibili = next(item for item in accounts if item["name"] == "哔哩哔哩")
        assert bilibili["report_count"] == 2

        opportunities = list_knowledge_opportunities(db, account_slug=bilibili["slug"], limit=10)
        assert len(opportunities) == 1
        assert opportunities[0]["account_name"] == "哔哩哔哩"
    finally:
        db.close()


def test_account_detail_merges_watchlist_timeline() -> None:
    db = _new_session()
    try:
        settings = get_settings()
        user = User(id=uuid.UUID(str(settings.single_user_id)), name="demo")
        db.add(user)
        db.flush()

        report = _sample_report()
        db.add(
            KnowledgeEntry(
                user_id=user.id,
                title=report.report_title,
                content="demo",
                source_domain="research.report",
                metadata_payload=build_research_report_metadata(report, action_cards=[]),
            )
        )
        db.flush()

        watchlist = ResearchWatchlist(
            user_id=user.id,
            name="百联集团预算观察",
            watch_type="company",
            query="百联集团 AI 文旅",
            alert_level="high",
            schedule="daily",
            status="active",
        )
        db.add(watchlist)
        db.flush()
        db.add(
            ResearchWatchlistChangeEvent(
                watchlist_id=watchlist.id,
                change_type="risk",
                summary="新增预算/招采线索 1 条",
                payload={
                    "accounts": ["百联集团"],
                    "why_now": ["预算窗口已进入下一轮论证"],
                    "top_budget_probability": 78,
                },
                severity="high",
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

        accounts = list_knowledge_accounts(db)
        detail = get_knowledge_account_detail(db, accounts[0]["slug"])

        assert detail is not None
        assert detail["timeline"]
        assert any(item["kind"] == "watchlist" for item in detail["timeline"])
        assert any(item["kind"] == "opportunity" for item in detail["timeline"])
    finally:
        db.close()


def test_review_queue_resolution_filters_resolved_items_from_dashboard() -> None:
    payload = {
        "kind": "research_report",
        "report": {
            "review_queue": [
                {
                    "id": "review-1",
                    "section_title": "预算与投资信号",
                    "severity": "high",
                    "summary": "预算窗口存在冲突表述。",
                    "recommended_action": "优先核验预算归口。",
                    "evidence_links": [],
                }
            ]
        },
    }

    resolved_payload = update_review_queue_resolution(
        payload,
        review_id="review-1",
        action="resolved",
        note="人工已完成核验",
    )
    resolved_queue = apply_review_queue_resolutions(resolved_payload)["report"]["review_queue"]
    assert resolved_queue[0]["resolution_status"] == "resolved"
    assert resolved_queue[0]["resolution_note"] == "人工已完成核验"

    deferred_payload = update_review_queue_resolution(
        payload,
        review_id="review-1",
        action="deferred",
        note="等待下轮补证",
    )
    deferred_queue = apply_review_queue_resolutions(deferred_payload)["report"]["review_queue"]
    assert deferred_queue[0]["resolution_status"] == "deferred"

    db = _new_session()
    try:
        settings = get_settings()
        user = User(id=uuid.UUID(str(settings.single_user_id)), name="demo")
        db.add(user)
        db.flush()

        db.add_all(
            [
                KnowledgeEntry(
                    user_id=user.id,
                    title="已核验冲突项",
                    content="demo",
                    source_domain="research.report",
                    metadata_payload=resolved_payload,
                ),
                KnowledgeEntry(
                    user_id=user.id,
                    title="延后冲突项",
                    content="demo",
                    source_domain="research.report",
                    metadata_payload=deferred_payload,
                ),
            ]
        )
        db.commit()

        dashboard = build_knowledge_commercial_dashboard(db)
        assert len(dashboard["review_queue"]) == 1
        assert dashboard["review_queue"][0]["id"] == "review-1"
        assert dashboard["review_queue"][0]["resolution_status"] == "deferred"
    finally:
        db.close()
