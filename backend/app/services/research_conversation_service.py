from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.research_entities import (
    ResearchConversation,
    ResearchJob,
    ResearchMessage,
    ResearchTrackingTopic,
)
from app.models.research_entities import ResearchReportVersion
from app.services.content_extractor import normalize_text


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _load_topic(db: Session, topic_id: UUID | None) -> ResearchTrackingTopic | None:
    if topic_id is None:
        return None
    return db.scalar(select(ResearchTrackingTopic).where(ResearchTrackingTopic.id == topic_id))


def _load_job(db: Session, job_id: UUID | None) -> ResearchJob | None:
    if job_id is None:
        return None
    return db.scalar(select(ResearchJob).where(ResearchJob.id == job_id))


def _load_latest_report_for_topic(db: Session, topic_id: UUID | None) -> dict[str, Any] | None:
    if topic_id is None:
        return None
    version = db.scalar(
        select(ResearchReportVersion)
        .where(ResearchReportVersion.topic_id == topic_id)
        .order_by(desc(ResearchReportVersion.created_at))
        .limit(1)
    )
    if version is None:
        return None
    return version.report_payload


def _relevant_sources(report: dict[str, Any] | None, question: str, limit: int = 3) -> list[dict[str, str]]:
    if not isinstance(report, dict):
        return []
    normalized_question = normalize_text(question).lower()
    rows: list[dict[str, str]] = []
    for source in list(report.get("sources") or []):
        title = normalize_text(str(source.get("title") or ""))
        snippet = normalize_text(str(source.get("snippet") or ""))
        url = normalize_text(str(source.get("url") or ""))
        if not url:
            continue
        score = 0
        if title and any(token and token in title.lower() for token in normalized_question.split()):
            score += 2
        if snippet and any(token and token in snippet.lower() for token in normalized_question.split()):
            score += 1
        rows.append(
            {
                "title": title or url,
                "url": url,
                "meta": f"{source.get('source_tier') or 'media'} / {source.get('source_type') or 'web'}",
                "score": str(score),
            }
        )
    rows.sort(key=lambda item: int(item["score"]), reverse=True)
    return rows[:limit]


def _pick_report_rows(report: dict[str, Any] | None, keys: list[str], limit: int = 3) -> list[str]:
    if not isinstance(report, dict):
        return []
    collected: list[str] = []
    for key in keys:
        values = report.get(key)
        if key == "sections" and isinstance(values, list):
            for section in values:
                if not isinstance(section, dict):
                    continue
                for item in list(section.get("items") or []):
                    text = normalize_text(str(item or ""))
                    if not text or text in collected:
                        continue
                    collected.append(text)
                    if len(collected) >= limit:
                        return collected
            continue
        if not isinstance(values, list):
            continue
        for value in values:
            text = normalize_text(str(value or ""))
            if not text or text in collected:
                continue
            collected.append(text)
            if len(collected) >= limit:
                return collected
    return collected


def _build_followups(report: dict[str, Any] | None) -> list[str]:
    if not isinstance(report, dict):
        return []
    query_plan = [normalize_text(item) for item in list(report.get("query_plan") or []) if normalize_text(item)]
    if query_plan:
        return query_plan[:3]
    keyword = normalize_text(str(report.get("keyword") or "该专题"))
    return [
        f"{keyword} 下一步最值得验证的公开招采信号是什么？",
        f"{keyword} 还有哪些甲方或伙伴没有被证据充分覆盖？",
        f"{keyword} 近 3 个月最值得跟踪的预算/时间节点是什么？",
    ]


def build_research_followup_answer(
    *,
    question: str,
    report: dict[str, Any] | None,
    topic_name: str | None = None,
    job_keyword: str | None = None,
) -> tuple[str, dict[str, Any]]:
    normalized_question = normalize_text(question).lower()
    rows: list[str]
    if any(token in normalized_question for token in ("时间", "timeline", "排期", "节奏", "招标")):
        rows = _pick_report_rows(report, ["tender_timeline", "budget_signals", "project_distribution"])
    elif any(token in normalized_question for token in ("预算", "budget", "采购", "立项")):
        rows = _pick_report_rows(report, ["budget_signals", "project_distribution", "tender_timeline"])
    elif any(token in normalized_question for token in ("甲方", "客户", "target", "buyer")):
        rows = _pick_report_rows(report, ["target_accounts", "public_contact_channels", "account_team_signals"])
    elif any(token in normalized_question for token in ("竞品", "竞争", "competitor")):
        rows = _pick_report_rows(report, ["competitor_profiles", "competition_analysis", "winner_peer_moves"])
    elif any(token in normalized_question for token in ("伙伴", "生态", "partner", "渠道")):
        rows = _pick_report_rows(report, ["ecosystem_partners", "strategic_directions", "benchmark_cases"])
    else:
        rows = _pick_report_rows(report, ["sections", "strategic_directions", "leadership_focus"])  # type: ignore[list-item]

    if not rows and isinstance(report, dict):
        executive_summary = normalize_text(str(report.get("executive_summary") or ""))
        consulting_angle = normalize_text(str(report.get("consulting_angle") or ""))
        rows = [value for value in [executive_summary, consulting_angle] if value][:3]

    sources = _relevant_sources(report, question)
    followups = _build_followups(report)
    topic_label = topic_name or job_keyword or normalize_text(str((report or {}).get("keyword") or "当前专题")) or "当前专题"

    answer_lines = [f"## 当前判断", *[f"- {row}" for row in rows[:3]]]
    if not rows:
        answer_lines.append("- 当前还没有足够的结构化证据，建议先刷新专题或补充范围。")
    if sources:
        answer_lines.extend(["", "## 关键证据"])
        answer_lines.extend([f"- [{source['title']}]({source['url']}) · {source['meta']}" for source in sources])
    if followups:
        answer_lines.extend(["", "## 下一步追问"])
        answer_lines.extend([f"- {row}" for row in followups[:3]])

    return "\n".join(answer_lines), {
        "topic_label": topic_label,
        "source_links": sources,
        "suggested_followups": followups[:3],
    }


def _serialize_message(message: ResearchMessage) -> dict[str, Any]:
    return {
        "id": str(message.id),
        "conversation_id": str(message.conversation_id),
        "role": message.role,
        "message_type": message.message_type,
        "content": message.content,
        "payload": message.payload or {},
        "created_at": message.created_at,
    }


def _serialize_conversation(
    conversation: ResearchConversation,
    messages: list[ResearchMessage],
) -> dict[str, Any]:
    return {
        "id": str(conversation.id),
        "topic_id": str(conversation.topic_id) if conversation.topic_id else None,
        "job_id": str(conversation.job_id) if conversation.job_id else None,
        "title": conversation.title,
        "status": conversation.status,
        "context_payload": conversation.context_payload or {},
        "created_at": conversation.created_at,
        "updated_at": conversation.updated_at,
        "messages": [_serialize_message(message) for message in messages],
    }


def list_research_conversations(db: Session, *, user_id: UUID, limit: int = 12) -> list[dict[str, Any]]:
    conversations = list(
        db.scalars(
            select(ResearchConversation)
            .where(ResearchConversation.user_id == user_id)
            .order_by(desc(ResearchConversation.updated_at))
            .limit(limit)
        )
    )
    results: list[dict[str, Any]] = []
    for conversation in conversations:
        messages = list(
            db.scalars(
                select(ResearchMessage)
                .where(ResearchMessage.conversation_id == conversation.id)
                .order_by(ResearchMessage.created_at.asc())
            )
        )
        results.append(_serialize_conversation(conversation, messages))
    return results


def get_research_conversation(db: Session, *, user_id: UUID, conversation_id: UUID) -> dict[str, Any] | None:
    conversation = db.scalar(
        select(ResearchConversation)
        .where(ResearchConversation.id == conversation_id)
        .where(ResearchConversation.user_id == user_id)
    )
    if conversation is None:
        return None
    messages = list(
        db.scalars(
            select(ResearchMessage)
            .where(ResearchMessage.conversation_id == conversation.id)
            .order_by(ResearchMessage.created_at.asc())
        )
    )
    return _serialize_conversation(conversation, messages)


def create_research_conversation(
    db: Session,
    *,
    user_id: UUID,
    title: str | None = None,
    topic_id: UUID | None = None,
    job_id: UUID | None = None,
) -> dict[str, Any]:
    topic = _load_topic(db, topic_id)
    job = _load_job(db, job_id)
    report = job.report_payload if job and job.report_payload else _load_latest_report_for_topic(db, topic_id)
    topic_label = normalize_text(title or "") or (topic.name if topic else "") or (job.keyword if job else "") or "研究对话"
    conversation = ResearchConversation(
        user_id=user_id,
        topic_id=topic.id if topic else None,
        job_id=job.id if job else None,
        title=topic_label,
        status="active",
        context_payload={
            "topic_name": topic.name if topic else None,
            "job_keyword": job.keyword if job else None,
            "report_keyword": (report or {}).get("keyword") if isinstance(report, dict) else None,
        },
    )
    db.add(conversation)
    db.flush()

    if isinstance(report, dict):
        bootstrap, payload = build_research_followup_answer(
            question="当前专题的基线判断是什么？",
            report=report,
            topic_name=topic.name if topic else None,
            job_keyword=job.keyword if job else None,
        )
        db.add(
            ResearchMessage(
                conversation_id=conversation.id,
                role="assistant",
                message_type="summary",
                content=bootstrap,
                payload=payload,
            )
        )
    db.commit()
    return get_research_conversation(db, user_id=user_id, conversation_id=conversation.id) or {}


def add_research_conversation_message(
    db: Session,
    *,
    user_id: UUID,
    conversation_id: UUID,
    content: str,
) -> dict[str, Any] | None:
    conversation = db.scalar(
        select(ResearchConversation)
        .where(ResearchConversation.id == conversation_id)
        .where(ResearchConversation.user_id == user_id)
    )
    if conversation is None:
        return None

    question = normalize_text(content)
    if not question:
        raise ValueError("message content is required")

    db.add(
        ResearchMessage(
            conversation_id=conversation.id,
            role="user",
            message_type="question",
            content=question,
            payload={},
        )
    )

    job = _load_job(db, conversation.job_id)
    topic = _load_topic(db, conversation.topic_id)
    report = job.report_payload if job and job.report_payload else _load_latest_report_for_topic(db, conversation.topic_id)
    answer, payload = build_research_followup_answer(
        question=question,
        report=report,
        topic_name=topic.name if topic else None,
        job_keyword=job.keyword if job else None,
    )
    db.add(
        ResearchMessage(
            conversation_id=conversation.id,
            role="assistant",
            message_type="answer",
            content=answer,
            payload=payload,
        )
    )
    conversation.updated_at = _utc_now()
    db.add(conversation)
    db.commit()
    return get_research_conversation(db, user_id=user_id, conversation_id=conversation_id)
