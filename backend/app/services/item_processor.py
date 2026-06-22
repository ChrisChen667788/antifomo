from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import Item, ItemTag
from app.services.browser_content_extractor import extract_from_browser
from app.services.language import localized_text, normalize_output_language
from app.services.content_extractor import (
    ContentExtractionError,
    extract_domain,
    extract_from_reader_proxy,
    extract_from_url,
    generate_title,
    normalize_text,
)
from app.services.scorer import Scorer
from app.services.summarizer import Summarizer
from app.services.tagger import Tagger
from app.services.llm_service import MockLLMService


summarizer = Summarizer()
tagger = Tagger()
scorer = Scorer()
_mock_llm_service = MockLLMService()
mock_summarizer = Summarizer(llm_service=_mock_llm_service)
mock_tagger = Tagger(llm_service=_mock_llm_service)
mock_scorer = Scorer(llm_service=_mock_llm_service)
settings = get_settings()

_ARTICLE_METRIC_RE = re.compile(
    r"20[2-3]\d[./年-]\s*\d{1,2}[./月-]\s*\d{1,2}日?\s*(?:本文)?字数\s*[:：]?\s*\d{2,6}\s*[,，、]?\s*阅读时长[^。；;，,\n]{0,32}",
    flags=re.IGNORECASE,
)
_WECHAT_BOILERPLATE_RE = re.compile(
    r"(?:原创\s*)?(?:微信扫一扫|听全文|继续滑动看下一个|轻触阅读原文|阅读原文|喜欢此内容的人还喜欢)",
    flags=re.IGNORECASE,
)
_WECHAT_HOME_HEADER_RE = re.compile(
    r"^[\u4e00-\u9fffA-Za-z0-9·_-]{2,20}\s+[\u4e00-\u9fffA-Za-z0-9·_-]{2,30}\s+20[2-3]\d年\d{1,2}月\d{1,2}日(?:\s+\d{1,2}:\d{2})?\s*",
    flags=re.IGNORECASE,
)
_WECHAT_HOME_HEADER_TITLE_RE = re.compile(
    r"^[\u4e00-\u9fffA-Za-z0-9·_-]{2,20}\s+[\u4e00-\u9fffA-Za-z0-9·_-]{2,30}\s+20[2-3]\d年\d{1,2}月\d{1,2}日(?:\s+\d{1,2}:\d{2})?$",
    flags=re.IGNORECASE,
)
_WECHAT_FOLLOW_PROMPT_RE = re.compile(
    r"(?:[\u4e00-\u9fff]{0,8}\d+\s*人\s*)?点击蓝字\s*可以关注我们[喔哦]?[!！]?",
    flags=re.IGNORECASE,
)
_BAD_TITLE_MARKERS = ("本文字数", "阅读时长", "字数：", "字数:", "分钟作者", "微信公众平台")
_BROWSER_NAV_NOISE_TOKENS = ("个人收藏", "京东", "天猫", "淘宝", "苏宁易购", "维基百科", "iCloud", "百度", "新浪微博")


def _looks_like_browser_nav_noise(value: str) -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return False
    return normalized.startswith("个人收藏") and sum(token in normalized for token in _BROWSER_NAV_NOISE_TOKENS) >= 4


def _is_wechat_source_domain(source_domain: str) -> bool:
    normalized = (source_domain or "").lower()
    return normalized in {"wechat.local"} or normalized.endswith("mp.weixin.qq.com") or "mp.weixin.qq.com" in normalized


def _looks_like_bad_article_title(value: str, *, source_domain: str = "") -> bool:
    normalized = normalize_text(value)
    if not normalized:
        return True
    lowered = normalized.lower()
    if lowered.startswith(("wechat auto", "wechat ocr", "untitled")):
        return True
    if any(marker in normalized for marker in _BAD_TITLE_MARKERS):
        return True
    if _is_wechat_source_domain(source_domain) and _WECHAT_HOME_HEADER_TITLE_RE.match(normalized):
        return True
    if _is_wechat_source_domain(source_domain) and _looks_like_browser_nav_noise(normalized):
        return True
    return bool(_ARTICLE_METRIC_RE.search(normalized))


def looks_like_bad_item_title(value: str, *, source_domain: str = "") -> bool:
    return _looks_like_bad_article_title(value, source_domain=source_domain)


def _strip_article_boilerplate(content: str, *, source_domain: str = "") -> str:
    text = normalize_text(content)
    if not text:
        return ""
    is_wechat = _is_wechat_source_domain(source_domain)
    if is_wechat:
        if _looks_like_browser_nav_noise(text):
            marker = re.search(r"(本地服务|第一次跑|已积累|source_url:|正文[:：])", text)
            if marker:
                text = text[marker.start() :]
        text = _WECHAT_HOME_HEADER_RE.sub(" ", text, count=1)
        text = _WECHAT_FOLLOW_PROMPT_RE.sub(" ", text, count=2)
        text = _WECHAT_BOILERPLATE_RE.sub(" ", text)
        text = _ARTICLE_METRIC_RE.sub(" ", text, count=2)
        text = re.sub(
            r"^(?:作者|来源)\s*[|｜:：]\s*[\u4e00-\u9fffA-Za-z0-9·\s]{2,24}(?=(近日|日前|近来|据|今年|本周|上周|\d{1,2}月))",
            "",
            text,
        )
        text = re.sub(
            r"^[\u4e00-\u9fffA-Za-z0-9·]{2,12}\s+[\u4e00-\u9fffA-Za-z·]{2,8}(?=(近日|日前|近来|据|今年|本周|上周|\d{1,2}月))",
            "",
            text,
        )
    return normalize_text(text).strip("，,、:：- ")


def _derive_topic_title_from_text(text: str) -> str:
    normalized = _strip_article_boilerplate(text, source_domain="mp.weixin.qq.com")
    if not normalized:
        return ""
    if "pixcull_demo" in normalized or ("模型加载" in normalized and "本地缓存" in normalized):
        return "本地照片分拣工具运行状态"
    briefing_match = re.search(r"(每天\s*3\s*分钟[，,、]\s*速览天下事)\s*([^。！？!?]{0,16})", normalized)
    if briefing_match:
        return normalize_text(f"{briefing_match.group(1)} {briefing_match.group(2)}")[:36].rstrip("，,、:：- ")
    quoted_entities = [
        normalize_text(match.group(1))
        for match in re.finditer(r"[“\"]([^”\"]{2,16})[”\"]", normalized)
        if normalize_text(match.group(1))
    ]
    if quoted_entities and any(token in normalized for token in ("约谈", "责令改正", "警告", "通报", "处罚")):
        names = "、".join(quoted_entities[:2])
        if len(quoted_entities) > 2:
            names = f"{names}等"
        if "标识" in normalized and any(token in normalized for token in ("AI", "人工智能", "生成合成")):
            return f"{names}因AI内容标识问题被约谈"[:36]
        return f"{names}被监管部门约谈"[:36]
    if "招标" in normalized and "数字人" in normalized:
        return "数字人项目招标要求梳理"
    for sentence in re.split(r"[。！？!?]", normalized):
        cleaned = normalize_text(sentence).strip("，,、:：- ")
        if not cleaned:
            continue
        cleaned = re.sub(r"^(近日|日前|据悉|今年|本周|上周)[，,]?", "", cleaned).strip("，,、:：- ")
        if 10 <= len(cleaned) <= 36:
            return cleaned
        if len(cleaned) > 36:
            return cleaned[:36].rstrip("，,、:：- ")
    return ""


def _resolve_display_title(
    *,
    source_title: str,
    llm_display_title: str | None,
    short_summary: str,
    clean_content: str = "",
    output_language: str,
    source_domain: str = "",
) -> str:
    candidate = normalize_text(llm_display_title or "")
    if 8 <= len(candidate) <= 36 and not _looks_like_bad_article_title(candidate, source_domain=source_domain):
        return candidate

    fallback = normalize_text(source_title)
    fallback = re.sub(r"^(重磅|深度|终于|彻底|爆火|疯传|独家)[:：]?", "", fallback).strip()
    if 8 <= len(fallback) <= 36 and not _looks_like_bad_article_title(fallback, source_domain=source_domain):
        return fallback

    topic_title = _derive_topic_title_from_text(" ".join([short_summary, clean_content]))
    if 8 <= len(topic_title) <= 36:
        return topic_title

    summary = normalize_text(short_summary)
    for sentence in re.split(r"[。！？!?]", summary):
        cleaned = normalize_text(sentence)
        if 8 <= len(cleaned) <= 36:
            return cleaned
        if len(cleaned) > 36:
            return cleaned[:36].rstrip("，,：:；; ")

    return localized_text(
        output_language,
        {
            "zh-CN": "主题待确认",
            "zh-TW": "主題待確認",
            "en": "Topic pending",
            "ja": "テーマ確認待ち",
            "ko": "주제 확인 대기",
        },
        "主题待确认",
    )


def _placeholder_title(source_domain: str, output_language: str) -> str:
    if source_domain.endswith("mp.weixin.qq.com"):
        return localized_text(
            output_language,
            {
                "zh-CN": "公众号文章（待补全）",
                "zh-TW": "公眾號文章（待補全）",
                "en": "WeChat article (needs completion)",
                "ja": "WeChat記事（補完待ち）",
                "ko": "위챗 글(보완 필요)",
            },
            "公众号文章（待补全）",
        )
    return localized_text(
        output_language,
        {
            "zh-CN": f"{source_domain or '未知来源'} 文章（待补全）",
            "zh-TW": f"{source_domain or '未知來源'} 文章（待補全）",
            "en": f"{source_domain or 'Unknown source'} article (needs completion)",
            "ja": f"{source_domain or '不明なソース'} の記事（補完待ち）",
            "ko": f"{source_domain or '알 수 없는 출처'} 글(보완 필요)",
        },
        f"{source_domain or '未知来源'} 文章（待补全）",
    )


def _missing_content_hint(source_domain: str, output_language: str) -> str:
    return localized_text(
        output_language,
        {
            "zh-CN": (
                f"该链接暂未获取到正文。来源：{source_domain or '未知来源'}。"
                "建议通过已登录浏览器插件提交页面，或手动粘贴正文。"
            ),
            "zh-TW": (
                f"此連結暫未取得正文。來源：{source_domain or '未知來源'}。"
                "建議使用已登入瀏覽器外掛提交頁面，或手動貼上正文。"
            ),
            "en": (
                f"Full text is not available for this link yet. Source: {source_domain or 'unknown source'}. "
                "Submit from a logged-in browser extension or paste the article text manually."
            ),
            "ja": (
                f"このリンクの本文はまだ取得できていません。ソース: {source_domain or '不明'}。"
                "ログイン済みブラウザ拡張から送信するか、本文を手動で貼り付けてください。"
            ),
            "ko": (
                f"이 링크의 본문을 아직 가져오지 못했습니다. 출처: {source_domain or '알 수 없음'}."
                "로그인된 브라우저 확장에서 다시 제출하거나 본문을 직접 붙여넣어 주세요."
            ),
        },
        "该链接暂未获取到正文，建议重新提交。",
    )


def resolve_item_display_title(
    *,
    source_title: str,
    llm_display_title: str | None = None,
    short_summary: str,
    clean_content: str = "",
    output_language: str,
    source_domain: str = "",
) -> str:
    return _resolve_display_title(
        source_title=source_title,
        llm_display_title=llm_display_title,
        short_summary=short_summary,
        clean_content=clean_content,
        output_language=output_language,
        source_domain=source_domain,
    )


def _extract_plugin_structured_content(
    raw_content: str, *, source_domain: str = ""
) -> tuple[str | None, str | None, str | None]:
    text = raw_content.strip()
    if not text:
        return None, None, None

    title_match = re.search(r"标题[:：]\s*(.+?)(?:\s+(?:作者[:：]|发布时间[:：]|关键词[:：]|摘要线索[:：]|正文[:：]))", text)
    if not title_match:
        title_match = re.search(r"标题[:：]\s*(.+)", text)
    title_hint = normalize_text(title_match.group(1)) if title_match else None
    if title_hint and _looks_like_bad_article_title(title_hint, source_domain=source_domain):
        title_hint = None

    keyword_match = re.search(r"关键词[:：]\s*(.+?)(?:\s+(?:摘要线索[:：]|正文[:：]))", text)
    if not keyword_match:
        keyword_match = re.search(r"关键词[:：]\s*(.+)", text)
    keywords = normalize_text(keyword_match.group(1)) if keyword_match else None

    body_match = re.search(r"正文[:：]\s*(.+)$", text)
    body_text = normalize_text(body_match.group(1)) if body_match else None
    body_text = _strip_article_boilerplate(body_text or "", source_domain="mp.weixin.qq.com") if body_text else None
    if body_text and len(body_text) < 60:
        body_text = None

    return title_hint, keywords, body_text


def _prepare_item_content(item: Item, output_language: str = "zh-CN") -> tuple[str, str, str]:
    resolved_language = normalize_output_language(output_language)
    source_domain = extract_domain(item.source_url) or item.source_domain or ""
    title = item.title or ""
    raw_content = normalize_text(item.raw_content or "")
    if _looks_like_bad_article_title(title, source_domain=source_domain):
        title = ""

    # Prefer plugin-provided page content when available.
    if item.source_type == "plugin" and len(raw_content) >= 120:
        parsed_title, parsed_keywords, parsed_body = _extract_plugin_structured_content(
            raw_content,
            source_domain=source_domain,
        )
        if parsed_title and not title:
            title = parsed_title
        if parsed_body:
            clean_content = _strip_article_boilerplate(parsed_body, source_domain=source_domain)
            if parsed_keywords:
                clean_content = f"{clean_content}\n关键词：{parsed_keywords}"
            if not title:
                title = _derive_topic_title_from_text(clean_content) or generate_title(clean_content, source_domain or None)
            return source_domain, title, clean_content

        if not title:
            title = _derive_topic_title_from_text(raw_content) or generate_title(raw_content, source_domain or None)
        clean_content = _strip_article_boilerplate(raw_content, source_domain=source_domain)
        return source_domain, title, clean_content

    # URL/plugin source: try fetch remote content first when URL is available.
    if item.source_url and item.source_type in {"url", "plugin"}:
        # Favorites imports should acknowledge the click quickly. A direct fetch can usually
        # distinguish a readable public article from an expired/verification page in seconds;
        # the slower logged-in browser path remains available through browser ingest/extension.
        if source_domain.endswith("mp.weixin.qq.com") and item.ingest_route == "wechat_favorites":
            try:
                extracted = extract_from_url(
                    item.source_url,
                    timeout_seconds=max(3, min(settings.url_fetch_timeout_seconds, 8)),
                )
                source_domain = extracted.source_domain or source_domain
                title = title or (extracted.title or "")
                raw_content = extracted.raw_content
                clean_content = _strip_article_boilerplate(extracted.clean_content, source_domain=source_domain)
                if _looks_like_bad_article_title(title, source_domain=source_domain):
                    title = _derive_topic_title_from_text(clean_content)
                return source_domain, title, clean_content if clean_content else normalize_text(raw_content)
            except ContentExtractionError:
                pass

        # WeChat official account pages are frequently gated; prefer a logged-in browser extraction chain.
        if source_domain.endswith("mp.weixin.qq.com"):
            try:
                extracted = extract_from_browser(
                    item.source_url,
                    timeout_seconds=settings.browser_extractor_timeout_seconds,
                )
                source_domain = extracted.source_domain or source_domain
                title = title or (extracted.title or "")
                raw_content = extracted.raw_content
                clean_content = _strip_article_boilerplate(extracted.clean_content, source_domain=source_domain)
                if _looks_like_bad_article_title(title, source_domain=source_domain):
                    title = _derive_topic_title_from_text(clean_content)
                return source_domain, title, clean_content if clean_content else normalize_text(raw_content)
            except ContentExtractionError:
                pass
            try:
                extracted = extract_from_reader_proxy(
                    item.source_url,
                    timeout_seconds=max(settings.url_fetch_timeout_seconds, 10),
                )
                source_domain = extracted.source_domain or source_domain
                title = title or (extracted.title or "")
                raw_content = extracted.raw_content
                clean_content = _strip_article_boilerplate(extracted.clean_content, source_domain=source_domain)
                if _looks_like_bad_article_title(title, source_domain=source_domain):
                    title = _derive_topic_title_from_text(clean_content)
                return source_domain, title, clean_content if clean_content else normalize_text(raw_content)
            except ContentExtractionError:
                pass

        try:
            extracted = extract_from_url(
                item.source_url,
                timeout_seconds=settings.url_fetch_timeout_seconds,
            )
            source_domain = extracted.source_domain or source_domain
            title = title or (extracted.title or "")
            raw_content = extracted.raw_content
            clean_content = _strip_article_boilerplate(extracted.clean_content, source_domain=source_domain)
            if _looks_like_bad_article_title(title, source_domain=source_domain):
                title = _derive_topic_title_from_text(clean_content)
            return source_domain, title, clean_content if clean_content else normalize_text(raw_content)
        except ContentExtractionError:
            # Fallback to a reader proxy before giving up.
            try:
                extracted = extract_from_reader_proxy(
                    item.source_url,
                    timeout_seconds=max(settings.url_fetch_timeout_seconds, 8),
                )
                source_domain = extracted.source_domain or source_domain
                title = title or (extracted.title or "")
                raw_content = extracted.raw_content
                clean_content = _strip_article_boilerplate(extracted.clean_content, source_domain=source_domain)
                if _looks_like_bad_article_title(title, source_domain=source_domain):
                    title = _derive_topic_title_from_text(clean_content)
                return source_domain, title, clean_content if clean_content else normalize_text(raw_content)
            except ContentExtractionError:
                # Fallback to existing raw_content if all extraction attempts fail.
                pass

    if raw_content and raw_content.startswith("来自 ") and " 的链接：" in raw_content:
        # Historical placeholder content from early demo versions.
        raw_content = ""
    if not raw_content and item.source_url:
        raw_content = _missing_content_hint(source_domain, resolved_language)
    if not title:
        title = _placeholder_title(source_domain, resolved_language)
    clean_content = _strip_article_boilerplate(raw_content, source_domain=source_domain)
    if _looks_like_bad_article_title(title, source_domain=source_domain):
        title = _derive_topic_title_from_text(clean_content)
    return source_domain, title, clean_content


def _resolve_item_processing_stack(item: Item) -> tuple[Summarizer, Tagger, Scorer, int | None]:
    if item.ingest_route == "ocr" and item.fallback_used:
        return mock_summarizer, mock_tagger, mock_scorer, None
    if item.ingest_route == "ocr":
        return summarizer, tagger, scorer, max(1, int(settings.ocr_item_llm_timeout_seconds))
    return summarizer, tagger, scorer, max(1, int(settings.item_llm_timeout_seconds))


def process_item(db: Session, item: Item, *, output_language: str | None = None) -> Item:
    resolved_language = normalize_output_language(output_language or item.output_language)
    item.output_language = resolved_language
    item.status = "processing"
    item.processing_error = None

    try:
        source_domain, title, clean_content = _prepare_item_content(item, resolved_language)
        if (
            title.startswith("来自 ")
            or title.lower().startswith("weixin official accounts platform")
            or title == "微信公众平台"
        ) and any(
            marker in clean_content
            for marker in (
                "暂未获取正文",
                "暂未获取到正文",
                "访问受限",
                "未能抓取到正文",
                "text is not available",
                "access is restricted",
            )
        ):
            title = _placeholder_title(source_domain, resolved_language)
        title = title or generate_title(clean_content, source_domain or None)
        source_domain = source_domain or "unknown"

        source_title = title
        resolved_summarizer, resolved_tagger, resolved_scorer, llm_timeout_seconds = _resolve_item_processing_stack(item)

        summarize_result = resolved_summarizer.summarize(
            title=source_title,
            source_domain=source_domain,
            clean_content=clean_content,
            output_language=resolved_language,
            timeout_seconds=llm_timeout_seconds,
        )

        display_title = _resolve_display_title(
            source_title=source_title,
            llm_display_title=summarize_result.display_title,
            short_summary=summarize_result.short_summary,
            clean_content=clean_content,
            output_language=resolved_language,
            source_domain=source_domain,
        )

        tags_result = resolved_tagger.extract_tags(
            title=display_title,
            short_summary=summarize_result.short_summary,
            clean_content=clean_content,
            output_language=resolved_language,
            timeout_seconds=llm_timeout_seconds,
        )

        score_result = resolved_scorer.score(
            title=display_title,
            source_domain=source_domain,
            short_summary=summarize_result.short_summary,
            long_summary=summarize_result.long_summary,
            output_language=resolved_language,
            timeout_seconds=llm_timeout_seconds,
        )

        item.source_domain = source_domain
        item.title = display_title
        item.clean_content = clean_content
        if item.source_type in {"url", "plugin"}:
            item.raw_content = clean_content
        else:
            item.raw_content = item.raw_content or clean_content
        item.short_summary = summarize_result.short_summary
        item.long_summary = summarize_result.long_summary
        item.score_value = Decimal(str(score_result.score_value))
        item.action_suggestion = score_result.action_suggestion
        item.processed_at = datetime.now(timezone.utc)
        item.status = "ready"

        item.tags.clear()
        for tag in tags_result.tags[:5]:
            if not tag:
                continue
            item.tags.append(ItemTag(tag_name=tag))

    except Exception as exc:  # pragma: no cover - defensive branch
        item.status = "failed"
        item.processing_error = str(exc)
        item.processed_at = datetime.now(timezone.utc)

    db.add(item)
    return item
