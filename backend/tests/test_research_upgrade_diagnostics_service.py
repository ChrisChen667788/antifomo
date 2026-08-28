from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.research import ResearchUpgradeDiagnosticsRequest, ResearchUpgradeSourceInput
from app.services.research_upgrade_diagnostics_service import build_research_upgrade_diagnostics


def test_default_upgrade_diagnostics_covers_15_roadmap_rounds() -> None:
    payload = build_research_upgrade_diagnostics(current_year=2026)

    assert payload["roadmap_version"] == "tencent-url-and-research-upgrade-plan-2026-06"
    assert payload["status"] == "ready"
    assert payload["readiness_score"] >= 80
    assert len(payload["roadmap_rounds"]) == 15
    assert [item["index"] for item in payload["roadmap_rounds"]] == list(range(1, 16))
    assert len(payload["query_plan"]) >= 5
    assert payload["url_first_diagnostics"]["strict_wechat_path_count"] == 1
    assert payload["retrieval_evaluation"]["filtered_old_source_count"] == 1
    assert payload["retrieval_evaluation"]["accepted_count"] >= 2
    assert payload["lightweight_graph"]["nodes"]
    assert {panel["role"] for panel in payload["expert_panels"]} == {
        "buyer_value",
        "competitor_threat",
        "partner_influence",
        "tender_cadence",
    }
    assert payload["source_type_contributions"]
    assert all(item["passed"] for item in payload["section_evidence_quotas"])


def test_upgrade_diagnostics_blocks_weak_payload_before_generation() -> None:
    request = ResearchUpgradeDiagnosticsRequest(
        keyword="上海医疗 AI",
        research_focus="预算 采购 甲方",
        sources=[
            ResearchUpgradeSourceInput(
                title="无链接旧行业综述",
                url="not-a-url",
                snippet="2016 年转载资料，没有采购人和预算证据。",
                source_type="industry_media",
                source_tier="media",
                published_year=2016,
            )
        ],
        sections=[
            {
                "title": "预算与采购信号",
                "summary": "仅有旧综述。",
                "evidence_urls": [],
            }
        ],
    )

    payload = build_research_upgrade_diagnostics(request, current_year=2026)

    assert payload["status"] == "blocked"
    assert payload["url_first_diagnostics"]["ocr_fallback_required"] is True
    assert payload["retrieval_evaluation"]["accepted_count"] == 0
    assert payload["retrieval_evaluation"]["filtered_old_source_count"] == 1
    assert payload["section_evidence_quotas"][0]["passed"] is False
    assert any(action["priority"] == "high" for action in payload["fallback_actions"])


def test_upgrade_diagnostics_api_preview_and_post_are_available() -> None:
    with TestClient(app) as client:
        preview = client.get("/api/research/upgrade-diagnostics/preview")
        custom = client.post(
            "/api/research/upgrade-diagnostics/preview",
            json={
                "keyword": "长三角政务 AI",
                "research_focus": "政策 采购 伙伴",
                "sources": [
                    {
                        "title": "江苏公共资源交易平台政务 AI 采购公告",
                        "url": "https://www.jszbtb.com/procurement/20260601-ai.html",
                        "snippet": "公告包含采购人、预算、实施和验收要求。",
                        "source_type": "public_tender",
                        "source_tier": "official",
                        "published_year": 2026,
                    }
                ],
                "sections": [
                    {
                        "title": "预算与采购信号",
                        "summary": "采购公告已出现。",
                        "evidence_urls": ["https://www.jszbtb.com/procurement/20260601-ai.html"],
                    }
                ],
                "previous_snapshot": {"budget_signal": "无"},
                "current_snapshot": {"budget_signal": "采购公告已出现"},
            },
        )

    assert preview.status_code == 200
    preview_payload = preview.json()
    assert len(preview_payload["roadmap_rounds"]) == 15
    assert preview_payload["diagnostics"] if "diagnostics" in preview_payload else True

    assert custom.status_code == 200
    custom_payload = custom.json()
    assert custom_payload["keyword"] == "长三角政务 AI"
    assert custom_payload["retrieval_evaluation"]["accepted_count"] == 1
    assert custom_payload["field_diffs"][0]["status"] == "changed"
