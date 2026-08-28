from __future__ import annotations

from collections.abc import Generator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.services import daily_brief_service


@pytest.fixture()
def api_client(monkeypatch: pytest.MonkeyPatch) -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)

    def override_get_db() -> Generator[Session, None, None]:
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    monkeypatch.setattr(
        daily_brief_service,
        "_generate_audio",
        lambda snapshot, script: ("unavailable", ""),
    )
    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.pop(get_db, None)
        engine.dispose()


def assert_ok(response, *, label: str) -> Any:
    assert response.status_code < 500, f"{label} returned server error: {response.status_code} {response.text}"
    assert response.status_code < 400, f"{label} failed: {response.status_code} {response.text}"
    payload = response.json()
    assert isinstance(payload, (dict, list)), f"{label} did not return JSON"
    return payload


def test_core_page_backing_apis_are_available(api_client: TestClient) -> None:
    checks = [
        ("system health", "GET", "/healthz"),
        ("feed items", "GET", "/api/items?limit=5"),
        ("knowledge list", "GET", "/api/knowledge?limit=5"),
        ("knowledge dashboard", "GET", "/api/knowledge/dashboard"),
        ("knowledge accounts", "GET", "/api/knowledge/accounts"),
        ("collector status", "GET", "/api/collector/status"),
        ("collector daily summary", "GET", "/api/collector/daily-summary?hours=24&limit=3"),
        ("research source settings", "GET", "/api/research/source-settings"),
        ("research workspace", "GET", "/api/research/workspace"),
        ("research daily brief", "GET", "/api/research/daily-brief"),
        ("research retrieval status", "GET", "/api/research/retrieval-index/status"),
        ("research experience metrics", "GET", "/api/research/experience/metrics"),
        ("research experience readiness", "GET", "/api/research/experience/readiness"),
        ("research watchlists", "GET", "/api/research/watchlists"),
    ]

    for label, method, path in checks:
        response = api_client.request(method, path)
        payload = assert_ok(response, label=label)
        assert payload is not None


def test_research_workspace_writes_remain_stable(api_client: TestClient) -> None:
    topic = assert_ok(
        api_client.post(
            "/api/research/workspace/topics",
            json={
                "name": "稳定性基准专题",
                "keyword": "2026 上海 AI 商机",
                "research_focus": "预算、甲方、落地场景",
                "perspective": "bidding",
                "region_filter": "上海",
                "industry_filter": "AI",
                "notes": "API smoke baseline",
            },
        ),
        label="create research topic",
    )
    topic_id = topic["id"]

    assert_ok(api_client.get(f"/api/research/workspace/topics/{topic_id}/versions"), label="topic versions")
    timeline = api_client.get(f"/api/research/workspace/topics/{topic_id}/timeline")
    assert timeline.status_code < 500, timeline.text
    assert timeline.status_code < 400, timeline.text
    assert isinstance(timeline.json(), list)

    watchlist = assert_ok(
        api_client.post(
            "/api/research/watchlists",
            json={
                "name": "稳定性基准监控",
                "query": "2026 上海 AI 商机",
                "tracking_topic_id": topic_id,
                "research_focus": "预算、甲方、落地场景",
                "perspective": "bidding",
                "region_filter": "上海",
                "industry_filter": "AI",
                "alert_level": "medium",
                "schedule": "manual",
            },
        ),
        label="create research watchlist",
    )
    watchlist_id = watchlist["id"]
    changes = api_client.get(f"/api/research/watchlists/{watchlist_id}/changes")
    assert changes.status_code < 500, changes.text
    assert changes.status_code < 400, changes.text
    assert isinstance(changes.json(), list)

    snapshot = assert_ok(
        api_client.post(
            "/api/research/workspace/compare-snapshots",
            json={
                "name": "稳定性基准对比",
                "query": "2026 上海 AI 商机",
                "region_filter": "上海",
                "industry_filter": "AI",
                "role_filter": "all",
                "tracking_topic_id": topic_id,
                "summary": "用于验证对比保存链路可用。",
                "rows": [
                    {
                        "name": "上海市数字化部门",
                        "role": "甲方",
                        "evidence": "smoke",
                        "score": 1,
                    }
                ],
                "metadata_payload": {"smoke": True},
            },
        ),
        label="create compare snapshot",
    )
    assert_ok(api_client.get(f"/api/research/workspace/compare-snapshots/{snapshot['id']}"), label="compare snapshot detail")

    archive = assert_ok(
        api_client.post(
            "/api/research/workspace/markdown-archives",
            json={
                "archive_kind": "compare_markdown",
                "name": "稳定性基准归档",
                "filename": "stability-baseline.md",
                "query": "2026 上海 AI 商机",
                "region_filter": "上海",
                "industry_filter": "AI",
                "tracking_topic_id": topic_id,
                "compare_snapshot_id": snapshot["id"],
                "summary": "用于验证归档保存链路可用。",
                "content": "# 稳定性基准\n\n用于 API smoke。",
                "metadata_payload": {"smoke": True},
            },
        ),
        label="create markdown archive",
    )
    assert_ok(api_client.get(f"/api/research/workspace/markdown-archives/{archive['id']}"), label="markdown archive detail")


def test_session_lifecycle_api_is_available(api_client: TestClient) -> None:
    settings = get_settings()
    session = assert_ok(
        api_client.post(
            "/api/sessions/start",
            json={
                "goal_text": "稳定性基准测试",
                "duration_minutes": 25,
                "output_language": "zh-CN",
            },
        ),
        label="start focus session",
    )
    assert session["user_id"] == str(settings.single_user_id)

    latest = assert_ok(api_client.get("/api/sessions/latest"), label="latest focus session")
    assert latest["id"] == session["id"]

    paused = assert_ok(api_client.post(f"/api/sessions/{session['id']}/pause"), label="pause focus session")
    assert paused["session"]["status"] == "paused"

    resumed = assert_ok(api_client.post(f"/api/sessions/{session['id']}/resume"), label="resume focus session")
    assert resumed["session"]["status"] == "running"
