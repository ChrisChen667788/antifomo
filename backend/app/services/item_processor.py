from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
import re

from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import Item, ItemTag
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


summarizer = Summarizer()
tagger = Tagger()
scorer = Scorer()
settings = get_settings()


def _resolve_display_title(
    *,
    source_title: str,
    llm_display_title: str | None,
    short_summary: str,
    output_language: str,
) -> str:
    candidate = normalize_text(llm_display_title or "")
    if 8 <= len(candidate) <= 36:
        return candidate

    fallback = normalize_text(source_title)
    fallback = re.sub(r"^(重磅|深度|终于|彻底|爆火|疯传|独家)[:：]?", "", fallback).strip()
    if 8 <= len(fallback) <= 36:
        return fallback

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


def _extract_plugin_structured_content(raw_content: str) -> tuple[str | None, str | None, str | None]:
    text = raw_content.strip()
    if not text:
        return None, None, None

    title_match = re.search(r"标题[:：]\s*(.+?)(?:\s+(?:作者[:：]|发布时间[:：]|关键词[:：]|摘要线索[:：]|正文[:：]))", text)
    if not title_match:
        title_match = re.search(r"标题[:：]\s*(.+)", text)
    title_hint = normalize_text(title_match.group(1)) if title_match else None

    keyword_match = re.search(r"关键词[:：]\s*(.+?)(?:\s+(?:摘要线索[:：]|正文[:：]))", text)
    if not keyword_match:
        keyword_match = re.search(r"关键词[:：]\s*(.+)", text)
    keywords = normalize_text(keyword_match.group(1)) if keyword_match else None

    body_match = re.search(r"正文[:：]\s*(.+)$", text)
    body_text = normalize_text(body_match.group(1)) if body_match else None
    if body_text and len(body_text) < 60:
        body_text = None

    return title_hint, keywords, body_text


def _prepare_item_content(item: Item, output_language: str = "zh-CN") -> tuple[str, str, str]:
    resolved_language = normalize_output_language(output_language)
    source_domain = extract_domain(item.source_url) or item.source_domain or ""
    title = item.title or ""
    raw_content = normalize_text(item.raw_content or "")

    # Prefer plugin-provided page content when available.
    if item.source_type == "plugin" and len(raw_content) >= 120:
        parsed_title, parsed_keywords, parsed_body = _extract_plugin_structured_content(raw_content)
        if parsed_title and not title:
            title = parsed_title
        if parsed_body:
            clean_content = parsed_body
            if parsed_keywords:
                clean_content = f"{clean_content}\n关键词：{parsed_keywords}"
            if not title:
                title = generate_title(clean_content, source_domain or None)
            return source_domain, title, clean_content

        if not title:
            title = generate_title(raw_content, source_domain or None)
        clean_content = raw_content
        return source_domain, title, clean_content

    # URL/plugin source: try fetch remote content first when URL is available.
    if item.source_url and item.source_type in {"url", "plugin"}:
        # WeChat official account pages are frequently gated; use reader proxy first.
        if source_domain.endswith("mp.weixin.qq.com"):
            try:
                extracted = extract_from_reader_proxy(
                    item.source_url,
                    timeout_seconds=10,
                )
                source_domain = extracted.source_domain or source_domain
                title = title or (extracted.title or "")
                raw_content = extracted.raw_content
                clean_content = extracted.clean_content
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
            clean_content = extracted.clean_content
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
                clean_content = extracted.clean_content
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
    clean_content = raw_content
    return source_domain, title, clean_content


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

        summarize_result = summarizer.summarize(
            title=source_title,
            source_domain=source_domain,
            clean_content=clean_content,
            output_language=resolved_language,
        )

        display_title = _resolve_display_title(
            source_title=source_title,
            llm_display_title=summarize_result.display_title,
            short_summary=summarize_result.short_summary,
            output_language=resolved_language,
        )

        tags_result = tagger.extract_tags(
            title=display_title,
            short_summary=summarize_result.short_summary,
            clean_content=clean_content,
            output_language=resolved_language,
        )

        score_result = scorer.score(
            title=display_title,
            source_domain=source_domain,
            short_summary=summarize_result.short_summary,
            long_summary=summarize_result.long_summary,
            output_language=resolved_language,
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
