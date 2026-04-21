from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.entities import Feedback, Item, KnowledgeEntry, KnowledgeRule
from app.services.content_extractor import normalize_text
from app.services.language import localized_text, normalize_output_language


@dataclass(slots=True)
class KnowledgeAutoArchiveResult:
    status: str
    entry: KnowledgeEntry | None = None
    reason: str | None = None
    threshold: float | None = None


def ensure_knowledge_rule(db: Session, user_id: UUID) -> KnowledgeRule:
    rule = db.scalar(select(KnowledgeRule).where(KnowledgeRule.user_id == user_id).limit(1))
    if rule:
        return rule

    rule = KnowledgeRule(user_id=user_id)
    db.add(rule)
    db.flush()
    return rule


def resolve_knowledge_title(
    *,
    item: Item,
    title: str | None = None,
    output_language: str = "zh-CN",
) -> str:
    resolved_language = normalize_output_language(output_language)
    normalized_title = normalize_text(title or item.title or "")
    is_placeholder = (
        not normalized_title
        or normalized_title.lower().startswith(("wechat auto", "wechat ocr", "untitled"))
        or normalized_title.startswith(("未命名", "主题：WeChat Auto", "主題：WeChat Auto"))
    )
    if normalized_title and not is_placeholder:
        return normalized_title[:80]

    for seed in (item.short_summary or "", item.long_summary or "", item.raw_content or ""):
        normalized_seed = normalize_text(seed)
        if not normalized_seed:
            continue
        for segment in (
            normalized_seed.replace("。", ".").replace("！", ".").replace("？", ".").split(".")
        ):
            candidate = normalize_text(segment).strip("，,、:：- ")
            if len(candidate) >= 8:
                return candidate[:80]

    return localized_text(
        resolved_language,
        {
            "zh-CN": "知识卡片",
            "zh-TW": "知識卡片",
            "en": "Knowledge card",
            "ja": "ナレッジカード",
            "ko": "지식 카드",
        },
        "知识卡片",
    )


def create_or_get_knowledge_entry(
    db: Session,
    *,
    user_id: UUID,
    item: Item,
    title: str | None,
    content: str,
    output_language: str = "zh-CN",
    reuse_existing_item: bool = False,
) -> tuple[KnowledgeEntry, bool]:
    normalized_title = resolve_knowledge_title(item=item, title=title, output_language=output_language)
    normalized_content = normalize_text(content).strip()
    if not normalized_content:
        normalized_content = localized_text(
            output_language,
            {
                "zh-CN": "暂无可归档内容",
                "zh-TW": "暫無可歸檔內容",
                "en": "No content available for archiving",
                "ja": "保存できる内容がありません",
                "ko": "보관할 내용이 없습니다",
            },
            "暂无可归档内容",
        )

    if reuse_existing_item:
        existing_by_item = db.scalar(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.user_id == user_id)
            .where(KnowledgeEntry.item_id == item.id)
            .order_by(desc(KnowledgeEntry.created_at))
            .limit(1)
        )
        if existing_by_item:
            return existing_by_item, False

    existing_exact = db.scalar(
        select(KnowledgeEntry)
        .where(KnowledgeEntry.user_id == user_id)
        .where(KnowledgeEntry.item_id == item.id)
        .where(KnowledgeEntry.title == normalized_title)
        .where(KnowledgeEntry.content == normalized_content)
        .limit(1)
    )
    if existing_exact:
        return existing_exact, False

    entry = KnowledgeEntry(
        user_id=user_id,
        item_id=item.id,
        title=normalized_title,
        content=normalized_content,
        source_domain=item.source_domain,
    )
    db.add(entry)
    db.flush()
    return entry, True


def create_or_get_standalone_knowledge_entry(
    db: Session,
    *,
    user_id: UUID,
    title: str,
    content: str,
    source_domain: str | None = None,
    collection_name: str | None = None,
    is_focus_reference: bool = False,
    metadata_payload: dict | None = None,
) -> tuple[KnowledgeEntry, bool]:
    normalized_title = normalize_text(title)[:120] or "知识卡片"
    normalized_content = normalize_text(content).strip() or "暂无可归档内容"
    normalized_collection = normalize_text(collection_name or "")[:80] or None
    normalized_source = normalize_text(source_domain or "")[:255] or None

    existing_exact = db.scalar(
        select(KnowledgeEntry)
        .where(KnowledgeEntry.user_id == user_id)
        .where(KnowledgeEntry.item_id.is_(None))
        .where(KnowledgeEntry.title == normalized_title)
        .where(KnowledgeEntry.content == normalized_content)
        .limit(1)
    )
    if existing_exact:
        if metadata_payload and not existing_exact.metadata_payload:
            existing_exact.metadata_payload = metadata_payload
        return existing_exact, False

    entry = KnowledgeEntry(
        user_id=user_id,
        item_id=None,
        title=normalized_title,
        content=normalized_content,
        source_domain=normalized_source,
        metadata_payload=metadata_payload,
        collection_name=normalized_collection,
        is_focus_reference=is_focus_reference,
    )
    db.add(entry)
    db.flush()
    return entry, True


def build_auto_archive_note(item: Item, *, output_language: str = "zh-CN") -> str:
    resolved_language = normalize_output_language(output_language or item.output_language)
    display_title = resolve_knowledge_title(item=item, output_language=resolved_language)
    tags = [normalize_text(tag.tag_name) for tag in item.tags if normalize_text(tag.tag_name)]
    tag_text = " / ".join(tags[:5]) if tags else localized_text(
        resolved_language,
        {
            "zh-CN": "待补充",
            "zh-TW": "待補充",
            "en": "Pending",
            "ja": "補完待ち",
            "ko": "보강 필요",
        },
        "待补充",
    )
    action_label = localized_text(
        resolved_language,
        {
            "zh-CN": {
                "deep_read": "建议深读",
                "later": "适合稍后再读",
                "skip": "可低优先级处理",
            }.get(item.action_suggestion or "", "建议进一步判断"),
            "zh-TW": {
                "deep_read": "建議深讀",
                "later": "適合稍後再讀",
                "skip": "可低優先級處理",
            }.get(item.action_suggestion or "", "建議進一步判斷"),
            "en": {
                "deep_read": "Worth a deep read",
                "later": "Save for later",
                "skip": "Low priority",
            }.get(item.action_suggestion or "", "Needs a closer look"),
            "ja": {
                "deep_read": "深掘り推奨",
                "later": "あとで読む候補",
                "skip": "優先度は低め",
            }.get(item.action_suggestion or "", "追加判断が必要"),
            "ko": {
                "deep_read": "깊게 읽을 가치가 있음",
                "later": "나중에 읽기 적합",
                "skip": "우선순위 낮음",
            }.get(item.action_suggestion or "", "추가 판단 필요"),
        },
        "建议进一步判断",
    )

    if resolved_language == "en":
        parts = [
            f"Topic: {display_title or 'Untitled'}",
            f"One-line brief: {item.short_summary or item.long_summary or 'No summary available.'}",
            f"Extended note: {item.long_summary or item.short_summary or 'No extended note available.'}",
            f"Tags: {tag_text}",
            f"Suggested action: {action_label}",
        ]
        return "\n".join(parts)

    if resolved_language == "ja":
        parts = [
            f"テーマ：{display_title or '無題コンテンツ'}",
            f"一言要約：{item.short_summary or item.long_summary or '要約はまだありません。'}",
            f"補足メモ：{item.long_summary or item.short_summary or '補足メモはまだありません。'}",
            f"タグ：{tag_text}",
            f"推奨アクション：{action_label}",
        ]
        return "\n".join(parts)

    if resolved_language == "ko":
        parts = [
            f"주제: {display_title or '제목 없음'}",
            f"한 줄 요약: {item.short_summary or item.long_summary or '아직 요약이 없습니다.'}",
            f"확장 메모: {item.long_summary or item.short_summary or '확장 메모가 없습니다.'}",
            f"태그: {tag_text}",
            f"권장 액션: {action_label}",
        ]
        return "\n".join(parts)

    label_map = {
        "zh-CN": {
            "topic": "主题",
            "one_line": "一句话概要",
            "extended": "扩展摘要",
            "tags": "标签",
            "action": "建议动作",
            "untitled": "未命名内容",
            "empty_summary": "暂无摘要。",
            "empty_long": "暂无扩展摘要。",
        },
        "zh-TW": {
            "topic": "主題",
            "one_line": "一句話概要",
            "extended": "延伸摘要",
            "tags": "標籤",
            "action": "建議動作",
            "untitled": "未命名內容",
            "empty_summary": "暫無摘要。",
            "empty_long": "暫無延伸摘要。",
        },
    }
    labels = label_map["zh-TW" if resolved_language == "zh-TW" else "zh-CN"]
    parts = [
        f"{labels['topic']}：{display_title or labels['untitled']}",
        f"{labels['one_line']}：{item.short_summary or item.long_summary or labels['empty_summary']}",
        f"{labels['extended']}：{item.long_summary or item.short_summary or labels['empty_long']}",
        f"{labels['tags']}：{tag_text}",
        f"{labels['action']}：{action_label}",
    ]
    return "\n".join(parts)


def maybe_auto_archive_item(
    db: Session,
    *,
    item: Item,
    trigger_feedback_type: str | None = None,
    output_language: str | None = None,
) -> KnowledgeAutoArchiveResult:
    rule = ensure_knowledge_rule(db, item.user_id)
    if not rule.enabled:
        return KnowledgeAutoArchiveResult(status="skipped", reason="disabled", threshold=float(rule.min_score_value))

    if item.status != "ready":
        return KnowledgeAutoArchiveResult(status="skipped", reason="not_ready", threshold=float(rule.min_score_value))

    if item.score_value is None:
        return KnowledgeAutoArchiveResult(status="skipped", reason="missing_score", threshold=float(rule.min_score_value))

    score_value = Decimal(str(item.score_value))
    threshold = Decimal(str(rule.min_score_value))
    if score_value < threshold:
        return KnowledgeAutoArchiveResult(status="skipped", reason="below_threshold", threshold=float(threshold))

    feedback_types = set(
        db.scalars(
            select(Feedback.feedback_type).where(
                Feedback.user_id == item.user_id,
                Feedback.item_id == item.id,
            )
        )
    )
    if trigger_feedback_type:
        feedback_types.add(trigger_feedback_type)

    matched = (rule.archive_on_like and "like" in feedback_types) or (
        rule.archive_on_save and "save" in feedback_types
    )
    if not matched:
        return KnowledgeAutoArchiveResult(status="skipped", reason="feedback_not_matched", threshold=float(threshold))

    entry, created = create_or_get_knowledge_entry(
        db,
        user_id=item.user_id,
        item=item,
        title=item.title,
        content=build_auto_archive_note(item, output_language=output_language or item.output_language),
        output_language=output_language or item.output_language,
        reuse_existing_item=True,
    )
    return KnowledgeAutoArchiveResult(
        status="created" if created else "existing",
        entry=entry,
        threshold=float(threshold),
    )
