from __future__ import annotations

import json
from email.message import Message

import pytest

from app.services import content_extractor
from app.services.content_extractor import (
    ContentExtractionError,
    _build_access_limited_content,
    _contains_access_block,
)
from app.services.llm_service import MockLLMService


def test_contains_access_block_detects_wechat_verification_page() -> None:
    assert _contains_access_block("Warning: This page maybe requiring CAPTCHA")
    assert _contains_access_block("当前环境异常，完成验证后即可继续访问。")
    assert _contains_access_block("参数错误，当前公众号文章链接已经失效。")
    assert not _contains_access_block("这是正常正文内容，无访问异常。")
    assert not _contains_access_block("如何排查参数错误 " + "这是一篇正常的技术文章正文。" * 80)


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


def test_url_extractor_rejects_access_limited_shell_and_preserves_verified_tls(monkeypatch) -> None:
    headers = Message()
    headers["Content-Type"] = "text/html; charset=utf-8"

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, _max_bytes: int) -> bytes:
            return "<html><title>微信公众平台</title><body>当前环境异常，完成验证后即可继续访问。</body></html>".encode(
                "utf-8"
            )

    response = _Response()
    response.headers = headers
    monkeypatch.setattr(content_extractor, "_urlopen_verified", lambda *_args, **_kwargs: response)

    with pytest.raises(ContentExtractionError, match="access_limited"):
        content_extractor.extract_from_url("https://mp.weixin.qq.com/s/blocked")


@pytest.mark.parametrize("reader_proxy", [False, True])
def test_extractors_reject_oversized_responses_without_storing_truncated_evidence(
    monkeypatch,
    reader_proxy: bool,
) -> None:
    headers = Message()
    headers["Content-Type"] = "text/html; charset=utf-8"

    class _Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self, requested: int) -> bytes:
            assert requested == 33
            return b"x" * requested

    response = _Response()
    response.headers = headers
    monkeypatch.setattr(content_extractor, "_urlopen_verified", lambda *_args, **_kwargs: response)
    monkeypatch.setattr(content_extractor, "validate_public_http_url", lambda _url: None)

    extractor = (
        content_extractor.extract_from_reader_proxy
        if reader_proxy
        else content_extractor.extract_from_url
    )
    with pytest.raises(ContentExtractionError, match="content_too_large"):
        extractor("https://example.com/article", max_bytes=32)
