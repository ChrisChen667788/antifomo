from __future__ import annotations

import uuid

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.db.base import Base
from app.models import User
from app.models.research_entities import ResearchReportVersion, ResearchTrackingTopic
from app.schemas.research import ResearchJobCreateRequest
from app.services import research_job_store
from app.services.research_conversation_service import (
    add_research_conversation_message,
    create_research_conversation,
)


def _new_session() -> Session:
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    return session_factory()


def test_research_conversation_bootstrap_and_followup() -> None:
    db = _new_session()
    settings = get_settings()
    try:
        user = User(id=settings.single_user_id, name="demo")
        db.add(user)
        db.flush()

        topic = ResearchTrackingTopic(
            user_id=settings.single_user_id,
            name="上海 AI 浏览器",
            keyword="AI 浏览器",
            research_focus="长三角区域，重点关注甲方、伙伴和预算节奏",
        )
        db.add(topic)
        db.flush()

        report_payload = {
            "keyword": "AI 浏览器",
            "executive_summary": "建议先跟进长三角区域的甲方试点和招标时间窗。",
            "target_accounts": ["上海数据集团", "某市政数局"],
            "budget_signals": ["Q2 预算已启动", "试点项目进入立项阶段"],
            "tender_timeline": ["4 月完成需求澄清", "6 月前后可能发招标"],
            "sources": [
                {
                    "title": "上海数据集团公开公告",
                    "url": "https://example.com/shanghai-data",
                    "snippet": "披露 AI 浏览器试点和预算安排",
                    "source_type": "policy",
                    "source_tier": "official",
                }
            ],
            "query_plan": ["继续验证预算节点", "补齐甲方联系人"],
        }
        db.add(
            ResearchReportVersion(
                topic_id=topic.id,
                report_title="AI 浏览器专题首版",
                report_payload=report_payload,
                source_count=1,
                evidence_density="medium",
                source_quality="high",
            )
        )
        db.commit()

        conversation = create_research_conversation(
            db,
            user_id=settings.single_user_id,
            title="AI 浏览器追问",
            topic_id=topic.id,
        )

        assert conversation["topic_id"] == str(topic.id)
        assert len(conversation["messages"]) == 1
        assert "当前判断" in conversation["messages"][0]["content"]

        updated = add_research_conversation_message(
            db,
            user_id=settings.single_user_id,
            conversation_id=uuid.UUID(conversation["id"]),
            content="最近的预算和时间节点是什么？",
        )

        assert updated is not None
        assert len(updated["messages"]) == 3
        assert updated["messages"][-1]["role"] == "assistant"
        assert "预算" in updated["messages"][-1]["content"] or "时间" in updated["messages"][-1]["content"]
        assert updated["messages"][-1]["payload"]["source_links"][0]["url"] == "https://example.com/shanghai-data"
    finally:
        db.close()


def test_research_job_timeline_tracks_stage_progress(monkeypatch) -> None:
    settings = get_settings()
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)

    with session_factory() as db:
        db.add(User(id=settings.single_user_id, name="demo"))
        db.commit()

    monkeypatch.setattr(research_job_store, "SessionLocal", session_factory)
    monkeypatch.setattr(research_job_store, "_JOBS_BACKFILL_ATTEMPTED", True)

    payload = ResearchJobCreateRequest(
        keyword="A2A 协议",
        research_focus="关注浏览器厂商与 agent 协议落地",
        output_language="zh-CN",
        include_wechat=True,
        max_sources=12,
        deep_research=True,
        research_mode="deep",
    )

    job = research_job_store.create_research_job(payload)
    updated = research_job_store.update_research_job(
        str(job.id),
        status="running",
        progress_percent=42,
        stage_key="search",
        stage_label="正在检索公开网页与招采来源",
        message="已经命中官方站点和行业媒体",
    )
    assert updated is not None

    timeline = research_job_store.get_research_job_timeline(str(job.id))
    assert timeline is not None
    assert len(timeline) >= 2
    assert timeline[0]["stage_key"] == "queued"
    assert timeline[-1]["stage_key"] == "search"
    assert timeline[-1]["progress_percent"] == 42
    assert "行业媒体" in timeline[-1]["message"]
