from __future__ import annotations

from app.services import research_service
from app.services.research import report_row_quality


def test_row_quality_filters_budget_noise_and_keeps_actionable_rows() -> None:
    assert report_row_quality.is_actionable_budget_row("上海数据集团采购项目预算 1200 万元，7 月启动招标")
    assert not report_row_quality.is_actionable_budget_row("中国经济开局良好，同比增长 5%")
    assert not report_row_quality.is_actionable_budget_row("当前证据不足，建议补充采购公告")


def test_summary_fact_rows_filters_guidance_and_source_artifacts() -> None:
    rows = report_row_quality.summary_fact_rows(
        [
            "上海数据集团：7 月预算复核",
            "建议补充政府采购、公共资源交易、上市公告和行业媒体对",
            "当前证据不足，待补充",
            "报告共计：公开线索 1 条，代表样本",
        ],
        limit=3,
    )

    assert rows == ["上海数据集团：7 月预算复核"]


def test_looks_like_insufficient_covers_localized_and_english_markers() -> None:
    assert report_row_quality.looks_like_insufficient("当前证据不足，待补充")
    assert report_row_quality.looks_like_insufficient("Current evidence is insufficient")
    assert not report_row_quality.looks_like_insufficient("预算窗口已经明确")


def test_research_service_row_quality_constants_are_owner_aliases() -> None:
    for name in (
        "MONEY_PATTERN",
        "SUMMARY_GUIDANCE_TOKENS",
        "BAD_SUMMARY_PHRASES",
        "BAD_EXEC_SUMMARY_PHRASES",
        "FIELD_ROW_NOISE_TOKENS",
        "COMMERCIAL_BUDGET_SIGNAL_TOKENS",
        "BUDGET_ROW_NOISE_TOKENS",
        "BUDGET_ROW_CONTEXT_TOKENS",
    ):
        assert getattr(research_service, name) is getattr(report_row_quality, name)
