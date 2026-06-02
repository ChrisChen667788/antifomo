from __future__ import annotations

import base64
import io
import re
from collections.abc import Callable
from typing import Any

from fastapi import HTTPException

from app.schemas.collector import CollectorOCRPreviewResponse


OCR_PREVIEW_VARIANT_PROFILES: dict[str, dict[str, float]] = {
    "article_right_focus": {"left": 0.34, "top": 0.06, "right": 0.98, "bottom": 0.92},
    "article_right_tight": {"left": 0.42, "top": 0.08, "right": 0.98, "bottom": 0.92},
    "article_far_right": {"left": 0.56, "top": 0.08, "right": 0.98, "bottom": 0.92},
}
OCR_PREVIEW_VARIANT_REASONS: dict[str, list[str]] = {
    "timeline_feed": ["article_right_focus", "article_far_right", "article_right_tight"],
    "chat_ui": ["article_right_focus", "article_far_right", "article_right_tight"],
    "chat_ui_multi": ["article_right_focus", "article_far_right", "article_right_tight"],
    "chat_list_brackets": ["article_right_focus", "article_far_right", "article_right_tight"],
    "non_article_hub": ["article_right_focus", "article_far_right", "article_right_tight"],
    "image_viewer": ["article_right_focus", "article_far_right"],
}


def evaluate_ocr_quality(
    body_text: str,
    confidence: float,
    *,
    clean_text: Callable[[str | None], str],
) -> tuple[bool, str | None]:
    text = clean_text(body_text)
    if len(text) < 45:
        return False, "text_too_short"
    if confidence < 0.15:
        return False, "low_confidence"

    alnum = sum(1 for ch in text if ch.isalnum() or ("\u4e00" <= ch <= "\u9fff"))
    if alnum < 24:
        return False, "not_enough_readable_chars"

    noisy_patterns = [
        r"\b(登录|注册|用户名|密码|扫一扫|发现|通讯录)\b",
        r"\b(login|password|register|sign in|sign up)\b",
    ]
    noise_hits = 0
    lower = text.lower()
    for pattern in noisy_patterns:
        if re.search(pattern, text, flags=re.IGNORECASE):
            noise_hits += 1
    if noise_hits >= 2 and len(text) < 140:
        return False, "likely_ui_text"

    comment_tokens = [
        "评论",
        "回复",
        "网友",
        "文明上网理性发言",
        "请先登录后发表评论",
        "内容由ai生成",
        "手机看",
        "打开小游戏",
    ]
    comment_hits = [token for token in comment_tokens if token in lower]
    reply_like_count = lower.count("回复") + lower.count("网友")
    if "请先登录后发表评论" in lower or "文明上网理性发言" in lower:
        return False, "comment_gate"
    if reply_like_count >= 3 and len(comment_hits) >= 3:
        return False, "comment_fragment"

    strong_chat_tokens = [
        "文件传输助手",
        "@所有人",
        "服务号",
        "视频号",
        "常看的号",
        "最近转发",
        "聊天信息",
        "通讯录",
        "草稿",
    ]
    weak_chat_tokens = [
        "搜索",
        "发现",
        "群聊",
        "订阅号消息",
        "小程序",
        "图片",
        "链接",
    ]
    strong_chat_hits = [token for token in strong_chat_tokens if token in lower]
    if strong_chat_hits:
        return False, "chat_ui"

    weak_chat_hits = [token for token in weak_chat_tokens if token in lower]
    timestamp_hits = len(re.findall(r"\b\d{1,2}:\d{2}\b", text))
    bracket_hits = text.count("［") + text.count("[")
    if timestamp_hits >= 3 and bracket_hits >= 2:
        return False, "chat_list_brackets"
    if len(weak_chat_hits) >= 3 and timestamp_hits >= 2 and len(text) < 900:
        return False, "chat_ui_multi"

    hub_tokens = [
        "查看历史消息",
        "历史消息",
        "全部消息",
        "进入公众号",
        "公众号名片",
        "公众号主页",
        "关注公众号",
        "篇原创内容",
        "最近更新",
        "更多文章",
        "继续滑动看下一个",
        "推荐阅读",
        "相关文章",
    ]
    hub_hits = [token for token in hub_tokens if token in lower]
    if len(hub_hits) >= 2 and len(text) < 900:
        return False, "non_article_hub"

    timeline_tokens = [
        "昨天",
        "今天",
        "小时前",
        "分钟前",
        "刚刚",
        "朋友看过",
        "订阅号消息",
    ]
    timeline_hits = [token for token in timeline_tokens if token in lower]
    if timestamp_hits >= 6 and len(text) < 600:
        return False, "timeline_feed"
    if timestamp_hits >= 4 and len(timeline_hits) >= 2 and len(text) < 900:
        return False, "timeline_feed"

    symbol_count = sum(1 for ch in text if not (ch.isalnum() or ch.isspace() or ("\u4e00" <= ch <= "\u9fff")))
    if symbol_count > len(text) * 0.35:
        return False, "high_symbol_ratio"

    return True, None


def run_ocr_preview(
    *,
    image_base64: str,
    mime_type: str,
    source_url: str | None,
    title_hint: str | None,
    output_language: str,
    vision_ocr: Any,
    clean_text: Callable[[str | None], str],
    truncate_text: Callable[[str | None, int], str],
    evaluate_quality: Callable[[str, float], tuple[bool, str | None]],
) -> CollectorOCRPreviewResponse:
    try:
        ocr_result = vision_ocr.extract(
            image_base64=image_base64,
            mime_type=mime_type,
            source_url=source_url,
            title_hint=title_hint,
            output_language=output_language,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # pragma: no cover - provider/runtime path
        raise HTTPException(status_code=500, detail=f"OCR extraction failed: {exc}") from exc

    body_text = clean_text(ocr_result.body_text)
    quality_ok, quality_reason = evaluate_quality(body_text, ocr_result.confidence)
    return CollectorOCRPreviewResponse(
        provider=ocr_result.provider,
        confidence=round(float(ocr_result.confidence), 3),
        text_length=len(body_text),
        title=truncate_text(ocr_result.title, 120),
        body_preview=truncate_text(body_text, 380),
        body_text=body_text,
        keywords=ocr_result.keywords[:8],
        quality_ok=quality_ok,
        quality_reason=quality_reason,
    )


def normalize_ocr_preview_quality_reason(
    reason: str | None,
    *,
    clean_text: Callable[[str | None], str],
) -> str:
    text = clean_text(reason)
    if not text:
        return ""
    return text.split(":", 1)[0]


def crop_preview_image_base64(
    image_base64: str,
    *,
    variant_name: str,
    image_cls: Any,
) -> str | None:
    if image_cls is None:
        return None
    profile = OCR_PREVIEW_VARIANT_PROFILES.get(variant_name)
    if profile is None:
        return None
    try:
        binary = base64.b64decode(image_base64)
        with image_cls.open(io.BytesIO(binary)) as image:
            width, height = image.size
            if width < 120 or height < 120:
                return None
            left = max(0, min(width - 60, int(width * float(profile["left"]))))
            top = max(0, min(height - 60, int(height * float(profile["top"]))))
            right = max(left + 60, min(width, int(width * float(profile["right"]))))
            bottom = max(top + 60, min(height, int(height * float(profile["bottom"]))))
            if right - left < 160 or bottom - top < 160:
                return None
            cropped = image.crop((left, top, right, bottom))
            buffer = io.BytesIO()
            cropped.save(buffer, format="PNG")
        return base64.b64encode(buffer.getvalue()).decode("utf-8")
    except Exception:
        return None


def run_ocr_preview_with_variants(
    *,
    image_base64: str,
    mime_type: str,
    source_url: str | None,
    title_hint: str | None,
    output_language: str,
    run_ocr_preview: Callable[..., CollectorOCRPreviewResponse],
    normalize_quality_reason: Callable[[str | None], str],
    crop_preview_image_base64: Callable[..., str | None],
) -> CollectorOCRPreviewResponse:
    preview = run_ocr_preview(
        image_base64=image_base64,
        mime_type=mime_type,
        source_url=source_url,
        title_hint=title_hint,
        output_language=output_language,
    )
    if preview.quality_ok:
        return preview
    retry_variants = OCR_PREVIEW_VARIANT_REASONS.get(
        normalize_quality_reason(preview.quality_reason),
        [],
    )
    for variant_name in retry_variants:
        cropped_base64 = crop_preview_image_base64(image_base64, variant_name=variant_name)
        if not cropped_base64:
            continue
        variant_preview = run_ocr_preview(
            image_base64=cropped_base64,
            mime_type="image/png",
            source_url=source_url,
            title_hint=title_hint,
            output_language=output_language,
        )
        if variant_preview.quality_ok:
            return variant_preview
    return preview
