from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import KnowledgeEntry
from app.schemas.research import (
    ResearchActionPlanRequest,
    ResearchActionPlanResponse,
    ResearchActionSaveRequest,
    ResearchActionSaveResponse,
    ResearchActionSaveItemOut,
    ResearchConversationCreateRequest,
    ResearchConversationMessageCreateRequest,
    ResearchConversationOut,
    ResearchEntityAliasResolveRequest,
    ResearchEntityDetailOut,
    ResearchConnectorStatusOut,
    ResearchJobCreateRequest,
    ResearchJobOut,
    ResearchJobTimelineEventOut,
    ResearchReportRequest,
    ResearchReportResponse,
    ResearchReportSaveRequest,
    ResearchReportSaveResponse,
    ResearchSavedViewCreateRequest,
    ResearchSavedViewOut,
    ResearchSourceSettingsOut,
    ResearchSourceSettingsUpdate,
    ResearchTrackingTopicCreateRequest,
    ResearchTrackingTopicRefreshRequest,
    ResearchTrackingTopicRefreshResponse,
    ResearchTrackingTopicOut,
    ResearchTrackingTopicVersionDetailOut,
    ResearchWatchlistChangeEventOut,
    ResearchWatchlistCreateRequest,
    ResearchWatchlistOut,
    ResearchWatchlistRefreshResponse,
    ResearchWorkspaceOut,
)
from app.services.research_conversation_service import (
    add_research_conversation_message,
    create_research_conversation,
    get_research_conversation,
    list_research_conversations,
)
from app.services.entity_catalog_service import (
    attach_entity_alias,
    get_entity_detail,
    sync_tracking_topic_entities,
)
from app.services.knowledge_service import create_or_get_standalone_knowledge_entry
from app.services.research_source_adapters import (
    build_research_connector_statuses,
    read_research_source_settings,
    write_research_source_settings,
)
from app.services.research_watchlist_service import (
    append_watchlist_change_events,
    get_watchlist_model,
    list_watchlist_change_events,
    list_watchlists,
    save_watchlist,
)
from app.services.research_workspace_store import (
    delete_saved_view,
    delete_tracking_topic,
    get_latest_tracking_topic_report_payload,
    get_tracking_topic,
    get_tracking_topic_version,
    list_saved_views,
    list_tracking_topic_versions,
    list_tracking_topics,
    mark_tracking_topic_refresh_failed,
    mark_tracking_topic_refresh_started,
    mark_tracking_topic_refreshed,
    save_saved_view,
    save_tracking_topic,
)
from app.services.research_service import (
    build_research_action_cards,
    build_research_report_markdown,
    generate_research_report,
)
from app.services.research_job_store import get_research_job, get_research_job_timeline, start_research_job
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api/research", tags=["research"])
settings = get_settings()


def _report_entity_names(*values: object) -> list[str]:
    names: list[str] = []
    for value in values:
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    candidate = str(item.get("name") or "").strip()
                else:
                    candidate = str(item or "").strip()
                if candidate and candidate not in names:
                    names.append(candidate)
    return names


def _report_budget_signals(value: object) -> list[str]:
    signals: list[str] = []
    if isinstance(value, list):
        for item in value:
            normalized = str(item or "").strip()
            if normalized and normalized not in signals:
                signals.append(normalized)
    return signals


def _build_watchlist_events(topic: dict[str, object], report: ResearchReportResponse) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    new_targets = [str(item) for item in (topic.get("last_refresh_new_targets") or []) if str(item).strip()]
    new_competitors = [str(item) for item in (topic.get("last_refresh_new_competitors") or []) if str(item).strip()]
    new_budget_signals = [str(item) for item in (topic.get("last_refresh_new_budget_signals") or []) if str(item).strip()]
    if new_targets:
        events.append(
            {
                "change_type": "added",
                "summary": f"新增甲方线索 {len(new_targets)} 条",
                "payload": {"targets": new_targets[:4]},
                "severity": "high" if len(new_targets) >= 2 else "medium",
            }
        )
    if new_competitors:
        events.append(
            {
                "change_type": "added",
                "summary": f"新增竞品动态 {len(new_competitors)} 条",
                "payload": {"competitors": new_competitors[:4]},
                "severity": "medium",
            }
        )
    if new_budget_signals:
        events.append(
            {
                "change_type": "risk",
                "summary": f"新增预算/招采线索 {len(new_budget_signals)} 条",
                "payload": {"budget_signals": new_budget_signals[:4]},
                "severity": "high",
            }
        )
    if report.source_quality == "low" or report.evidence_density == "low":
        events.append(
            {
                "change_type": "risk",
                "summary": "当前证据质量仍偏弱，建议继续补官方源与专项核验",
                "payload": {
                    "source_quality": report.source_quality,
                    "evidence_density": report.evidence_density,
                },
                "severity": "medium",
            }
        )
    if not events:
        events.append(
            {
                "change_type": "rewritten",
                "summary": str(topic.get("last_refresh_note") or "暂无新增核心情报，专题仍建议继续观察"),
                "payload": {"report_title": report.report_title},
                "severity": "low",
            }
        )
    return events
def _build_tracking_delta(
    previous_report: dict | None,
    current_report: ResearchReportResponse,
) -> tuple[list[str], list[str], list[str], str]:
    previous_targets = set(
        _report_entity_names(
            (previous_report or {}).get("top_target_accounts"),
            (previous_report or {}).get("target_accounts"),
        )
    )
    previous_competitors = set(
        _report_entity_names(
            (previous_report or {}).get("top_competitors"),
            (previous_report or {}).get("competitor_profiles"),
        )
    )
    previous_budgets = set(_report_budget_signals((previous_report or {}).get("budget_signals")))
    current_targets = _report_entity_names(current_report.top_target_accounts, current_report.target_accounts)
    current_competitors = _report_entity_names(current_report.top_competitors, current_report.competitor_profiles)
    current_budgets = _report_budget_signals(current_report.budget_signals)

    new_targets = [item for item in current_targets if item not in previous_targets][:3]
    new_competitors = [item for item in current_competitors if item not in previous_competitors][:3]
    new_budget_signals = [item for item in current_budgets if item not in previous_budgets][:3]

    summary_bits: list[str] = []
    if new_targets:
        summary_bits.append(f"新增甲方 {len(new_targets)}")
    if new_competitors:
        summary_bits.append(f"新增竞品 {len(new_competitors)}")
    if new_budget_signals:
        summary_bits.append(f"新增预算线索 {len(new_budget_signals)}")
    if not summary_bits:
        summary_bits.append("暂无新增核心情报，建议继续观察公开源变化")
    return new_targets, new_competitors, new_budget_signals, " / ".join(summary_bits)


def _find_existing_research_entry_by_keyword(db: Session, *, keyword: str) -> KnowledgeEntry | None:
    normalized_keyword = (keyword or "").strip()
    if not normalized_keyword:
        return None
    entries = db.scalars(
        select(KnowledgeEntry)
        .where(KnowledgeEntry.user_id == settings.single_user_id)
        .where(KnowledgeEntry.source_domain == "research.report")
        .order_by(KnowledgeEntry.updated_at.desc(), KnowledgeEntry.created_at.desc())
    ).all()
    for entry in entries:
        payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else {}
        report_payload = payload.get("report") if isinstance(payload.get("report"), dict) else {}
        if str(report_payload.get("keyword") or "").strip() == normalized_keyword:
            return entry
    return None


def _upsert_research_knowledge_entry(
    db: Session,
    *,
    keyword: str,
    title: str,
    content: str,
    collection_name: str | None,
    is_focus_reference: bool,
    metadata_payload: dict,
) -> KnowledgeEntry:
    existing_entry = _find_existing_research_entry_by_keyword(db, keyword=keyword)
    if existing_entry is not None:
        existing_entry.title = title
        existing_entry.content = content
        existing_entry.source_domain = "research.report"
        if collection_name:
            existing_entry.collection_name = collection_name
        if is_focus_reference:
            existing_entry.is_focus_reference = True
        existing_entry.metadata_payload = metadata_payload
        db.add(existing_entry)
        db.commit()
        db.refresh(existing_entry)
        return existing_entry

    entry, created = create_or_get_standalone_knowledge_entry(
        db,
        user_id=settings.single_user_id,
        title=title,
        content=content,
        source_domain="research.report",
        collection_name=collection_name,
        is_focus_reference=is_focus_reference,
        metadata_payload=metadata_payload,
    )
    if not created:
        if collection_name and not entry.collection_name:
            entry.collection_name = collection_name
        if is_focus_reference and not entry.is_focus_reference:
            entry.is_focus_reference = True
        entry.metadata_payload = metadata_payload
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _build_source_settings_out() -> ResearchSourceSettingsOut:
    source_settings = read_research_source_settings()
    return ResearchSourceSettingsOut(
        enable_jianyu_tender_feed=source_settings.enable_jianyu_tender_feed,
        enable_yuntoutiao_feed=source_settings.enable_yuntoutiao_feed,
        enable_ggzy_feed=source_settings.enable_ggzy_feed,
        enable_cecbid_feed=source_settings.enable_cecbid_feed,
        enable_ccgp_feed=source_settings.enable_ccgp_feed,
        enable_gov_policy_feed=source_settings.enable_gov_policy_feed,
        enable_local_ggzy_feed=source_settings.enable_local_ggzy_feed,
        enabled_source_labels=source_settings.enabled_labels(),
        connector_statuses=[
            ResearchConnectorStatusOut(**status)
            for status in build_research_connector_statuses(source_settings)
        ],
        updated_at=source_settings.updated_at,
    )


def _refresh_tracking_topic_core(
    db: Session,
    *,
    topic_id: str,
    topic: dict[str, object],
    payload: ResearchTrackingTopicRefreshRequest,
) -> ResearchTrackingTopicRefreshResponse:
    mark_tracking_topic_refresh_started(db, topic_id, note="正在刷新专题研报并补充新增情报")

    previous_report = get_latest_tracking_topic_report_payload(db, topic_id)
    request_payload = ResearchReportRequest(
        keyword=str(topic.get("keyword") or ""),
        research_focus=str(topic.get("research_focus") or ""),
        output_language=payload.output_language,
        include_wechat=payload.include_wechat,
        max_sources=payload.max_sources,
    )
    try:
        report = generate_research_report(request_payload)
        action_cards = build_research_action_cards(report)
        saved_entry_id: str | None = None
        saved_entry_title: str | None = None
        if payload.save_to_knowledge:
            ensure_demo_user(db)
            _, content = build_research_report_markdown(report, output_language=payload.output_language)
            entry = _upsert_research_knowledge_entry(
                db,
                keyword=report.keyword,
                title=report.report_title,
                content=content,
                collection_name=payload.collection_name or str(topic.get("name") or "长期跟踪专题"),
                is_focus_reference=payload.is_focus_reference,
                metadata_payload={
                    "kind": "research_report",
                    "tracking_topic_id": topic_id,
                    "report": report.model_dump(mode="json"),
                    "action_cards": [card.model_dump(mode="json") for card in action_cards],
                },
            )
            saved_entry_id = str(entry.id)
            saved_entry_title = entry.title

        new_targets, new_competitors, new_budget_signals, refresh_note = _build_tracking_delta(
            previous_report,
            report,
        )

        refreshed = mark_tracking_topic_refreshed(
            db,
            topic_id,
            last_refreshed_at=datetime.now(timezone.utc).isoformat(),
            last_report_entry_id=saved_entry_id,
            last_report_title=saved_entry_title or report.report_title,
            source_count=report.source_count,
            evidence_density=report.evidence_density,
            source_quality=report.source_quality,
            last_refresh_note=refresh_note,
            last_refresh_new_targets=new_targets,
            last_refresh_new_competitors=new_competitors,
            last_refresh_new_budget_signals=new_budget_signals,
            report_payload=report.model_dump(mode="json"),
            action_cards_payload=[card.model_dump(mode="json") for card in action_cards],
        )
        if refreshed is None:
            raise RuntimeError("tracking topic persistence failed")
        sync_tracking_topic_entities(
            db,
            topic_id=topic_id,
            report_payload=report.model_dump(mode="json"),
        )
        return ResearchTrackingTopicRefreshResponse(
            topic=ResearchTrackingTopicOut(**refreshed),
            report=report,
            saved_entry_id=saved_entry_id,
            saved_entry_title=saved_entry_title or report.report_title,
            report_version_id=str(refreshed.get("last_report_version_id") or ""),
            persistence_status="persisted",
            persistence_error=None,
        )
    except Exception as exc:
        mark_tracking_topic_refresh_failed(
            db,
            topic_id,
            error=str(exc),
            note="专题刷新失败，请检查当前关键词公开源与模型链路",
        )
        raise


@router.get("/source-settings", response_model=ResearchSourceSettingsOut)
def get_research_source_settings() -> ResearchSourceSettingsOut:
    return _build_source_settings_out()


@router.put("/source-settings", response_model=ResearchSourceSettingsOut)
def update_research_source_settings(payload: ResearchSourceSettingsUpdate) -> ResearchSourceSettingsOut:
    write_research_source_settings(
        enable_jianyu_tender_feed=payload.enable_jianyu_tender_feed,
        enable_yuntoutiao_feed=payload.enable_yuntoutiao_feed,
        enable_ggzy_feed=payload.enable_ggzy_feed,
        enable_cecbid_feed=payload.enable_cecbid_feed,
        enable_ccgp_feed=payload.enable_ccgp_feed,
        enable_gov_policy_feed=payload.enable_gov_policy_feed,
        enable_local_ggzy_feed=payload.enable_local_ggzy_feed,
    )
    return _build_source_settings_out()


@router.get("/workspace", response_model=ResearchWorkspaceOut)
def get_research_workspace(db: Session = Depends(get_db)) -> ResearchWorkspaceOut:
    ensure_demo_user(db)
    return ResearchWorkspaceOut(
        saved_views=[ResearchSavedViewOut(**item) for item in list_saved_views(db)],
        tracking_topics=[ResearchTrackingTopicOut(**item) for item in list_tracking_topics(db)],
    )


@router.post("/workspace/views", response_model=ResearchSavedViewOut)
def create_research_saved_view(
    payload: ResearchSavedViewCreateRequest,
    db: Session = Depends(get_db),
) -> ResearchSavedViewOut:
    ensure_demo_user(db)
    return ResearchSavedViewOut(**save_saved_view(db, payload.model_dump(mode="json")))


@router.delete("/workspace/views/{view_id}")
def remove_research_saved_view(view_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    ensure_demo_user(db)
    if not delete_saved_view(db, view_id):
        raise HTTPException(status_code=404, detail="Saved view not found")
    return {"ok": True}


@router.post("/workspace/topics", response_model=ResearchTrackingTopicOut)
def create_research_tracking_topic(
    payload: ResearchTrackingTopicCreateRequest,
    db: Session = Depends(get_db),
) -> ResearchTrackingTopicOut:
    ensure_demo_user(db)
    return ResearchTrackingTopicOut(**save_tracking_topic(db, payload.model_dump(mode="json")))


@router.delete("/workspace/topics/{topic_id}")
def remove_research_tracking_topic(topic_id: str, db: Session = Depends(get_db)) -> dict[str, bool]:
    ensure_demo_user(db)
    if not delete_tracking_topic(db, topic_id):
        raise HTTPException(status_code=404, detail="Tracking topic not found")
    return {"ok": True}


@router.get("/workspace/topics/{topic_id}/versions", response_model=list[ResearchTrackingTopicVersionDetailOut])
def get_research_tracking_topic_versions(
    topic_id: str,
    db: Session = Depends(get_db),
) -> list[ResearchTrackingTopicVersionDetailOut]:
    ensure_demo_user(db)
    topic = get_tracking_topic(db, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Tracking topic not found")
    return [ResearchTrackingTopicVersionDetailOut(**item) for item in list_tracking_topic_versions(db, topic_id)]


@router.get("/workspace/topics/{topic_id}/versions/{version_id}", response_model=ResearchTrackingTopicVersionDetailOut)
def get_research_tracking_topic_version(
    topic_id: str,
    version_id: str,
    db: Session = Depends(get_db),
) -> ResearchTrackingTopicVersionDetailOut:
    ensure_demo_user(db)
    version = get_tracking_topic_version(db, topic_id, version_id)
    if not version:
        raise HTTPException(status_code=404, detail="Tracking topic version not found")
    return ResearchTrackingTopicVersionDetailOut(**version)


@router.post("/workspace/topics/{topic_id}/refresh", response_model=ResearchTrackingTopicRefreshResponse)
def refresh_research_tracking_topic(
    topic_id: str,
    payload: ResearchTrackingTopicRefreshRequest,
    db: Session = Depends(get_db),
) -> ResearchTrackingTopicRefreshResponse:
    ensure_demo_user(db)
    topic = get_tracking_topic(db, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Tracking topic not found")
    return _refresh_tracking_topic_core(db, topic_id=topic_id, topic=topic, payload=payload)


@router.get("/watchlists", response_model=list[ResearchWatchlistOut])
def get_research_watchlists(db: Session = Depends(get_db)) -> list[ResearchWatchlistOut]:
    ensure_demo_user(db)
    return [ResearchWatchlistOut(**item) for item in list_watchlists(db)]


@router.post("/watchlists", response_model=ResearchWatchlistOut)
def create_research_watchlist(
    payload: ResearchWatchlistCreateRequest,
    db: Session = Depends(get_db),
) -> ResearchWatchlistOut:
    ensure_demo_user(db)
    tracking_topic_id = payload.tracking_topic_id
    if tracking_topic_id:
        topic = get_tracking_topic(db, tracking_topic_id)
        if not topic:
            raise HTTPException(status_code=404, detail="Tracking topic not found")
    else:
        topic = save_tracking_topic(
            db,
            {
                "name": payload.name,
                "keyword": payload.query,
                "research_focus": payload.research_focus,
                "perspective": payload.perspective,
                "region_filter": payload.region_filter,
                "industry_filter": payload.industry_filter,
                "notes": f"Watchlist · {payload.watch_type}",
            },
        )
        tracking_topic_id = topic["id"]
    saved = save_watchlist(
        db,
        {
            **payload.model_dump(mode="json"),
            "tracking_topic_id": tracking_topic_id,
        },
    )
    return ResearchWatchlistOut(**saved)


@router.get("/watchlists/{watchlist_id}/changes", response_model=list[ResearchWatchlistChangeEventOut])
def get_research_watchlist_changes(
    watchlist_id: str,
    db: Session = Depends(get_db),
) -> list[ResearchWatchlistChangeEventOut]:
    ensure_demo_user(db)
    watchlist = get_watchlist_model(db, watchlist_id)
    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    return [ResearchWatchlistChangeEventOut(**item) for item in list_watchlist_change_events(db, watchlist_id)]


@router.post("/watchlists/{watchlist_id}/refresh", response_model=ResearchWatchlistRefreshResponse)
def refresh_research_watchlist(
    watchlist_id: str,
    payload: ResearchTrackingTopicRefreshRequest,
    db: Session = Depends(get_db),
) -> ResearchWatchlistRefreshResponse:
    ensure_demo_user(db)
    watchlist = get_watchlist_model(db, watchlist_id)
    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    if watchlist.tracking_topic_id is None:
        raise HTTPException(status_code=400, detail="Watchlist is not linked to a tracking topic")
    topic = get_tracking_topic(db, str(watchlist.tracking_topic_id))
    if not topic:
        raise HTTPException(status_code=404, detail="Tracking topic not found")
    result = _refresh_tracking_topic_core(
        db,
        topic_id=str(watchlist.tracking_topic_id),
        topic=topic,
        payload=payload,
    )
    changes = append_watchlist_change_events(
        db,
        watchlist_id,
        _build_watchlist_events(result.topic.model_dump(mode="json"), result.report),
        checked_at=datetime.now(timezone.utc),
    )
    current_watchlist = get_watchlist_model(db, watchlist_id)
    if current_watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    latest_changes = [ResearchWatchlistChangeEventOut(**item) for item in changes]
    return ResearchWatchlistRefreshResponse(
        watchlist=ResearchWatchlistOut(
            **{
                **save_watchlist(
                    db,
                    {
                        "id": str(current_watchlist.id),
                        "tracking_topic_id": str(current_watchlist.tracking_topic_id),
                        "name": current_watchlist.name,
                        "watch_type": current_watchlist.watch_type,
                        "query": current_watchlist.query,
                        "region_filter": current_watchlist.region_filter,
                        "industry_filter": current_watchlist.industry_filter,
                        "alert_level": current_watchlist.alert_level,
                        "schedule": current_watchlist.schedule,
                        "status": current_watchlist.status,
                        "last_checked_at": datetime.now(timezone.utc).isoformat(),
                    },
                ),
                "latest_changes": [item.model_dump(mode="json") for item in latest_changes],
            }
        ),
        topic=result.topic,
        report=result.report,
        changes=latest_changes,
    )


@router.get("/entities/{entity_id}", response_model=ResearchEntityDetailOut)
def get_research_entity_detail(entity_id: str, db: Session = Depends(get_db)) -> ResearchEntityDetailOut:
    ensure_demo_user(db)
    detail = get_entity_detail(db, entity_id)
    if detail is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return ResearchEntityDetailOut(**detail)


@router.post("/entities/resolve-alias", response_model=ResearchEntityDetailOut)
def resolve_research_entity_alias(
    payload: ResearchEntityAliasResolveRequest,
    db: Session = Depends(get_db),
) -> ResearchEntityDetailOut:
    ensure_demo_user(db)
    detail = attach_entity_alias(
        db,
        entity_id=payload.entity_id,
        alias_name=payload.alias_name,
        confidence=payload.confidence,
    )
    if detail is None:
        raise HTTPException(status_code=404, detail="Entity not found")
    return ResearchEntityDetailOut(**detail)


@router.post("/report", response_model=ResearchReportResponse)
def create_research_report(payload: ResearchReportRequest) -> ResearchReportResponse:
    return generate_research_report(payload)


@router.post("/jobs", response_model=ResearchJobOut)
def create_research_job(payload: ResearchJobCreateRequest, db: Session = Depends(get_db)) -> ResearchJobOut:
    ensure_demo_user(db)
    return start_research_job(payload)


@router.get("/jobs/{job_id}", response_model=ResearchJobOut)
def get_research_job_status(job_id: str) -> ResearchJobOut:
    job = get_research_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Research job not found")
    return job


@router.get("/jobs/{job_id}/timeline", response_model=list[ResearchJobTimelineEventOut])
def get_research_job_timeline_items(job_id: str) -> list[ResearchJobTimelineEventOut]:
    timeline = get_research_job_timeline(job_id)
    if timeline is None:
        raise HTTPException(status_code=404, detail="Research job not found")
    return [ResearchJobTimelineEventOut(**item) for item in timeline]


@router.get("/conversations", response_model=list[ResearchConversationOut])
def list_research_conversation_items(db: Session = Depends(get_db)) -> list[ResearchConversationOut]:
    ensure_demo_user(db)
    return [ResearchConversationOut(**item) for item in list_research_conversations(db, user_id=settings.single_user_id)]


@router.post("/conversations", response_model=ResearchConversationOut, status_code=201)
def create_research_conversation_item(
    payload: ResearchConversationCreateRequest,
    db: Session = Depends(get_db),
) -> ResearchConversationOut:
    ensure_demo_user(db)
    try:
        parsed_topic_id = UUID(payload.topic_id) if payload.topic_id else None
        parsed_job_id = UUID(payload.job_id) if payload.job_id else None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid topic_id or job_id") from exc
    try:
        result = create_research_conversation(
            db,
            user_id=settings.single_user_id,
            title=payload.title,
            topic_id=parsed_topic_id,
            job_id=parsed_job_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ResearchConversationOut(**result)


@router.get("/conversations/{conversation_id}", response_model=ResearchConversationOut)
def get_research_conversation_item(conversation_id: str, db: Session = Depends(get_db)) -> ResearchConversationOut:
    ensure_demo_user(db)
    try:
        parsed_id = UUID(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid conversation id") from exc
    result = get_research_conversation(db, user_id=settings.single_user_id, conversation_id=parsed_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ResearchConversationOut(**result)


@router.post("/conversations/{conversation_id}/messages", response_model=ResearchConversationOut)
def add_research_conversation_message_item(
    conversation_id: str,
    payload: ResearchConversationMessageCreateRequest,
    db: Session = Depends(get_db),
) -> ResearchConversationOut:
    ensure_demo_user(db)
    try:
        parsed_id = UUID(conversation_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid conversation id") from exc
    try:
        result = add_research_conversation_message(
            db,
            user_id=settings.single_user_id,
            conversation_id=parsed_id,
            content=payload.content,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return ResearchConversationOut(**result)


@router.post("/report/save", response_model=ResearchReportSaveResponse)
def save_research_report(
    payload: ResearchReportSaveRequest,
    db: Session = Depends(get_db),
) -> ResearchReportSaveResponse:
    ensure_demo_user(db)
    _, content = build_research_report_markdown(payload.report, output_language=payload.report.output_language)
    action_cards = build_research_action_cards(payload.report)
    entry = _upsert_research_knowledge_entry(
        db,
        keyword=payload.report.keyword,
        title=payload.report.report_title,
        content=content,
        collection_name=payload.collection_name,
        is_focus_reference=payload.is_focus_reference,
        metadata_payload={
            "kind": "research_report",
            "report": payload.report.model_dump(mode="json"),
            "action_cards": [card.model_dump(mode="json") for card in action_cards],
        },
    )
    return ResearchReportSaveResponse(
        entry_id=str(entry.id),
        title=entry.title,
        created_at=entry.created_at,
    )


@router.post("/action-plan", response_model=ResearchActionPlanResponse)
def create_research_action_plan(payload: ResearchActionPlanRequest) -> ResearchActionPlanResponse:
    return ResearchActionPlanResponse(
        keyword=payload.report.keyword,
        generated_at=datetime.now(timezone.utc),
        cards=build_research_action_cards(payload.report),
    )


@router.post("/action-plan/save", response_model=ResearchActionSaveResponse)
def save_research_action_plan(
    payload: ResearchActionSaveRequest,
    db: Session = Depends(get_db),
) -> ResearchActionSaveResponse:
    ensure_demo_user(db)
    collection_name = payload.collection_name or "研报行动卡"
    saved_items: list[ResearchActionSaveItemOut] = []
    created_count = 0

    for card in payload.cards:
        lines = [
            f"行动摘要：{card.summary}",
            "",
            f"优先级：{card.priority}",
        ]
        if card.target_persona:
            lines.append(f"目标对象：{card.target_persona}")
        if card.execution_window:
            lines.append(f"执行窗口：{card.execution_window}")
        if card.deliverable:
            lines.append(f"交付物：{card.deliverable}")
        lines.extend([
            "",
            "建议步骤：",
        ])
        lines.extend([f"- {step}" for step in card.recommended_steps] or ["- 暂无补充步骤"])
        if card.evidence:
            lines.extend(["", "参考依据："])
            lines.extend([f"- {item}" for item in card.evidence])

        entry, created = create_or_get_standalone_knowledge_entry(
            db,
            user_id=settings.single_user_id,
            title=card.title,
            content="\n".join(lines).strip(),
            source_domain="research.action_card",
            collection_name=collection_name,
            is_focus_reference=payload.is_focus_reference,
            metadata_payload={
                "kind": "research_action_card",
                "keyword": payload.keyword,
                "card": card.model_dump(mode="json"),
            },
        )
        if payload.is_focus_reference and not entry.is_focus_reference:
            entry.is_focus_reference = True
        db.add(entry)
        db.flush()
        if created:
            created_count += 1
        saved_items.append(
            ResearchActionSaveItemOut(
                entry_id=str(entry.id),
                title=entry.title,
                created_at=entry.created_at,
            )
        )

    db.commit()
    return ResearchActionSaveResponse(
        created_count=created_count,
        items=saved_items,
    )
