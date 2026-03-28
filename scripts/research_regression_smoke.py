from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.schemas.research import ResearchEntityGraphOut  # noqa: E402
from app.services.research_service import (  # noqa: E402
    SourceDocument,
    _build_report_title_override,
    _infer_input_scope_hints,
    _rank_top_entities,
)


def assert_true(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def run_case_ai_comic_instance_gate() -> None:
    keyword = "AI漫剧相关商机"
    focus = "只看长三角地区，聚焦AI漫剧、AIGC动画、动漫IP短剧，不要扩展到天津、金融、银行、芯片。"
    scope_hints = _infer_input_scope_hints(keyword=keyword, research_focus=focus)
    sources = [
        SourceDocument(
            title="爱奇艺发布 AIGC 短剧计划",
            url="https://www.iqiyi.com/a",
            domain="iqiyi.com",
            snippet="爱奇艺在上海推进 AI漫剧 和 AIGC动画 项目，披露合作与预算窗口。",
            search_query="爱奇艺 AI漫剧",
            source_type="web",
            content_status="snippet_only",
            excerpt="爱奇艺在上海推进 AI漫剧 和 AIGC动画 项目，披露合作与预算窗口。",
            source_label="爱奇艺官网",
            source_tier="official",
        ),
        SourceDocument(
            title="标签服务平台升级",
            url="https://example.com/b",
            domain="example.com",
            snippet="标签服务、用户画像服务、主力与协办能力升级。",
            search_query="AI漫剧 标签服务",
            source_type="web",
            content_status="snippet_only",
            excerpt="标签服务、用户画像服务、主力与协办能力升级。",
            source_label="某媒体",
            source_tier="media",
        ),
    ]
    top, pending = _rank_top_entities(
        sources,
        role="target",
        output_language="zh-CN",
        scope_hints=scope_hints,
        theme_terms=["ai漫剧", "aigc动画"],
        entity_graph=ResearchEntityGraphOut(),
        fallback_values=["主力与协办", "标签服务", "爱奇艺：AIGC动画与短剧平台公开线索"],
        limit=3,
    )
    top_names = [item.name for item in top]
    pending_names = [item.name for item in pending]
    assert_true("爱奇艺" in top_names, f"expected 爱奇艺 in top targets, got {top_names}")
    assert_true("主力与协办" not in top_names and "标签服务" not in top_names, f"generic labels leaked into top targets: {top_names}")
    assert_true("主力与协办" not in pending_names and "标签服务" not in pending_names, f"generic labels leaked into pending targets: {pending_names}")


def run_case_title_anchor_alignment() -> None:
    keyword = "AI漫剧相关商机"
    focus = "只看长三角地区，聚焦AI漫剧、AIGC动画、动漫IP短剧，不要扩展到天津、金融、银行、芯片。"
    scope_hints = _infer_input_scope_hints(keyword=keyword, research_focus=focus)
    scope_hints["company_anchors"] = ["爱奇艺", "某银行科技平台"]
    title = _build_report_title_override(
        keyword=keyword,
        research_focus=focus,
        scope_hints=scope_hints,
        intelligence={
            "target_accounts": ["爱奇艺：AIGC动画与短剧平台公开线索", "某银行科技平台：无关错题"],
            "tender_timeline": ["预算窗口已出现"],
            "project_distribution": ["AIGC动画项目"],
            "ecosystem_partners": ["阅文集团"],
            "competitor_profiles": ["腾讯视频"],
        },
        output_language="zh-CN",
    )
    assert_true("爱奇艺" in title, f"title did not anchor to theme company: {title}")
    assert_true("银行" not in title, f"title still drifted to excluded industry: {title}")


def main() -> int:
    run_case_ai_comic_instance_gate()
    run_case_title_anchor_alignment()
    print("research_regression_smoke: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
