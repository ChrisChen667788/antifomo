from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import uuid

from app.models.entities import Item
from app.services import item_processor, wechat_url_resolver
from app.services.browser_content_extractor import extract_from_browser
from app.services import browser_content_extractor
from app.services.content_extractor import ContentExtractionError, ExtractedContent, normalize_text
from app.services.research.source_documents import clean_source_text_for_analysis
from app.services.research.source_extraction import SourceExtractionDependencies, extract_source_document
from app.services.research.source_ranking import classify_source_tier, classify_source_type, derive_source_label
from app.services.research.web_search import SearchHit


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


def test_extract_from_browser_rejects_wechat_parameter_error_shell(monkeypatch) -> None:
    def fake_run(*args, **kwargs):
        return SimpleNamespace(
            returncode=0,
            stdout=(
                '{"page_url":"https://mp.weixin.qq.com/s/expired","title":"微信公众平台",'
                '"body_text":"参数错误，当前文章链接已失效。","raw_content":"正文：参数错误，当前文章链接已失效。",'
                '"source_domain":"mp.weixin.qq.com","has_body":false,"access_limited":true}\n'
            ),
            stderr="",
        )

    monkeypatch.setattr(browser_content_extractor, "BROWSER_EXTRACT_SCRIPT", Path(__file__))
    monkeypatch.setattr(browser_content_extractor.subprocess, "run", fake_run)

    try:
        extract_from_browser("https://mp.weixin.qq.com/s/expired", timeout_seconds=8)
    except ContentExtractionError as exc:
        assert "access-limited" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("parameter error shell must not be accepted as article content")


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


def test_wechat_favorites_item_uses_fast_direct_fetch_before_browser(monkeypatch) -> None:
    body = "公众号收藏正文。" * 60
    calls: list[str] = []

    def fake_direct(*args, **kwargs):
        calls.append("direct")
        return ExtractedContent(
            source_url="https://mp.weixin.qq.com/s/favorite-demo",
            source_domain="mp.weixin.qq.com",
            title="收藏链接快速抓取",
            raw_content=body,
            clean_content=body,
        )

    def fail_browser(*args, **kwargs):  # pragma: no cover
        raise AssertionError("favorites direct fetch succeeded; browser should not be called")

    monkeypatch.setattr(item_processor, "extract_from_url", fake_direct)
    monkeypatch.setattr(item_processor, "extract_from_browser", fail_browser)

    item = Item(
        user_id=uuid.uuid4(),
        source_type="url",
        source_url="https://mp.weixin.qq.com/s/favorite-demo",
        ingest_route="wechat_favorites",
        title=None,
        raw_content="",
        status="pending",
    )

    source_domain, title, clean_content = item_processor._prepare_item_content(item)
    assert calls == ["direct"]
    assert source_domain == "mp.weixin.qq.com"
    assert title == "收藏链接快速抓取"
    assert clean_content == body


def test_research_source_document_marks_browser_extracted_for_wechat() -> None:
    body = "提取到的微信正文。" * 40

    def fake_browser(*args, **kwargs):
        return ExtractedContent(
            source_url="https://mp.weixin.qq.com/s/research-demo",
            source_domain="mp.weixin.qq.com",
            title="研究微信正文",
            raw_content=body,
            clean_content=body,
        )

    deps = SourceExtractionDependencies(
        classify_source_type=classify_source_type,
        classify_source_tier=classify_source_tier,
        derive_source_label=derive_source_label,
        truncate_text=lambda value, limit: normalize_text(value or "")[:limit],
        clean_source_text_for_analysis=clean_source_text_for_analysis,
        extract_from_browser=fake_browser,
        extract_from_url=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("url extractor should not be used")
        ),
        extract_from_reader_proxy=lambda *args, **kwargs: (_ for _ in ()).throw(
            AssertionError("reader proxy should not be used")
        ),
    )

    hit = SearchHit(
        title="研究微信正文",
        url="https://mp.weixin.qq.com/s/research-demo",
        snippet="微信正文片段",
        search_query="AI漫剧 快手 官方",
        source_hint="wechat",
    )
    source = extract_source_document(hit, timeout_seconds=8, excerpt_chars=220, deps=deps)
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
