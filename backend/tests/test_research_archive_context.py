from __future__ import annotations

from datetime import datetime, timezone
import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models.entities import KnowledgeEntry, User
from app.schemas.research import (
    ResearchEntityGraphOut,
    ResearchFollowupContextOut,
    ResearchReportRequest,
    ResearchReportResponse,
)
from app.services import research_service


def _new_session_factory():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)


def _seed_demo_user(db: Session) -> User:
    settings = get_settings()
    user = User(
        id=settings.single_user_id,
        name="Demo User",
        email="demo@anti-fomo.local",
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _build_stored_report(*, title: str, keyword: str) -> ResearchReportResponse:
    now = datetime.now(timezone.utc)
    return ResearchReportResponse(
        keyword=keyword,
        research_focus="梳理预算窗口、组织入口和推进策略",
        output_language="zh-CN",
        research_mode="deep",
        report_title=title,
        executive_summary="历史研报显示，上海数据集团 7 月前后将启动预算复核，采购中心和数字化部门是关键入口。",
        consulting_angle="适合作为预算窗口判断和打单路径设计的历史底稿。",
        target_accounts=["上海数据集团"],
        target_departments=["采购中心", "数字化部"],
        budget_signals=["7 月启动预算复核"],
        source_count=4,
        evidence_density="high",
        source_quality="high",
        sources=[
            {
                "title": "上海数据集团公开公告",
                "url": "https://example.com/shanghai-data",
                "domain": "example.com",
                "snippet": "预算复核与需求确认窗口",
                "search_query": keyword,
                "source_type": "policy",
                "content_status": "extracted",
                "source_label": "官网",
                "source_tier": "official",
            },
            {
                "title": "上海数据集团采购计划",
                "url": "https://example.com/shanghai-data-plan",
                "domain": "example.com",
                "snippet": "采购中心将同步梳理预算安排",
                "search_query": keyword,
                "source_type": "procurement",
                "content_status": "extracted",
                "source_label": "采购公告",
                "source_tier": "official",
            },
        ],
        source_diagnostics={
            "scope_regions": ["上海"],
            "scope_industries": ["政务云"],
            "scope_clients": ["上海数据集团"],
            "official_source_ratio": 0.75,
            "strict_match_ratio": 0.8,
            "retrieval_quality": "high",
            "evidence_mode": "strong",
        },
        generated_at=now,
    )


def test_load_research_archive_context_returns_supported_stored_reports(monkeypatch) -> None:
    session_factory = _new_session_factory()
    monkeypatch.setattr(research_service, "SessionLocal", session_factory)

    with session_factory() as db:
        user = _seed_demo_user(db)
        report = _build_stored_report(title="上海数据集团预算窗口研判", keyword="上海数据集团预算窗口")
        entry = KnowledgeEntry(
            id=uuid.uuid4(),
            user_id=user.id,
            title=report.report_title,
            content="聚焦预算复核、采购中心和数字化部的切入窗口。",
            source_domain="research.report",
            metadata_payload={"report": report.model_dump(mode="json")},
            is_focus_reference=True,
        )
        db.add(entry)
        db.commit()

    items = research_service._load_research_archive_context(
        keyword="上海数据集团预算窗口",
        research_focus="判断预算复核时间节点和组织入口",
        scope_hints={"industries": ["政务云"], "prefer_company_entities": True},
        limit=3,
    )

    assert items
    assert items[0]["kind"] == "stored_report"
    assert "上海数据集团" in items[0]["supported_targets"]
    assert items[0]["official_source_ratio"] >= 0.75
    assert "上海数据集团" in str(items[0]["match_snippet"])


def test_build_followup_research_diagnostics_rebuilds_filters_and_queries() -> None:
    followup_scope_hints, diagnostics = research_service._build_followup_research_diagnostics(
        keyword="政务云预算窗口",
        report_research_focus="梳理预算窗口和组织入口",
        followup_context=ResearchFollowupContextOut(
            supplemental_context="新增范围锁定到南京市数据局和电子政务云平台。",
            supplemental_evidence="公开线索提到 2026 年采购意向、预算安排和项目建设路径。",
            supplemental_requirements="优先补甲方、预算口径和采购意向公告。",
        ),
        include_wechat=False,
        base_scope_hints={"regions": [], "industries": ["政务云"], "clients": [], "company_anchors": []},
    )

    assert diagnostics.enabled is True
    assert diagnostics.scope_rebuilt is True
    assert diagnostics.query_decomposition_applied is True
    assert "南京市数据局" in diagnostics.rebuilt_clients
    assert "政务云" in diagnostics.rebuilt_industries
    assert diagnostics.decomposition_queries
    assert any("南京市数据局" in query for query in diagnostics.decomposition_queries)
    assert followup_scope_hints.get("strategy_query_expansions")


def test_merge_scope_hints_with_archive_context_pushes_archive_targets_into_query_plan() -> None:
    base_scope_hints = {
        "regions": ["上海"],
        "industries": ["政务云"],
        "clients": [],
        "company_anchors": [],
        "strategy_query_expansions": [],
        "prefer_company_entities": False,
    }
    merged_scope_hints = research_service._merge_scope_hints_with_archive_context(
        base_scope_hints,
        [
            {
                "kind": "stored_report",
                "supported_targets": ["上海数据集团"],
                "target_departments": ["采购中心"],
                "budget_signals": ["7 月预算复核"],
                "source_count": 4,
                "official_source_ratio": 0.75,
                "retrieval_quality": "high",
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ],
        keyword="上海政务云预算窗口",
        research_focus="优先锁定具体账户和采购中心",
    )

    assert merged_scope_hints["archive_targets"] == ["上海数据集团"]
    assert "采购中心" in merged_scope_hints["archive_target_departments"]
    assert "7 月预算复核" in merged_scope_hints["archive_budget_signals"]
    queries = research_service._build_query_plan(
        "上海政务云预算窗口",
        "优先锁定具体账户和采购中心",
        False,
        scope_hints=merged_scope_hints,
        limit=24,
    )

    assert any("上海数据集团" in query and "采购中心" in query for query in queries)
    assert any("上海数据集团" in query and "预算" in query for query in queries)


def test_merge_scope_hints_with_archive_context_ignores_stale_low_support_archive_items() -> None:
    base_scope_hints = {
        "regions": ["上海"],
        "industries": ["政务云"],
        "clients": [],
        "company_anchors": [],
        "strategy_query_expansions": [],
        "prefer_company_entities": False,
    }
    merged_scope_hints = research_service._merge_scope_hints_with_archive_context(
        base_scope_hints,
        [
            {
                "kind": "stored_report",
                "supported_targets": ["上海数据集团"],
                "target_departments": ["采购中心"],
                "budget_signals": ["7 月预算复核"],
                "source_count": 2,
                "official_source_ratio": 0.3,
                "retrieval_quality": "medium",
                "updated_at": datetime(2023, 1, 1, tzinfo=timezone.utc).isoformat(),
            }
        ],
        keyword="上海政务云预算窗口",
        research_focus="优先锁定具体账户和采购中心",
    )

    assert "archive_targets" not in merged_scope_hints
    queries = research_service._build_query_plan(
        "上海政务云预算窗口",
        "优先锁定具体账户和采购中心",
        False,
        scope_hints=merged_scope_hints,
        limit=24,
    )

    assert not any("上海数据集团" in query and "采购中心" in query for query in queries)


class _FakeSourceSettings:
    enable_curated_wechat_channels = False

    @staticmethod
    def enabled_labels() -> list[str]:
        return []


class _CaptureLLM:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    def run_prompt(self, prompt_name: str, variables: dict[str, str]) -> str:
        self.calls.append((prompt_name, dict(variables)))
        if prompt_name == "research_report_outline.txt":
            return (
                '{"report_title":"上海政务云推进研判","executive_summary":"先围绕上海数据集团做预算与组织入口判断。",'
                '"consulting_angle":"适合先做范围锁定和推进路径设计。"}'
            )
        if prompt_name == "research_report.txt":
            return """
            {
              "report_title": "上海政务云推进研判",
              "executive_summary": "先围绕上海数据集团做预算与组织入口判断，再补公开采购和官网证据。",
              "consulting_angle": "适合方案设计情报和打单推进双用途。",
              "industry_brief": [],
              "key_signals": [],
              "policy_and_leadership": [],
              "commercial_opportunities": [],
              "solution_design": [],
              "sales_strategy": [],
              "bidding_strategy": [],
              "outreach_strategy": [],
              "ecosystem_strategy": [],
              "target_accounts": ["上海数据集团"],
              "target_departments": ["采购中心"],
              "public_contact_channels": [],
              "account_team_signals": [],
              "budget_signals": ["7 月预算复核"],
              "project_distribution": [],
              "strategic_directions": [],
              "tender_timeline": [],
              "leadership_focus": [],
              "ecosystem_partners": [],
              "competitor_profiles": [],
              "benchmark_cases": [],
              "flagship_products": [],
              "key_people": [],
              "five_year_outlook": [],
              "client_peer_moves": [],
              "winner_peer_moves": [],
              "competition_analysis": [],
              "risks": [],
              "next_actions": []
            }
            """
        raise AssertionError(f"unexpected prompt: {prompt_name}")


def test_generate_research_report_passes_archive_context_into_outline_and_full_prompt(monkeypatch) -> None:
    llm = _CaptureLLM()
    monkeypatch.setattr(research_service, "get_llm_service", lambda: llm)
    monkeypatch.setattr(research_service, "_apply_strategy_scope_planning", lambda **kwargs: kwargs["input_scope_hints"])
    monkeypatch.setattr(research_service, "read_research_source_settings", lambda: _FakeSourceSettings())
    monkeypatch.setattr(research_service, "collect_enabled_source_hits", lambda *args, **kwargs: (_FakeSourceSettings(), []))
    monkeypatch.setattr(research_service, "_build_query_plan", lambda *args, **kwargs: [])
    monkeypatch.setattr(research_service, "_build_expanded_query_plan", lambda *args, **kwargs: [])
    monkeypatch.setattr(research_service, "_build_corrective_query_plan", lambda *args, **kwargs: [])
    monkeypatch.setattr(research_service, "_build_company_contact_query_plan", lambda *args, **kwargs: [])
    monkeypatch.setattr(research_service, "_build_company_profile_query_plan", lambda *args, **kwargs: [])
    monkeypatch.setattr(research_service, "_build_company_team_query_plan", lambda *args, **kwargs: [])
    monkeypatch.setattr(research_service, "_build_company_seed_hits", lambda *args, **kwargs: [])
    monkeypatch.setattr(research_service, "_search_public_web", lambda *args, **kwargs: [])
    monkeypatch.setattr(research_service, "_load_research_archive_context", lambda **kwargs: [
        {
            "kind": "stored_report",
            "title": "历史上海数据集团研判",
            "match_label": "补充新证据",
            "match_snippet": "上海数据集团将在 7 月启动预算复核。",
            "summary": "历史研报已锁定预算窗口和采购中心。",
            "supported_targets": ["上海数据集团"],
            "target_departments": ["采购中心"],
            "budget_signals": ["7 月预算复核"],
            "source_count": 4,
            "official_source_ratio": 0.75,
            "score": 0.91,
        }
    ])
    monkeypatch.setattr(
        research_service,
        "_build_research_runtime",
        lambda payload: {
            "query_limit": 1,
            "adapter_per_source_limit": 1,
            "effective_max_sources": 6,
            "expanded_adapter_per_source_limit": 1,
            "enough_hit_threshold": 2,
            "expanded_selected_limit": 6,
            "search_timeout_seconds": 1,
            "search_result_limit": 1,
            "url_timeout_seconds": 1,
            "llm_timeout_seconds": 30,
            "expansion_min_sources": 6,
            "expansion_min_dimensions": 5,
            "enable_expansion": False,
            "expanded_query_limit": 1,
        },
    )
    monkeypatch.setattr(research_service, "_build_source_intelligence", lambda *args, **kwargs: {"target_accounts": ["上海数据集团"]})
    monkeypatch.setattr(research_service, "_company_convergence_is_weak", lambda **kwargs: False)
    monkeypatch.setattr(research_service, "_retrieval_quality_band", lambda **kwargs: "medium")
    monkeypatch.setattr(research_service, "_apply_topic_specific_overrides", lambda parsed, **kwargs: parsed)
    monkeypatch.setattr(research_service, "_apply_strategy_llm_refinement", lambda parsed, **kwargs: parsed)
    monkeypatch.setattr(research_service, "_rank_top_entities", lambda *args, **kwargs: ([], []))

    report = research_service.generate_research_report(
        ResearchReportRequest(
            keyword="上海政务云预算窗口",
            research_focus="优先锁定具体账户和采购中心",
            supplemental_context="新增范围集中到上海数据集团采购中心。",
            supplemental_evidence="新增证据显示 7 月预算复核后会同步确认采购安排。",
            supplemental_requirements="优先补采购中心、预算口径和官网公告。",
            include_wechat=False,
            research_mode="fast",
            max_sources=6,
        )
    )

    assert "上海" in report.report_title
    outline_call = next(call for call in llm.calls if call[0] == "research_report_outline.txt")
    full_call = next(call for call in llm.calls if call[0] == "research_report.txt")
    assert "上海数据集团" in outline_call[1]["archive_context"]
    assert "预算复核" in outline_call[1]["archive_context"]
    assert "上海数据集团" in full_call[1]["archive_context"]
    assert "预算复核" in full_call[1]["archive_context"]
    assert "二次检索摘要" in outline_call[1]["followup_diagnostics"]
    assert "采购中心" in full_call[1]["followup_diagnostics"]
