from __future__ import annotations

import json

from app.services.content_extractor import _build_access_limited_content, _contains_access_block
from app.services.llm_service import MockLLMService


def test_contains_access_block_detects_wechat_verification_page() -> None:
    assert _contains_access_block("Warning: This page maybe requiring CAPTCHA")
    assert _contains_access_block("当前环境异常，完成验证后即可继续访问。")
    assert not _contains_access_block("这是正常正文内容，无访问异常。")


def test_build_access_limited_content_has_readable_title_and_guidance() -> None:
    title, clean_content = _build_access_limited_content(
        "mp.weixin.qq.com",
        "https://mp.weixin.qq.com/s/vC1AnilUPkxBn3RrMwwP4g",
    )
    assert "访问受限" in title
    assert "建议" in clean_content
    assert "正文" in clean_content


def test_mock_llm_marks_access_limited_content_as_skip() -> None:
    service = MockLLMService()
    summary_raw = service.run_prompt(
        "summarize.txt",
        {
            "title": "mp.weixin.qq.com 文章（访问受限）",
            "source_domain": "mp.weixin.qq.com",
            "clean_content": "该链接当前访问受限，未能抓取到正文。可能需要登录或验证码。",
        },
    )
    score_raw = service.run_prompt(
        "score.txt",
        {
            "title": "mp.weixin.qq.com 文章（访问受限）",
            "source_domain": "mp.weixin.qq.com",
            "short_summary": "该链接暂未获取正文，可能需要登录或验证码。",
            "long_summary": "系统识别到访问受限，当前无法稳定抓取正文内容。",
        },
    )
    tags_raw = service.run_prompt(
        "tags.txt",
        {
            "title": "mp.weixin.qq.com 文章（访问受限）",
            "short_summary": "该链接暂未获取正文，可能需要登录或验证码。",
            "clean_content": "该链接当前访问受限，未能抓取到正文。",
        },
    )

    summary_payload = json.loads(summary_raw)
    score_payload = json.loads(score_raw)
    tags_payload = json.loads(tags_raw)

    assert "建议" in summary_payload["short_summary"]
    assert summary_payload["display_title"]
    assert score_payload["action_suggestion"] == "skip"
    assert score_payload["score_value"] <= 1.5
    assert "待补全" in tags_payload["tags"]
