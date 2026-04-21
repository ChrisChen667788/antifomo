from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import uuid

from app.models.entities import Item
from app.services import item_processor, research_service, wechat_url_resolver
from app.services.browser_content_extractor import extract_from_browser
from app.services import browser_content_extractor
from app.services.content_extractor import ContentExtractionError, ExtractedContent


def test_extract_from_browser_parses_script_output(monkeypatch) -> None:
    body = "这是浏览器正文内容。" * 30

    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=(
                '{"page_url":"https://mp.weixin.qq.com/s/demo","title":"浏览器正文测试","body_text":"'
                + body
                + '","raw_content":"标题：浏览器正文测试\\n正文：'
                + body
                + '","source_domain":"mp.weixin.qq.com"}\n'
            ),
            stderr="",
        )

    monkeypatch.setattr(browser_content_extractor, "BROWSER_EXTRACT_SCRIPT", Path(__file__))
    monkeypatch.setattr(browser_content_extractor.subprocess, "run", fake_run)

    extracted = extract_from_browser("https://mp.weixin.qq.com/s/demo", timeout_seconds=8)
    assert extracted.source_domain == "mp.weixin.qq.com"
    assert extracted.title == "浏览器正文测试"
    assert "浏览器正文内容" in extracted.clean_content


def test_item_processor_prefers_browser_extractor_for_wechat_url(monkeypatch) -> None:
    body = "公众号正文。" * 60
    calls: list[str] = []

    def fake_browser(*args, **kwargs):
        calls.append("browser")
        return ExtractedContent(
            source_url="https://mp.weixin.qq.com/s/demo",
            source_domain="mp.weixin.qq.com",
            title="浏览器抓取成功",
            raw_content=body,
            clean_content=body,
        )

    def fail_remote(*args, **kwargs):  # pragma: no cover
        raise AssertionError("fallback extractor should not be called when browser extraction succeeds")

    monkeypatch.setattr(item_processor, "extract_from_browser", fake_browser)
    monkeypatch.setattr(item_processor, "extract_from_reader_proxy", fail_remote)
    monkeypatch.setattr(item_processor, "extract_from_url", fail_remote)

    item = Item(
        user_id=uuid.uuid4(),
        source_type="url",
        source_url="https://mp.weixin.qq.com/s/demo",
        title=None,
        raw_content="",
        status="pending",
    )

    source_domain, title, clean_content = item_processor._prepare_item_content(item)
    assert calls == ["browser"]
    assert source_domain == "mp.weixin.qq.com"
    assert title == "浏览器抓取成功"
    assert clean_content == body


def test_research_source_document_marks_browser_extracted_for_wechat(monkeypatch) -> None:
    body = "提取到的微信正文。" * 40

    def fake_browser(*args, **kwargs):
        return ExtractedContent(
            source_url="https://mp.weixin.qq.com/s/research-demo",
            source_domain="mp.weixin.qq.com",
            title="研究微信正文",
            raw_content=body,
            clean_content=body,
        )

    monkeypatch.setattr(research_service, "extract_from_browser", fake_browser)
    monkeypatch.setattr(
        research_service,
        "extract_from_url",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("url extractor should not be used")),
    )
    monkeypatch.setattr(
        research_service,
        "extract_from_reader_proxy",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("reader proxy should not be used")),
    )

    hit = research_service.SearchHit(
        title="研究微信正文",
        url="https://mp.weixin.qq.com/s/research-demo",
        snippet="微信正文片段",
        search_query="AI漫剧 快手 官方",
        source_hint="wechat",
    )
    source = research_service._extract_source_document(hit, timeout_seconds=8, excerpt_chars=220)
    assert source.content_status == "browser_extracted"
    assert "提取到的微信正文" in source.excerpt


def test_wechat_resolver_prefers_browser_extractor(monkeypatch) -> None:
    body = "这是一段可以命中的公众号正文。" * 20
    calls: list[str] = []

    monkeypatch.setattr(wechat_url_resolver, "_search_existing_items", lambda *args, **kwargs: [])
    monkeypatch.setattr(wechat_url_resolver, "_build_queries", lambda *args, **kwargs: ["测试文章"])
    monkeypatch.setattr(
        wechat_url_resolver,
        "_search_duckduckgo",
        lambda *args, **kwargs: [
            wechat_url_resolver._SearchHit(
                title="测试文章",
                url="https://mp.weixin.qq.com/s/resolver-demo",
                snippet="正文片段",
                search_query="测试文章",
            )
        ],
    )

    def fake_browser(*args, **kwargs):
        calls.append("browser")
        return ExtractedContent(
            source_url="https://mp.weixin.qq.com/s/resolver-demo",
            source_domain="mp.weixin.qq.com",
            title="测试文章",
            raw_content=body,
            clean_content=body,
        )

    def fail_fallback(*args, **kwargs):
        calls.append("fallback")
        raise ContentExtractionError("should not be reached")

    monkeypatch.setattr(wechat_url_resolver, "extract_from_browser", fake_browser)
    monkeypatch.setattr(wechat_url_resolver, "extract_from_url", fail_fallback)
    monkeypatch.setattr(wechat_url_resolver, "extract_from_reader_proxy", fail_fallback)

    result = wechat_url_resolver.resolve_wechat_article_url(
        title_hint="测试文章",
        body_preview="这是一段可以命中的公众号正文。",
        timeout_seconds=3,
        search_limit=3,
        verify_limit=1,
    )
    assert calls == ["browser"]
    assert result.resolved_url == "https://mp.weixin.qq.com/s/resolver-demo"
