from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable

from sqlalchemy import and_, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import FocusSession, Item, SessionItem
from app.services.language import localized_text, normalize_output_language
from app.services.session_summarizer import SessionSummarizer


session_summarizer = SessionSummarizer()


@dataclass(slots=True)
class SessionMetrics:
    new_content_count: int
    deep_read_count: int
    later_count: int
    skip_count: int


def gather_items_in_window(
    db: Session,
    *,
    user_id,
    start_time: datetime,
    end_time: datetime,
) -> list[Item]:
    # SQLite `CURRENT_TIMESTAMP` is second-level precision in many environments.
    # FocusSession start_time is Python datetime with microseconds.
    # If an item is created within the same second as start_time, strict >= start_time
    # may exclude it. Apply a small boundary tolerance.
    start_boundary = start_time.replace(microsecond=0) - timedelta(seconds=1)
    return list(
        db.scalars(
            select(Item)
            .where(Item.user_id == user_id)
            .where(and_(Item.created_at >= start_boundary, Item.created_at <= end_time))
            .options(selectinload(Item.tags))
            .order_by(Item.created_at.asc())
        )
    )


def compute_session_metrics(items: Iterable[Item]) -> SessionMetrics:
    new_count = 0
    deep = 0
    later = 0
    skip = 0
    for item in items:
        new_count += 1
        if item.action_suggestion == "deep_read":
            deep += 1
        elif item.action_suggestion == "later":
            later += 1
        else:
            skip += 1

    return SessionMetrics(
        new_content_count=new_count,
        deep_read_count=deep,
        later_count=later,
        skip_count=skip,
    )


def sync_session_items(db: Session, session: FocusSession, items: list[Item]) -> None:
    existing_ids = {
        row.item_id
        for row in db.scalars(
            select(SessionItem).where(SessionItem.session_id == session.id)
        )
    }
    for item in items:
        if item.id in existing_ids:
            continue
        db.add(SessionItem(session_id=session.id, item_id=item.id))


def sync_running_sessions_for_item(db: Session, item: Item) -> int:
    if not item.user_id or not item.created_at:
        return 0

    sessions = list(
        db.scalars(
            select(FocusSession)
            .where(FocusSession.user_id == item.user_id)
            .where(FocusSession.status == "running")
            .where(FocusSession.start_time <= item.created_at)
        )
    )
    if not sessions:
        return 0

    added = 0
    for session in sessions:
        exists = db.scalar(
            select(SessionItem)
            .where(SessionItem.session_id == session.id)
            .where(SessionItem.item_id == item.id)
            .limit(1)
        )
        if exists:
            continue
        db.add(SessionItem(session_id=session.id, item_id=item.id))
        added += 1
    return added


def _format_action_label(action: str | None, output_language: str) -> str:
    if action == "deep_read":
        return localized_text(
            output_language,
            {"zh-CN": "建议深读", "zh-TW": "建議深讀", "en": "deep read", "ja": "深読み", "ko": "정독 권장"},
            "建议深读",
        )
    if action == "skip":
        return localized_text(
            output_language,
            {"zh-CN": "可忽略", "zh-TW": "可忽略", "en": "skip", "ja": "スキップ", "ko": "건너뛰기"},
            "可忽略",
        )
    return localized_text(
        output_language,
        {"zh-CN": "稍后读", "zh-TW": "稍後讀", "en": "later", "ja": "後で読む", "ko": "나중에 읽기"},
        "稍后读",
    )


def _build_summary_payload(
    goal_text: str | None,
    items: list[Item],
    metrics: SessionMetrics,
    output_language: str,
) -> dict:
    goal = (goal_text or localized_text(
        output_language,
        {
            "zh-CN": "完成一次专注任务",
            "zh-TW": "完成一次專注任務",
            "en": "finish one focused session",
            "ja": "1回の集中セッションを完了する",
            "ko": "한 번의 집중 세션 완료",
        },
        "完成一次专注任务",
    )).strip()
    highlights = []
    for item in items[:5]:
        title = item.title or localized_text(
            output_language,
            {
                "zh-CN": "未命名内容",
                "zh-TW": "未命名內容",
                "en": "Untitled item",
                "ja": "無題コンテンツ",
                "ko": "제목 없음",
            },
            "未命名内容",
        )
        action = _format_action_label(item.action_suggestion, output_language)
        wrapper_left = "（" if normalize_output_language(output_language) in {"zh-CN", "zh-TW", "ja"} else "("
        wrapper_right = "）" if wrapper_left == "（" else ")"
        highlights.append(f"{title}{wrapper_left}{action}{wrapper_right}")

    separator = "、" if normalize_output_language(output_language) in {"zh-CN", "zh-TW", "ja"} else ", "
    first_line = separator.join(highlights) if highlights else localized_text(
        output_language,
        {
            "zh-CN": "暂无新增内容",
            "zh-TW": "暫無新增內容",
            "en": "No new items during this session.",
            "ja": "このセッション中の新規項目はありません。",
            "ko": "이번 세션 동안 새 항목이 없습니다.",
        },
        "暂无新增内容",
    )
    summary_template = localized_text(
        output_language,
        {
            "zh-CN": (
                "你已完成本次专注，没有被新信息打断。围绕“{goal}”的新增内容共 {new_count} 条，"
                "其中建议深读 {deep_count} 条、稍后读 {later_count} 条、可忽略 {skip_count} 条。"
                "优先处理：{highlights}。建议先看深读项，再批量处理稍后读，其余可归档。"
            ),
            "zh-TW": (
                "你已完成本次專注，未被新資訊打斷。圍繞「{goal}」的新增內容共 {new_count} 條，"
                "其中建議深讀 {deep_count} 條、稍後讀 {later_count} 條、可忽略 {skip_count} 條。"
                "優先處理：{highlights}。建議先看深讀項，再批次處理稍後讀，其餘可歸檔。"
            ),
            "en": (
                "You completed this focus block without interruptions. Around \"{goal}\", "
                "there are {new_count} new items: deep read {deep_count}, later {later_count}, skip {skip_count}. "
                "Priority list: {highlights}. Start with deep reads, then batch-process later items, and archive the rest."
            ),
            "ja": (
                "今回の集中セッションを中断なく完了しました。目標「{goal}」に関連する新着は {new_count} 件で、"
                "深読み {deep_count} 件、後で読む {later_count} 件、スキップ {skip_count} 件です。"
                "優先項目: {highlights}。まず深読みから着手し、その後に後で読む項目をまとめて処理してください。"
            ),
            "ko": (
                "이번 집중 세션을 방해 없이 완료했습니다. 목표 \"{goal}\" 기준 신규 항목은 {new_count}개이며, "
                "정독 {deep_count}개, 나중에 읽기 {later_count}개, 건너뛰기 {skip_count}개입니다. "
                "우선순위: {highlights}. 먼저 정독 항목을 처리하고, 이후 나중에 읽기 항목을 묶어 처리하세요."
            ),
        },
        "你已完成本次专注。",
    )
    summary_text = summary_template.format(
        goal=goal,
        new_count=metrics.new_content_count,
        deep_count=metrics.deep_read_count,
        later_count=metrics.later_count,
        skip_count=metrics.skip_count,
        highlights=first_line,
    )
    return {"summary_text": summary_text}


def _build_session_items_summary_list(items: list[Item], output_language: str) -> str:
    if not items:
        return localized_text(
            output_language,
            {
                "zh-CN": "暂无新增内容。",
                "zh-TW": "暫無新增內容。",
                "en": "No new content.",
                "ja": "新規コンテンツはありません。",
                "ko": "새 콘텐츠가 없습니다.",
            },
            "暂无新增内容。",
        )

    lines: list[str] = []
    for item in items[:10]:
        title = item.title or localized_text(
            output_language,
            {
                "zh-CN": "未命名内容",
                "zh-TW": "未命名內容",
                "en": "Untitled item",
                "ja": "無題コンテンツ",
                "ko": "제목 없음",
            },
            "未命名内容",
        )
        action = _format_action_label(item.action_suggestion, output_language)
        summary = (
            item.short_summary
            or item.long_summary
            or localized_text(
                output_language,
                {
                    "zh-CN": "暂无摘要",
                    "zh-TW": "暫無摘要",
                    "en": "No summary yet",
                    "ja": "要約なし",
                    "ko": "요약 없음",
                },
                "暂无摘要",
            )
        ).strip()
        lines.append(f"- {title} | {action} | {summary[:120]}")
    return "\n".join(lines)


def generate_session_summary_text(
    goal_text: str | None,
    items: list[Item],
    metrics: SessionMetrics,
    *,
    output_language: str = "zh-CN",
) -> str:
    resolved_language = normalize_output_language(output_language)
    goal = (
        goal_text
        or localized_text(
            resolved_language,
            {
                "zh-CN": "完成一次专注任务",
                "zh-TW": "完成一次專注任務",
                "en": "finish one focused session",
                "ja": "1回の集中セッションを完了する",
                "ko": "한 번의 집중 세션 완료",
            },
            "完成一次专注任务",
        )
    ).strip()
    session_items_summary_list = _build_session_items_summary_list(items, resolved_language)

    try:
        result = session_summarizer.summarize(
            goal_text=goal,
            session_items_summary_list=session_items_summary_list,
            output_language=resolved_language,
        )
        summary_text = (result.summary_text or "").strip()
        if summary_text:
            return summary_text
    except Exception:
        pass

    payload = _build_summary_payload(goal, items, metrics, resolved_language)
    return payload["summary_text"]


def finish_session(
    db: Session,
    session: FocusSession,
    *,
    output_language: str | None = None,
) -> tuple[FocusSession, list[Item], SessionMetrics]:
    if session.status != "running":
        raise ValueError("Session is not running")

    resolved_language = normalize_output_language(output_language or session.output_language)
    session.output_language = resolved_language
    session.end_time = datetime.now(timezone.utc)
    session.status = "finished"

    items = gather_items_in_window(
        db,
        user_id=session.user_id,
        start_time=session.start_time,
        end_time=session.end_time,
    )
    sync_session_items(db, session, items)

    metrics = compute_session_metrics(items)
    session.summary_text = generate_session_summary_text(
        session.goal_text,
        items,
        metrics,
        output_language=resolved_language,
    )
    db.add(session)
    return session, items, metrics
