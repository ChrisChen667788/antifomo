from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.models.entities import FocusSession, Item, KnowledgeEntry, SessionItem, WorkTask
from app.models.research_entities import ResearchWatchlistChangeEvent
from app.schemas.research import ResearchReportDocument
from app.services.knowledge_intelligence_service import (
    build_knowledge_commercial_dashboard,
    get_knowledge_account_detail,
    list_knowledge_accounts,
)
from app.services.language import normalize_output_language
from app.services.session_artifact_service import persist_session_artifact
from app.services.session_service import (
    compute_session_metrics,
    generate_session_summary_text,
    list_session_items,
)
from app.services.work_task_service import (
    build_feasibility_study_pdf_document,
    build_feasibility_study_word_document,
    build_knowledge_bundle_markdown,
    build_knowledge_markdown,
    build_markdown_summary,
    build_project_proposal_pdf_document,
    build_project_proposal_word_document,
    build_research_pdf_document,
    build_reading_list,
    build_research_markdown,
    build_research_word_document,
    build_artifact_item_snapshots,
    build_exec_brief,
    build_todo_draft,
    build_outreach_draft,
    build_sales_brief,
    build_watchlist_digest,
    complete_task,
    fail_task,
    sanitize_task_context_payload,
    select_reading_list_items,
    select_summary_items,
    select_todo_items,
)


def _load_session_for_user(db: Session, *, user_id: UUID, session_id: UUID) -> FocusSession:
    session = db.scalar(
        select(FocusSession)
        .where(FocusSession.id == session_id)
        .where(FocusSession.user_id == user_id)
        .options(
            selectinload(FocusSession.session_items)
            .selectinload(SessionItem.item)
            .selectinload(Item.tags)
        )
    )
    if not session:
        raise ValueError("Session not found")
    return session


def _items_for_session(db: Session, session: FocusSession) -> list[Item]:
    return list_session_items(db, session, now=datetime.now(timezone.utc))


def _latest_items(db: Session, *, user_id: UUID, limit: int = 20) -> list[Item]:
    return list(
        db.scalars(
            select(Item)
            .where(Item.user_id == user_id)
            .options(selectinload(Item.tags))
            .order_by(desc(Item.created_at))
            .limit(limit)
        )
    )


def _latest_watchlist_changes(db: Session, limit: int = 8) -> list[ResearchWatchlistChangeEvent]:
    return list(
        db.scalars(
            select(ResearchWatchlistChangeEvent)
            .order_by(desc(ResearchWatchlistChangeEvent.created_at))
            .limit(limit)
        )
    )


def _compact_task_account_context(detail: dict | None) -> dict | None:
    if not isinstance(detail, dict):
        return None
    return {
        "slug": str(detail.get("slug") or ""),
        "name": str(detail.get("name") or ""),
        "objective": str(((detail.get("account_plan") or {}) if isinstance(detail.get("account_plan"), dict) else {}).get("objective") or ""),
        "value_hypothesis": str(((detail.get("account_plan") or {}) if isinstance(detail.get("account_plan"), dict) else {}).get("value_hypothesis") or ""),
        "next_meeting_goal": str(((detail.get("account_plan") or {}) if isinstance(detail.get("account_plan"), dict) else {}).get("next_meeting_goal") or ""),
        "why_now": [str(value or "").strip() for value in (detail.get("why_now") or []) if str(value or "").strip()][:3],
        "stakeholders": [
            {
                "name": str(item.get("name") or ""),
                "role": str(item.get("role") or ""),
                "priority": str(item.get("priority") or ""),
                "next_move": str(item.get("next_move") or ""),
            }
            for item in (detail.get("stakeholder_map") or [])[:4]
            if isinstance(item, dict)
        ],
        "close_plan": [
            {
                "title": str(item.get("title") or ""),
                "owner": str(item.get("owner") or ""),
                "due_window": str(item.get("due_window") or ""),
                "exit_criteria": str(item.get("exit_criteria") or ""),
            }
            for item in (detail.get("close_plan") or [])[:4]
            if isinstance(item, dict)
        ],
        "pipeline_risks": [
            {
                "title": str(item.get("title") or ""),
                "severity": str(item.get("severity") or "medium"),
                "detail": str(item.get("detail") or ""),
                "mitigation": str(item.get("mitigation") or ""),
            }
            for item in (detail.get("pipeline_risks") or [])[:4]
            if isinstance(item, dict)
        ],
    }


def _compact_dashboard_context(dashboard: dict | None) -> dict:
    if not isinstance(dashboard, dict):
        return {"top_accounts": [], "top_opportunities": [], "top_alerts": [], "review_queue": []}
    return {
        "top_accounts": [
            {
                "slug": str(item.get("slug") or ""),
                "name": str(item.get("name") or ""),
                "budget_probability": int(item.get("budget_probability") or 0),
                "next_best_action": str(item.get("next_best_action") or ""),
            }
            for item in (dashboard.get("top_accounts") or [])[:3]
            if isinstance(item, dict)
        ],
        "top_opportunities": [
            {
                "title": str(item.get("title") or ""),
                "account_name": str(item.get("account_name") or ""),
                "budget_probability": int(item.get("budget_probability") or 0),
                "next_step": str(item.get("next_step") or ""),
            }
            for item in (dashboard.get("top_opportunities") or [])[:3]
            if isinstance(item, dict)
        ],
        "top_alerts": [
            {
                "title": str(item.get("title") or ""),
                "severity": str(item.get("severity") or "medium"),
                "summary": str(item.get("summary") or ""),
                "account_name": str(item.get("account_name") or ""),
                "recommended_action": str(item.get("recommended_action") or ""),
            }
            for item in (dashboard.get("top_alerts") or [])[:4]
            if isinstance(item, dict)
        ],
        "review_queue": [
            {
                "id": str(item.get("id") or ""),
                "title": str(item.get("title") or ""),
                "severity": str(item.get("severity") or "medium"),
                "summary": str(item.get("summary") or ""),
                "account_name": str(item.get("account_name") or ""),
                "recommended_action": str(item.get("recommended_action") or ""),
                "resolution_status": str(item.get("resolution_status") or "open"),
            }
            for item in (dashboard.get("review_queue") or [])[:4]
            if isinstance(item, dict)
        ],
    }


def _build_task_knowledge_context(
    db: Session,
    *,
    report_payload: dict | None,
) -> dict:
    dashboard = build_knowledge_commercial_dashboard(db)
    compact_dashboard = _compact_dashboard_context(dashboard)

    candidate_names: list[str] = []
    if isinstance(report_payload, dict):
        try:
            report = ResearchReportDocument.model_validate(report_payload)
        except Exception:
            report = None
        if report is not None:
            candidate_names.extend([item.name for item in report.top_target_accounts[:3] if getattr(item, "name", "")])
            candidate_names.extend([value for value in report.target_accounts[:3] if value])
            candidate_names.extend([value for value in report.commercial_summary.account_focus[:2] if value])

    account_detail = None
    for name in candidate_names:
        matches = list_knowledge_accounts(db, query=name, limit=3)
        if not matches:
            continue
        exact = next((row for row in matches if str(row.get("name") or "").strip() == str(name).strip()), matches[0])
        slug = str(exact.get("slug") or "").strip()
        if not slug:
            continue
        account_detail = get_knowledge_account_detail(db, slug)
        if account_detail:
            break

    if account_detail is None and compact_dashboard["top_accounts"]:
        fallback_slug = str(compact_dashboard["top_accounts"][0].get("slug") or "").strip()
        if fallback_slug:
            account_detail = get_knowledge_account_detail(db, fallback_slug)

    return {
        "account": _compact_task_account_context(account_detail),
        **compact_dashboard,
    }


def _load_knowledge_entry_for_user(db: Session, *, user_id: UUID, entry_id: UUID) -> KnowledgeEntry:
    entry = db.scalar(
        select(KnowledgeEntry)
        .where(KnowledgeEntry.id == entry_id)
        .where(KnowledgeEntry.user_id == user_id)
    )
    if not entry:
        raise ValueError("Knowledge entry not found")
    return entry


def _load_knowledge_entries_for_user(
    db: Session,
    *,
    user_id: UUID,
    entry_ids: list[UUID],
) -> list[KnowledgeEntry]:
    unique_ids = list(dict.fromkeys(entry_ids))
    if not unique_ids:
        raise ValueError("Knowledge entry ids are required")
    entries = list(
        db.scalars(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.user_id == user_id)
            .where(KnowledgeEntry.id.in_(unique_ids))
        )
    )
    if len(entries) != len(unique_ids):
        raise ValueError("Some knowledge entries were not found")
    order = {entry_id: index for index, entry_id in enumerate(unique_ids)}
    entries.sort(key=lambda entry: order.get(entry.id, 0))
    return entries


def _artifact_payload(
    db: Session,
    *,
    task: WorkTask,
    artifact_type: str,
    markdown: str,
    items: list[dict],
) -> dict:
    artifact = persist_session_artifact(
        db,
        task=task,
        artifact_type=artifact_type,
        markdown=markdown,
        items=items,
    )
    return {
        "artifact_id": str(artifact.id),
        "artifact_type": artifact_type,
        "artifact_items": items,
    }


def create_and_execute_task(
    db: Session,
    *,
    user_id: UUID,
    task_type: str,
    session_id: UUID | None = None,
    input_payload: dict | None = None,
) -> WorkTask:
    task = WorkTask(
        user_id=user_id,
        session_id=session_id,
        task_type=task_type,
        input_payload=input_payload or {},
        status="processing",
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    try:
        payload_language = None
        assistant_context = None
        if isinstance(input_payload, dict):
            language_value = input_payload.get("output_language")
            if isinstance(language_value, str):
                payload_language = language_value
            context_value = input_payload.get("assistant_context")
            if isinstance(context_value, dict):
                assistant_context = context_value

        session: FocusSession | None = None
        items: list[Item]
        if session_id:
            session = _load_session_for_user(db, user_id=user_id, session_id=session_id)
            items = _items_for_session(db, session)
        else:
            items = _latest_items(db, user_id=user_id, limit=20)

        resolved_language = normalize_output_language(
            payload_language or (session.output_language if session else None) or (items[0].output_language if items else None)
        )
        report_payload = input_payload.get("report") if isinstance(input_payload, dict) and isinstance(input_payload.get("report"), dict) else None
        knowledge_context = (
            _build_task_knowledge_context(
                db,
                report_payload=report_payload,
            )
            if task_type in {"export_exec_brief", "export_sales_brief", "export_outreach_draft", "export_watchlist_digest"}
            else None
        )
        sanitized_knowledge_context = sanitize_task_context_payload(knowledge_context)

        if task_type == "export_markdown_summary":
            if not session:
                raise ValueError("session_id is required for export_markdown_summary")
            metrics = compute_session_metrics(items)
            summary_text_override = None
            if normalize_output_language(session.output_language) != resolved_language:
                summary_text_override = generate_session_summary_text(
                    session.goal_text,
                    items,
                    metrics,
                    output_language=resolved_language,
                )
            content = build_markdown_summary(
                session,
                metrics,
                items,
                output_language=resolved_language,
                summary_text_override=summary_text_override,
                assistant_context=assistant_context,
            )
            summary_items = build_artifact_item_snapshots(
                select_summary_items(items),
                included_reason="deep_read_recommendation",
            )
            complete_task(
                task,
                content=content,
                extra_payload={
                    "format": "markdown",
                    "output_language": resolved_language,
                    **_artifact_payload(
                        db,
                        task=task,
                        artifact_type="markdown_summary",
                        markdown=content,
                        items=summary_items,
                    ),
                },
            )
        elif task_type == "export_reading_list":
            content = build_reading_list(
                items,
                output_language=resolved_language,
                assistant_context=assistant_context,
            )
            reading_items = build_artifact_item_snapshots(
                select_reading_list_items(items),
                included_reason="reading_list_candidate",
            )
            complete_task(
                task,
                content=content,
                extra_payload={
                    "format": "markdown",
                    "output_language": resolved_language,
                    **_artifact_payload(
                        db,
                        task=task,
                        artifact_type="reading_list",
                        markdown=content,
                        items=reading_items,
                    ),
                },
            )
        elif task_type == "export_todo_draft":
            if not session:
                raise ValueError("session_id is required for export_todo_draft")
            content = build_todo_draft(
                session,
                items,
                output_language=resolved_language,
                assistant_context=assistant_context,
            )
            todo_items = build_artifact_item_snapshots(
                select_todo_items(items),
                included_reason="todo_followup",
            )
            complete_task(
                task,
                content=content,
                extra_payload={
                    "format": "markdown",
                    "output_language": resolved_language,
                    **_artifact_payload(
                        db,
                        task=task,
                        artifact_type="todo_draft",
                        markdown=content,
                        items=todo_items,
                    ),
                },
            )
        elif task_type == "export_knowledge_markdown":
            if not isinstance(input_payload, dict) or not input_payload.get("entry_id"):
                raise ValueError("input_payload.entry_id is required for export_knowledge_markdown")
            entry_id = UUID(str(input_payload["entry_id"]))
            entry = _load_knowledge_entry_for_user(db, user_id=user_id, entry_id=entry_id)
            filename, content = build_knowledge_markdown(entry, output_language=resolved_language)
            complete_task(
                task,
                content=content,
                extra_payload={
                    "format": "markdown",
                    "filename": filename,
                    "entry_id": str(entry.id),
                    "output_language": resolved_language,
                },
            )
        elif task_type == "export_knowledge_bundle_markdown":
            if not isinstance(input_payload, dict) or not input_payload.get("entry_ids"):
                raise ValueError("input_payload.entry_ids is required for export_knowledge_bundle_markdown")
            raw_ids = input_payload["entry_ids"]
            if not isinstance(raw_ids, list) or not raw_ids:
                raise ValueError("input_payload.entry_ids must be a non-empty list")
            entries = _load_knowledge_entries_for_user(
                db,
                user_id=user_id,
                entry_ids=[UUID(str(value)) for value in raw_ids],
            )
            title = input_payload.get("title") if isinstance(input_payload.get("title"), str) else None
            filename, content = build_knowledge_bundle_markdown(
                entries,
                output_language=resolved_language,
                title=title,
            )
            complete_task(
                task,
                content=content,
                extra_payload={
                    "format": "markdown",
                    "filename": filename,
                    "entry_ids": [str(entry.id) for entry in entries],
                    "entry_count": len(entries),
                    "output_language": resolved_language,
                },
            )
        elif task_type in {
            "export_research_report_markdown",
            "export_research_report_word",
            "export_research_report_pdf",
            "export_feasibility_study_word",
            "export_feasibility_study_pdf",
            "export_project_proposal_word",
            "export_project_proposal_pdf",
        }:
            if not isinstance(input_payload, dict) or not isinstance(input_payload.get("report"), dict):
                raise ValueError(f"input_payload.report is required for {task_type}")
            delivery_supplement = (
                input_payload.get("delivery_supplement")
                if isinstance(input_payload.get("delivery_supplement"), dict)
                else None
            )
            if task_type == "export_research_report_markdown":
                filename, content = build_research_markdown(
                    input_payload["report"],
                    output_language=resolved_language,
                )
                complete_task(
                    task,
                    content=content,
                    extra_payload={
                        "format": "markdown",
                        "filename": filename,
                        "output_language": resolved_language,
                    },
                )
            elif task_type == "export_research_report_word":
                filename, content, mime_type = build_research_word_document(
                    input_payload["report"],
                    output_language=resolved_language,
                )
                complete_task(
                    task,
                    content=content,
                    extra_payload={
                        "format": "word",
                        "filename": filename,
                        "mime_type": mime_type,
                        "output_language": resolved_language,
                    },
                )
            elif task_type == "export_research_report_pdf":
                filename, preview_content, content_base64, mime_type = build_research_pdf_document(
                    input_payload["report"],
                    output_language=resolved_language,
                )
                complete_task(
                    task,
                    content=preview_content,
                    extra_payload={
                        "format": "pdf",
                        "filename": filename,
                        "mime_type": mime_type,
                        "content_base64": content_base64,
                        "output_language": resolved_language,
                    },
                )
            elif task_type == "export_feasibility_study_word":
                filename, content, mime_type = build_feasibility_study_word_document(
                    input_payload["report"],
                    output_language=resolved_language,
                    delivery_supplement=delivery_supplement,
                )
                complete_task(
                    task,
                    content=content,
                    extra_payload={
                        "format": "word",
                        "filename": filename,
                        "mime_type": mime_type,
                        "output_language": resolved_language,
                        "document_kind": "feasibility_study",
                    },
                )
            elif task_type == "export_feasibility_study_pdf":
                filename, preview_content, content_base64, mime_type = build_feasibility_study_pdf_document(
                    input_payload["report"],
                    output_language=resolved_language,
                    delivery_supplement=delivery_supplement,
                )
                complete_task(
                    task,
                    content=preview_content,
                    extra_payload={
                        "format": "pdf",
                        "filename": filename,
                        "mime_type": mime_type,
                        "content_base64": content_base64,
                        "output_language": resolved_language,
                        "document_kind": "feasibility_study",
                    },
                )
            elif task_type == "export_project_proposal_word":
                filename, content, mime_type = build_project_proposal_word_document(
                    input_payload["report"],
                    output_language=resolved_language,
                    delivery_supplement=delivery_supplement,
                )
                complete_task(
                    task,
                    content=content,
                    extra_payload={
                        "format": "word",
                        "filename": filename,
                        "mime_type": mime_type,
                        "output_language": resolved_language,
                        "document_kind": "project_proposal",
                    },
                )
            else:
                filename, preview_content, content_base64, mime_type = build_project_proposal_pdf_document(
                    input_payload["report"],
                    output_language=resolved_language,
                    delivery_supplement=delivery_supplement,
                )
                complete_task(
                    task,
                    content=preview_content,
                    extra_payload={
                        "format": "pdf",
                        "filename": filename,
                        "mime_type": mime_type,
                        "content_base64": content_base64,
                        "output_language": resolved_language,
                        "document_kind": "project_proposal",
                    },
                )
        elif task_type == "export_exec_brief":
            content = build_exec_brief(
                output_language=resolved_language,
                report_payload=report_payload,
                items=items,
                knowledge_context=sanitized_knowledge_context,
            )
            complete_task(
                task,
                content=content,
                extra_payload={
                    "format": "markdown",
                    "filename": "exec-brief.md",
                    "output_language": resolved_language,
                    "briefing_context": sanitized_knowledge_context,
                },
            )
        elif task_type == "export_sales_brief":
            content = build_sales_brief(
                output_language=resolved_language,
                report_payload=report_payload,
                items=items,
                knowledge_context=sanitized_knowledge_context,
            )
            complete_task(
                task,
                content=content,
                extra_payload={
                    "format": "markdown",
                    "filename": "sales-brief.md",
                    "output_language": resolved_language,
                    "briefing_context": sanitized_knowledge_context,
                },
            )
        elif task_type == "export_outreach_draft":
            content = build_outreach_draft(
                output_language=resolved_language,
                report_payload=report_payload,
                knowledge_context=sanitized_knowledge_context,
            )
            complete_task(
                task,
                content=content,
                extra_payload={
                    "format": "markdown",
                    "filename": "outreach-draft.md",
                    "output_language": resolved_language,
                    "briefing_context": sanitized_knowledge_context,
                },
            )
        elif task_type == "export_watchlist_digest":
            changes = _latest_watchlist_changes(db)
            content = build_watchlist_digest(
                output_language=resolved_language,
                changes=changes,
                knowledge_context=sanitized_knowledge_context,
            )
            complete_task(
                task,
                content=content,
                extra_payload={
                    "format": "markdown",
                    "filename": "watchlist-digest.md",
                    "change_count": len(changes),
                    "output_language": resolved_language,
                    "watchlist_context": sanitized_knowledge_context,
                },
            )
        else:
            raise ValueError("Unsupported task_type")
    except Exception as exc:
        fail_task(task, str(exc))

    db.add(task)
    db.commit()
    db.refresh(task)
    return task
