from __future__ import annotations

from app.services.research_retrieval_service import (
    build_report_retrieval_chunks,
    retrieve_report_evidence_chunks,
)


def test_build_report_retrieval_chunks_includes_section_and_followup_evidence() -> None:
    report = {
        "keyword": "AI 浏览器",
        "executive_summary": "优先关注预算窗口和重点甲方。",
        "followup_context": {
            "supplemental_evidence": "新增证据表明，上海数据集团将在 7 月启动预算复核。",
            "supplemental_requirements": "请重点判断最新预算窗口和下一步组织入口。",
        },
        "sections": [
            {
                "title": "项目与商机判断",
                "items": ["上海数据集团当前的推进窗口比其他甲方更清晰。"],
                "evidence_links": [
                    {
                        "title": "上海数据集团公开公告",
                        "url": "https://example.com/shanghai-data",
                        "source_label": "公开公告",
                        "source_tier": "official",
                        "anchor_text": "预算复核 / 时间窗",
                        "excerpt": "公告提到 7 月将启动预算复核，并同步需求确认。",
                    }
                ],
            }
        ],
        "sources": [
            {
                "title": "上海数据集团公开公告",
                "url": "https://example.com/shanghai-data",
                "snippet": "披露 AI 浏览器试点与预算安排",
                "source_type": "policy",
                "source_tier": "official",
            }
        ],
    }

    chunks = build_report_retrieval_chunks(report)

    assert any(chunk.field_key == "supplemental_evidence" for chunk in chunks)
    assert any(chunk.field_key == "section_evidence" for chunk in chunks)
    assert any(chunk.source_url == "https://example.com/shanghai-data" for chunk in chunks)


def test_retrieve_report_evidence_chunks_prioritizes_new_budget_evidence() -> None:
    report = {
        "keyword": "AI 浏览器",
        "executive_summary": "上一版建议先跟进长三角区域甲方。",
        "budget_signals": ["Q2 预算已启动"],
        "followup_context": {
            "supplemental_evidence": "新增证据显示，上海数据集团 7 月前后将启动预算复核。",
        },
        "sections": [
            {
                "title": "项目与商机判断",
                "items": ["上海数据集团更适合优先推进。"],
                "evidence_links": [
                    {
                        "title": "上海数据集团公开公告",
                        "url": "https://example.com/shanghai-data",
                        "source_label": "公开公告",
                        "source_tier": "official",
                        "anchor_text": "预算复核 / 时间窗",
                        "excerpt": "公告提到 7 月前后将启动预算复核与需求确认。",
                    }
                ],
            }
        ],
    }

    matches = retrieve_report_evidence_chunks("新增的预算证据和时间节点是什么？", report, limit=3)

    assert matches
    assert "预算复核" in matches[0]["text"]
    assert matches[0]["field_key"] in {"supplemental_evidence", "section_evidence"}
    assert any(link["url"] == "https://example.com/shanghai-data" for link in matches[0]["evidence_links"])
