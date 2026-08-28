from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, HTTPException

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.schemas.mobile import MobileDailyBriefResponse
from app.schemas.research import (
    ResearchCompareSnapshotCreateRequest,
    ResearchCompareSnapshotDetailOut,
    ResearchCompareSnapshotOut,
    ResearchMarkdownArchiveCreateRequest,
    ResearchMarkdownArchiveDetailOut,
    ResearchMarkdownArchiveOut,
    ResearchLowQualityReviewActionResponse,
    ResearchOfflineEvaluationOut,
    ResearchLowQualityReviewQueueOut,
    ResearchLowQualityReviewResolveRequest,
    ResearchActionPlanRequest,
    ResearchActionPlanResponse,
    ResearchActionSaveRequest,
    ResearchActionSaveResponse,
    ResearchActionSaveItemOut,
    ResearchAssuranceSnapshotOut,
    ResearchClarificationPacketOut,
    ResearchClarificationSubmitRequest,
    ResearchClarificationSubmitResponse,
    ResearchConversationCreateRequest,
    ResearchConversationMessageCreateRequest,
    ResearchConversationOut,
    ResearchEntityAliasResolveRequest,
    ResearchEntityDetailOut,
    ResearchExperienceFeedbackOut,
    ResearchExperienceFeedbackRequest,
    ResearchExperienceMetricsOut,
    ResearchExperienceReadinessOut,
    ResearchConnectorStatusOut,
    ResearchDeliveryExportDiagnosticsOut,
    ResearchExperimentActivePolicyOut,
    ResearchExperimentControlPlaneOut,
    ResearchExperimentEffectiveRuntimeConfigOut,
    ResearchExperimentOrchestrationOut,
    ResearchExperimentPlanCreateRequest,
    ResearchExperimentPlanOut,
    ResearchExperimentRolloutActionRequest,
    ResearchExperimentRuntimeConsumer,
    ResearchExperimentRuntimeSnapshotOut,
    ResearchFollowupDeltaEvaluationOut,
    ResearchGoldenEvaluationOut,
    ResearchIndustryKnowledgeBenchmarkOut,
    ResearchIndustryKnowledgeRetrievalApprovalTemplateOut,
    ResearchIndustryKnowledgeRetrievalAssuranceSnapshotOut,
    ResearchIndustryKnowledgeRetrievalEvidenceOperationsSnapshotOut,
    ResearchIndustryKnowledgeRetrievalEvidenceOperationsTemplatesOut,
    ResearchIndustryKnowledgeRetrievalEvidenceTemplatesOut,
    ResearchIndustryKnowledgeDeliveryReviewArtifactOut,
    ResearchIndustryKnowledgeDeliveryReviewOut,
    ResearchIndustryKnowledgeDeliveryReviewRequest,
    ResearchIndustryKnowledgeSearchOut,
    ResearchIndustrySkillLibraryOut,
    ResearchJobCreateRequest,
    ResearchJobOut,
    ResearchJobTimelineEventOut,
    ResearchReportRequest,
    ResearchReportResponse,
    ResearchReportSaveRequest,
    ResearchReportSaveResponse,
    ResearchRetrievalIndexRebuildOut,
    ResearchRetrievalIndexRebuildRequest,
    ResearchRetrievalIndexSearchHitOut,
    ResearchRetrievalIndexSearchOut,
    ResearchRetrievalIndexStatusOut,
    ResearchSectionRetrievalPackOut,
    ResearchSectionRetrievalPackRequest,
    ResearchSolutionDeliveryPackOut,
    ResearchSolutionDeliveryRequest,
    ResearchSavedViewCreateRequest,
    ResearchSavedViewOut,
    ResearchSourceSettingsOut,
    ResearchSourceSettingsUpdate,
    ResearchUpgradeDiagnosticsOut,
    ResearchUpgradeDiagnosticsRequest,
    ResearchTrackingTopicCreateRequest,
    ResearchTrackingTopicRefreshRequest,
    ResearchTrackingTopicRefreshResponse,
    ResearchTrackingTopicOut,
    ResearchTrackingTopicTimelineEventOut,
    ResearchTrackingTopicVersionDetailOut,
    ResearchWatchlistChangeEventOut,
    ResearchWatchlistAutomationStatusOut,
    ResearchWatchlistCreateRequest,
    ResearchWatchlistDigestExportOut,
    ResearchWatchlistOpsSummaryOut,
    ResearchWatchlistRunOut,
    ResearchWatchlistRunDueItemOut,
    ResearchWatchlistRunDueResponse,
    ResearchWatchlistOut,
    ResearchWatchlistRefreshResponse,
    ResearchWatchlistUpdateRequest,
    ResearchWorkspaceOut,
)
from app.services.delivery.market_intelligence import build_market_intelligence_pack
from app.services.research_solution_intelligence_service import build_solution_delivery_pack
from app.services.industry_knowledge_rag import hybrid_search_industry_knowledge
from app.services.industry_knowledge_retrieval_benchmark import (
    BENCHMARK_ID,
    STRATEGY_KEYS,
    industry_knowledge_benchmark_artifact_reference,
    load_industry_knowledge_retrieval_benchmark_dataset,
    load_latest_industry_knowledge_retrieval_benchmark,
    register_industry_knowledge_delivery_review_artifacts,
    run_industry_knowledge_retrieval_benchmark,
)
from app.services.industry_knowledge_retrieval_assurance import (
    build_industry_knowledge_retrieval_assurance_snapshot,
    export_industry_knowledge_retrieval_approval_template,
    export_industry_knowledge_retrieval_evidence_templates,
)
from app.services.industry_knowledge_retrieval_evidence_operations import (
    build_industry_knowledge_retrieval_evidence_operations_snapshot,
    export_industry_knowledge_retrieval_evidence_operations_templates,
)
from app.services.industry_skill_library import build_industry_skill_library_snapshot, resolve_library_dir
from app.services.industry_knowledge_rag import INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGIES
from app.services.research_delivery_export_diagnostics_service import build_delivery_export_diagnostics
from app.services.research_experiment_orchestration_service import (
    build_research_experiment_orchestration,
    build_research_experiment_runtime_snapshot,
    create_research_experiment_plan,
    evaluate_research_experiment_rollout_gate,
    freeze_research_experiment_cohort,
    list_research_experiment_active_policies,
    lock_research_experiment_baseline,
    promote_research_experiment_rollout,
    resolve_research_experiment_runtime_config,
    revoke_research_experiment_rollout,
)
from app.services.research_evaluation_service import (
    build_followup_delta_evaluation,
    build_golden_research_evaluation,
    build_offline_research_evaluation,
    build_research_experiment_control_plane,
)
from app.services.research_retrieval_index_service import (
    build_research_retrieval_index,
    get_persistent_research_retrieval_index_status,
    rebuild_persistent_research_retrieval_index,
    search_persistent_research_retrieval_index,
)
from app.services.research_section_retrieval_service import build_section_retrieval_packs
from app.services.research_upgrade_diagnostics_service import build_research_upgrade_diagnostics
from app.services.research_assurance_service import build_research_assurance_snapshot
from app.services.research.report_persistence import upsert_research_knowledge_entry
from app.services.research.clarification import require_formal_research_delivery
from app.services.daily_brief_service import build_daily_brief_snapshot, serialize_daily_brief
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
from app.services.knowledge_intelligence_service import (
    build_report_knowledge_intelligence,
    build_research_report_metadata,
)
from app.services.knowledge_service import create_or_get_standalone_knowledge_entry
from app.services.research_source_adapters import (
    build_research_connector_statuses,
    read_research_source_settings,
    write_research_source_settings,
)
from app.services.research_watchlist_service import (
    append_watchlist_change_events,
    build_watchlist_digest_export,
    build_watchlist_ops_summary,
    get_watchlist_payload,
    get_watchlist_model,
    list_due_watchlists,
    list_watchlist_change_events,
    list_watchlist_runs,
    list_watchlists,
    record_watchlist_run,
    save_watchlist,
)
from app.services.watchlist_automation_service import get_watchlist_automation_status
from app.services.research_workspace_store import (
    delete_compare_snapshot,
    delete_markdown_archive,
    delete_saved_view,
    delete_tracking_topic,
    get_compare_snapshot,
    get_markdown_archive,
    get_latest_tracking_topic_report_payload,
    get_tracking_topic,
    get_tracking_topic_version,
    list_compare_snapshots,
    list_markdown_archives,
    list_tracking_topic_timeline,
    list_saved_views,
    list_tracking_topic_versions,
    list_tracking_topics,
    mark_tracking_topic_refresh_failed,
    mark_tracking_topic_refresh_started,
    mark_tracking_topic_refreshed,
    save_markdown_archive,
    save_saved_view,
    save_tracking_topic,
    save_compare_snapshot,
)
from app.schemas.research_runtime import ResearchRunMetricsOut
from app.services.research_service import (
    build_research_action_cards,
    build_research_report_markdown,
    generate_research_report,
)
from app.services.research_review_service import (
    list_low_quality_research_review_queue,
    resolve_low_quality_research_entry,
    rewrite_low_quality_research_entry,
)
from app.services.research_job_store import (
    get_research_job,
    get_research_job_metrics,
    get_research_job_timeline,
    record_research_experience_feedback,
    start_research_job,
    submit_research_clarification,
)
from app.services.research_experience_service import (
    build_research_experience_metrics,
    build_research_experience_readiness,
)
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api/research", tags=["research"])
settings = get_settings()


def _require_formal_report(report: ResearchReportResponse) -> ResearchReportResponse:
    try:
        return require_formal_research_delivery(report)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
    intelligence = build_report_knowledge_intelligence(report)
    intelligence_accounts = [str(item.get("name") or "") for item in intelligence.get("accounts", []) if str(item.get("name") or "").strip()]
    intelligence_opportunities = [
        str(item.get("title") or "")
        for item in intelligence.get("opportunities", [])
        if str(item.get("title") or "").strip()
    ]
    why_now = [str(item) for item in intelligence.get("why_now", []) if str(item).strip()]
    top_budget_probability = 0
    for item in intelligence.get("opportunities", []):
        try:
            top_budget_probability = max(top_budget_probability, int(item.get("budget_probability") or 0))
        except (TypeError, ValueError, AttributeError):
            continue
    new_targets = [str(item) for item in (topic.get("last_refresh_new_targets") or []) if str(item).strip()]
    new_competitors = [str(item) for item in (topic.get("last_refresh_new_competitors") or []) if str(item).strip()]
    new_budget_signals = [str(item) for item in (topic.get("last_refresh_new_budget_signals") or []) if str(item).strip()]
    if new_targets:
        events.append(
            {
                "change_type": "added",
                "summary": f"新增甲方线索 {len(new_targets)} 条",
                "payload": {
                    "targets": new_targets[:4],
                    "accounts": intelligence_accounts[:3],
                    "why_now": why_now[:2],
                    "top_budget_probability": top_budget_probability,
                },
                "severity": "high" if len(new_targets) >= 2 else "medium",
            }
        )
    if new_competitors:
        events.append(
            {
                "change_type": "added",
                "summary": f"新增竞品动态 {len(new_competitors)} 条",
                "payload": {
                    "competitors": new_competitors[:4],
                    "opportunities": intelligence_opportunities[:2],
                },
                "severity": "medium",
            }
        )
    if new_budget_signals:
        events.append(
            {
                "change_type": "risk",
                "summary": f"新增预算/招采线索 {len(new_budget_signals)} 条",
                "payload": {
                    "budget_signals": new_budget_signals[:4],
                    "accounts": intelligence_accounts[:3],
                    "why_now": why_now[:2],
                    "top_budget_probability": top_budget_probability,
                },
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
                    "why_now": why_now[:2],
                },
                "severity": "medium",
            }
        )
    if not events:
        events.append(
            {
                "change_type": "rewritten",
                "summary": str(topic.get("last_refresh_note") or "暂无新增核心情报，专题仍建议继续观察"),
                "payload": {
                    "report_title": report.report_title,
                    "accounts": intelligence_accounts[:3],
                    "opportunities": intelligence_opportunities[:2],
                    "why_now": why_now[:2],
                    "top_budget_probability": top_budget_probability,
                },
                "severity": "low",
            }
        )
    return events


def _build_watchlist_save_payload(
    watchlist,
    *,
    overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": str(watchlist.id),
        "tracking_topic_id": str(watchlist.tracking_topic_id) if watchlist.tracking_topic_id else None,
        "name": watchlist.name,
        "watch_type": watchlist.watch_type,
        "query": watchlist.query,
        "region_filter": watchlist.region_filter,
        "industry_filter": watchlist.industry_filter,
        "alert_level": watchlist.alert_level,
        "schedule": watchlist.schedule,
        "status": watchlist.status,
        "last_checked_at": watchlist.last_checked_at.isoformat() if watchlist.last_checked_at else None,
    }
    if overrides:
        payload.update(overrides)
    return payload


def _refresh_watchlist_core(
    db: Session,
    *,
    watchlist_id: str,
    payload: ResearchTrackingTopicRefreshRequest,
) -> ResearchWatchlistRefreshResponse:
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
    save_watchlist(
        db,
        _build_watchlist_save_payload(
            current_watchlist,
            overrides={"last_checked_at": datetime.now(timezone.utc).isoformat()},
        ),
    )
    payload_out = get_watchlist_payload(db, watchlist_id)
    if payload_out is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    latest_changes = [ResearchWatchlistChangeEventOut(**item) for item in changes]
    return ResearchWatchlistRefreshResponse(
        watchlist=ResearchWatchlistOut(**payload_out),
        topic=result.topic,
        report=result.report,
        changes=latest_changes,
    )
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
        enable_curated_wechat_channels=source_settings.enable_curated_wechat_channels,
        enabled_source_labels=source_settings.enabled_labels(),
        connector_statuses=[
            ResearchConnectorStatusOut(**status)
            for status in build_research_connector_statuses(source_settings)
        ],
        updated_at=source_settings.updated_at,
    )


def _with_runtime_generation_strategy(
    db: Session,
    payload: ResearchReportRequest,
) -> ResearchReportRequest:
    runtime_strategy_config = dict(payload.runtime_strategy_config or {})
    query_config = resolve_research_experiment_runtime_config(db, consumer="query_generation")
    reranker_config = resolve_research_experiment_runtime_config(db, consumer="source_reranker")
    runtime_strategy_config.update(
        {
            "query_generation": query_config.model_dump(mode="json"),
            "source_reranker": reranker_config.model_dump(mode="json"),
        }
    )
    return payload.model_copy(update={"runtime_strategy_config": runtime_strategy_config})


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
        report = generate_research_report(_with_runtime_generation_strategy(db, request_payload))
        action_cards = build_research_action_cards(report)
        saved_entry_id: str | None = None
        saved_entry_title: str | None = None
        if payload.save_to_knowledge:
            report = _require_formal_report(report)
            ensure_demo_user(db)
            _, content = build_research_report_markdown(report, output_language=payload.output_language)
            entry = upsert_research_knowledge_entry(
                db,
                keyword=report.keyword,
                title=report.report_title,
                content=content,
                collection_name=payload.collection_name or str(topic.get("name") or "长期跟踪专题"),
                is_focus_reference=payload.is_focus_reference,
                metadata_payload=build_research_report_metadata(
                    report,
                    action_cards=action_cards,
                    tracking_topic_id=topic_id,
                ),
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
        enable_curated_wechat_channels=payload.enable_curated_wechat_channels,
    )
    return _build_source_settings_out()


@router.get("/workspace", response_model=ResearchWorkspaceOut)
def get_research_workspace(db: Session = Depends(get_db)) -> ResearchWorkspaceOut:
    ensure_demo_user(db)
    return ResearchWorkspaceOut(
        saved_views=[ResearchSavedViewOut(**item) for item in list_saved_views(db)],
        tracking_topics=[ResearchTrackingTopicOut(**item) for item in list_tracking_topics(db)],
        compare_snapshots=[ResearchCompareSnapshotOut(**item) for item in list_compare_snapshots(db)],
        markdown_archives=[ResearchMarkdownArchiveOut(**item) for item in list_markdown_archives(db)],
    )


@router.get("/daily-brief", response_model=MobileDailyBriefResponse)
def get_research_daily_brief(
    force_refresh: bool = False,
    db: Session = Depends(get_db),
) -> MobileDailyBriefResponse:
    ensure_demo_user(db)
    snapshot = build_daily_brief_snapshot(db, user_id=settings.single_user_id, force_refresh=force_refresh)
    return MobileDailyBriefResponse(**serialize_daily_brief(snapshot))


@router.get("/evaluation/offline", response_model=ResearchOfflineEvaluationOut)
def get_research_offline_evaluation(
    weakest_limit: int = 6,
    db: Session = Depends(get_db),
) -> ResearchOfflineEvaluationOut:
    ensure_demo_user(db)
    return build_offline_research_evaluation(
        db,
        weakest_limit=max(1, min(weakest_limit, 12)),
    )


@router.get("/evaluation/golden", response_model=ResearchGoldenEvaluationOut)
def get_research_golden_evaluation() -> ResearchGoldenEvaluationOut:
    return build_golden_research_evaluation()


@router.get("/evaluation/control-plane", response_model=ResearchExperimentControlPlaneOut)
def get_research_experiment_control_plane(
    db: Session = Depends(get_db),
) -> ResearchExperimentControlPlaneOut:
    ensure_demo_user(db)
    return build_research_experiment_control_plane(db)


@router.get("/experiments/orchestration", response_model=ResearchExperimentOrchestrationOut)
def get_research_experiment_orchestration(
    db: Session = Depends(get_db),
) -> ResearchExperimentOrchestrationOut:
    ensure_demo_user(db)
    return build_research_experiment_orchestration(db)


@router.get("/experiments/active-policies", response_model=list[ResearchExperimentActivePolicyOut])
def get_research_experiment_active_policies(
    db: Session = Depends(get_db),
) -> list[ResearchExperimentActivePolicyOut]:
    ensure_demo_user(db)
    return list_research_experiment_active_policies(db)


@router.get("/experiments/runtime-snapshot", response_model=ResearchExperimentRuntimeSnapshotOut)
def get_research_experiment_runtime_snapshot(
    db: Session = Depends(get_db),
) -> ResearchExperimentRuntimeSnapshotOut:
    ensure_demo_user(db)
    return build_research_experiment_runtime_snapshot(db)


@router.get("/experiments/runtime-config", response_model=ResearchExperimentEffectiveRuntimeConfigOut)
def get_research_experiment_runtime_config(
    consumer: ResearchExperimentRuntimeConsumer = "all",
    db: Session = Depends(get_db),
) -> ResearchExperimentEffectiveRuntimeConfigOut:
    ensure_demo_user(db)
    return resolve_research_experiment_runtime_config(db, consumer=consumer)


@router.post("/experiments/plans", response_model=ResearchExperimentPlanOut)
def create_research_experiment_plan_endpoint(
    payload: ResearchExperimentPlanCreateRequest,
    db: Session = Depends(get_db),
) -> ResearchExperimentPlanOut:
    ensure_demo_user(db)
    return ResearchExperimentPlanOut(**create_research_experiment_plan(db, payload))


@router.post("/experiments/plans/{plan_id}/freeze-cohort", response_model=ResearchExperimentPlanOut)
def freeze_research_experiment_plan_cohort(
    plan_id: str,
    db: Session = Depends(get_db),
) -> ResearchExperimentPlanOut:
    ensure_demo_user(db)
    try:
        payload = freeze_research_experiment_cohort(db, plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ResearchExperimentPlanOut(**payload)


@router.post("/experiments/plans/{plan_id}/lock-baseline", response_model=ResearchExperimentPlanOut)
def lock_research_experiment_plan_baseline(
    plan_id: str,
    db: Session = Depends(get_db),
) -> ResearchExperimentPlanOut:
    ensure_demo_user(db)
    try:
        payload = lock_research_experiment_baseline(db, plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ResearchExperimentPlanOut(**payload)


@router.post("/experiments/plans/{plan_id}/evaluate-gate", response_model=ResearchExperimentPlanOut)
def evaluate_research_experiment_plan_gate(
    plan_id: str,
    db: Session = Depends(get_db),
) -> ResearchExperimentPlanOut:
    ensure_demo_user(db)
    try:
        payload = evaluate_research_experiment_rollout_gate(db, plan_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ResearchExperimentPlanOut(**payload)


@router.post("/experiments/plans/{plan_id}/promote-rollout", response_model=ResearchExperimentPlanOut)
def promote_research_experiment_plan_rollout(
    plan_id: str,
    payload: ResearchExperimentRolloutActionRequest,
    db: Session = Depends(get_db),
) -> ResearchExperimentPlanOut:
    ensure_demo_user(db)
    try:
        result = promote_research_experiment_rollout(db, plan_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ResearchExperimentPlanOut(**result)


@router.post("/experiments/plans/{plan_id}/revoke-rollout", response_model=ResearchExperimentPlanOut)
def revoke_research_experiment_plan_rollout(
    plan_id: str,
    payload: ResearchExperimentRolloutActionRequest,
    db: Session = Depends(get_db),
) -> ResearchExperimentPlanOut:
    ensure_demo_user(db)
    try:
        result = revoke_research_experiment_rollout(db, plan_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return ResearchExperimentPlanOut(**result)


@router.get("/evaluation/followup-delta", response_model=ResearchFollowupDeltaEvaluationOut)
def get_research_followup_delta_evaluation(
    weakest_limit: int = 6,
    db: Session = Depends(get_db),
) -> ResearchFollowupDeltaEvaluationOut:
    ensure_demo_user(db)
    return build_followup_delta_evaluation(
        db,
        weakest_limit=max(1, min(weakest_limit, 12)),
    )


@router.get("/delivery/export-diagnostics", response_model=ResearchDeliveryExportDiagnosticsOut)
def get_research_delivery_export_diagnostics(
    trend_limit: int = 8,
    db: Session = Depends(get_db),
) -> ResearchDeliveryExportDiagnosticsOut:
    ensure_demo_user(db)
    return build_delivery_export_diagnostics(
        db,
        trend_limit=max(1, min(trend_limit, 16)),
    )


@router.get("/upgrade-diagnostics/preview", response_model=ResearchUpgradeDiagnosticsOut)
def get_research_upgrade_diagnostics_preview() -> ResearchUpgradeDiagnosticsOut:
    return ResearchUpgradeDiagnosticsOut(**build_research_upgrade_diagnostics())


@router.post("/upgrade-diagnostics/preview", response_model=ResearchUpgradeDiagnosticsOut)
def preview_research_upgrade_diagnostics(
    payload: ResearchUpgradeDiagnosticsRequest,
) -> ResearchUpgradeDiagnosticsOut:
    return ResearchUpgradeDiagnosticsOut(**build_research_upgrade_diagnostics(payload))


@router.get("/assurance/preview", response_model=ResearchAssuranceSnapshotOut)
def get_research_assurance_preview(
    db: Session = Depends(get_db),
) -> ResearchAssuranceSnapshotOut:
    """Read the quality-program state without modifying tasks or artifacts."""

    ensure_demo_user(db)
    return ResearchAssuranceSnapshotOut(**build_research_assurance_snapshot(db))


@router.post("/retrieval/section-packs", response_model=list[ResearchSectionRetrievalPackOut])
def build_research_section_retrieval_packs(
    payload: ResearchSectionRetrievalPackRequest,
    db: Session = Depends(get_db),
) -> list[ResearchSectionRetrievalPackOut]:
    ensure_demo_user(db)
    runtime_config = resolve_research_experiment_runtime_config(db, consumer="retrieval_search").effective_config
    index = build_research_retrieval_index(
        db,
        user_id=settings.single_user_id,
        limit_per_source=payload.limit_per_source,
    )
    return build_section_retrieval_packs(
        payload.report,
        index,
        limit_per_section=payload.limit_per_section,
        parent_block_boost=float(runtime_config.get("parent_block_boost") or 1.0),
        official_source_bias=bool(runtime_config.get("official_source_bias", True)),
    )


@router.get("/industry-skills", response_model=ResearchIndustrySkillLibraryOut)
def get_research_industry_skills(
    query: str = "",
    limit: int = 8,
) -> ResearchIndustrySkillLibraryOut:
    return build_industry_skill_library_snapshot(query=query, limit=limit)


@router.get("/industry-skills/retrieve", response_model=ResearchIndustryKnowledgeSearchOut)
def retrieve_research_industry_knowledge(
    query: str,
    industries: str = "",
    document_types: str = "",
    limit: int = 6,
    strategy: Literal["baseline_hybrid", "prefilter_weighted_hybrid", "prefilter_weighted_rerank"] = "baseline_hybrid",
) -> ResearchIndustryKnowledgeSearchOut:
    result = hybrid_search_industry_knowledge(
        resolve_library_dir(),
        query=query,
        industries=[item.strip() for item in industries.split(",") if item.strip()],
        document_types=[item.strip() for item in document_types.split(",") if item.strip()],
        limit=limit,
        strategy=strategy,
    )
    return ResearchIndustryKnowledgeSearchOut(**result)


@router.get("/industry-skills/retrieval-ranking-benchmark", response_model=ResearchIndustryKnowledgeBenchmarkOut)
def get_research_industry_knowledge_retrieval_ranking_benchmark() -> ResearchIndustryKnowledgeBenchmarkOut:
    return ResearchIndustryKnowledgeBenchmarkOut(**load_latest_industry_knowledge_retrieval_benchmark())


@router.post("/industry-skills/retrieval-ranking-benchmark/run", response_model=ResearchIndustryKnowledgeBenchmarkOut)
def run_research_industry_knowledge_retrieval_ranking_benchmark() -> ResearchIndustryKnowledgeBenchmarkOut:
    return ResearchIndustryKnowledgeBenchmarkOut(**run_industry_knowledge_retrieval_benchmark())


@router.get(
    "/industry-skills/retrieval-ranking-assurance",
    response_model=ResearchIndustryKnowledgeRetrievalAssuranceSnapshotOut,
)
def get_research_industry_knowledge_retrieval_assurance() -> ResearchIndustryKnowledgeRetrievalAssuranceSnapshotOut:
    """Return the fail-closed 15-round retrieval assurance view."""

    return ResearchIndustryKnowledgeRetrievalAssuranceSnapshotOut(
        **build_industry_knowledge_retrieval_assurance_snapshot()
    )


@router.post(
    "/industry-skills/retrieval-ranking-assurance/approval-template",
    response_model=ResearchIndustryKnowledgeRetrievalApprovalTemplateOut,
)
def export_research_industry_knowledge_retrieval_approval_template() -> ResearchIndustryKnowledgeRetrievalApprovalTemplateOut:
    """Create a pending human approval template without promoting a strategy."""

    try:
        return ResearchIndustryKnowledgeRetrievalApprovalTemplateOut(
            **export_industry_knowledge_retrieval_approval_template()
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post(
    "/industry-skills/retrieval-ranking-assurance/evidence-templates",
    response_model=ResearchIndustryKnowledgeRetrievalEvidenceTemplatesOut,
)
def export_research_industry_knowledge_retrieval_evidence_templates() -> ResearchIndustryKnowledgeRetrievalEvidenceTemplatesOut:
    """Create pending approval/shadow/drift templates without creating evidence."""

    try:
        return ResearchIndustryKnowledgeRetrievalEvidenceTemplatesOut(
            **export_industry_knowledge_retrieval_evidence_templates()
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.get(
    "/industry-skills/retrieval-evidence-operations",
    response_model=ResearchIndustryKnowledgeRetrievalEvidenceOperationsSnapshotOut,
)
def get_research_industry_knowledge_retrieval_evidence_operations() -> ResearchIndustryKnowledgeRetrievalEvidenceOperationsSnapshotOut:
    """Return the read-only 2.8.1-2.9.5 evidence-operations control plane."""

    return ResearchIndustryKnowledgeRetrievalEvidenceOperationsSnapshotOut(
        **build_industry_knowledge_retrieval_evidence_operations_snapshot()
    )


@router.post(
    "/industry-skills/retrieval-evidence-operations/templates",
    response_model=ResearchIndustryKnowledgeRetrievalEvidenceOperationsTemplatesOut,
)
def export_research_industry_knowledge_retrieval_evidence_operations_templates() -> ResearchIndustryKnowledgeRetrievalEvidenceOperationsTemplatesOut:
    """Create missing pending operations templates without completing external evidence."""

    try:
        return ResearchIndustryKnowledgeRetrievalEvidenceOperationsTemplatesOut(
            **export_industry_knowledge_retrieval_evidence_operations_templates()
        )
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


def _delivery_review_report_digest(report: ResearchReportResponse) -> str:
    payload = {
        "keyword": report.keyword,
        "research_focus": report.research_focus,
        "report_title": report.report_title,
        "generated_at": report.generated_at.isoformat(),
        "source_urls": [source.url for source in report.sources],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@router.post(
    "/industry-skills/retrieval-ranking-benchmark/delivery-review",
    response_model=ResearchIndustryKnowledgeDeliveryReviewOut,
)
def build_research_industry_knowledge_delivery_review(
    payload: ResearchIndustryKnowledgeDeliveryReviewRequest,
) -> ResearchIndustryKnowledgeDeliveryReviewOut:
    """Create three strategy-isolated solution-delivery artifacts for human A/B review."""
    report = _require_formal_report(payload.report)
    _dataset, cases = load_industry_knowledge_retrieval_benchmark_dataset()
    case = next((item for item in cases if item.case_id == payload.case_id), None)
    if case is None:
        raise HTTPException(status_code=404, detail="Unknown fixed retrieval-ranking benchmark case")

    source_report_digest = _delivery_review_report_digest(report)
    review_root = (
        resolve_library_dir().parent
        / BENCHMARK_ID
        / "delivery-review"
        / case.case_id
        / source_report_digest[:16]
    )
    artifacts: list[ResearchIndustryKnowledgeDeliveryReviewArtifactOut] = []
    warnings: list[str] = []
    for strategy in STRATEGY_KEYS:
        pack = build_solution_delivery_pack(
            report,
            scenario=payload.scenario or case.query,
            target_customer=payload.target_customer,
            vertical_scene=payload.vertical_scene or case.query,
            supplemental_context=payload.supplemental_context,
            use_industry_skills=payload.use_industry_skills,
            industry_skill_ids=payload.industry_skill_ids,
            industry_knowledge_retrieval_strategy=strategy,
            industry_knowledge_retrieval_industries=case.industries,
            industry_knowledge_retrieval_document_types=case.document_types,
        )
        context = pack.industry_skill_context
        content = "\n".join(
            [
                "# 检索排序报告人工复核工件",
                "",
                "> 该工件以同一正式研报为基础，仅改变本地行业资料检索策略；用于人工 A/B 复核，不代表生产默认策略已切换。",
                "",
                f"- 固定题目：{case.case_id}",
                f"- 固定查询：{case.query}",
                f"- 原始研报：{report.report_title}",
                f"- 原始研报摘要哈希：`{source_report_digest}`",
                f"- 本地检索策略：{context.retrieval_strategy_label or strategy}",
                f"- 策略标识：`{strategy}`",
                f"- 实际复排：{context.rerank_applied} ({context.rerank_backend})",
                "",
                "## 完整方案交付稿",
                pack.export_markdown,
                "",
                "## 人工复核要求",
                "- 对照同一题目的三份工件，从事实支撑、引用可用性、方案可执行性和结构完整性四方面给 1-5 分。",
                "- 将此文件路径填入 human-review.json 对应条目的 report_artifact_path。",
                "- 真实 Cross Encoder 未应用时，不得把候选 B 视为复排通过。",
                "",
            ]
        )
        path = review_root / f"{strategy}.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        artifacts.append(
            ResearchIndustryKnowledgeDeliveryReviewArtifactOut(
                strategy=strategy,
                strategy_label=INDUSTRY_KNOWLEDGE_RETRIEVAL_STRATEGIES[strategy].label,
                report_artifact_path=industry_knowledge_benchmark_artifact_reference(path),
            )
        )
        warnings.extend(context.warnings)
        if strategy == "prefilter_weighted_rerank" and not context.rerank_applied:
            warnings.append("候选 B 未实际应用 Cross Encoder；该工件只可用于记录不可用状态，不能形成复排上线证据。")
    warnings.extend(
        register_industry_knowledge_delivery_review_artifacts(
            case_id=case.case_id,
            artifact_paths={item.strategy: item.report_artifact_path for item in artifacts},
        )
    )
    return ResearchIndustryKnowledgeDeliveryReviewOut(
        case_id=case.case_id,
        query=case.query,
        source_report_title=report.report_title,
        source_report_digest=source_report_digest,
        generated_at=datetime.now(timezone.utc),
        artifacts=artifacts,
        warnings=list(dict.fromkeys(warnings))[:10],
    )


@router.post("/solution-delivery-pack", response_model=ResearchSolutionDeliveryPackOut)
def build_research_solution_delivery_pack(
    payload: ResearchSolutionDeliveryRequest,
) -> ResearchSolutionDeliveryPackOut:
    report = _require_formal_report(payload.report)
    return build_solution_delivery_pack(
        report,
        scenario=payload.scenario,
        target_customer=payload.target_customer,
        vertical_scene=payload.vertical_scene,
        supplemental_context=payload.supplemental_context,
        use_industry_skills=payload.use_industry_skills,
        industry_skill_ids=payload.industry_skill_ids,
        industry_knowledge_retrieval_strategy=payload.industry_knowledge_retrieval_strategy,
    )


@router.post("/solution-intelligence/refresh", response_model=ResearchReportResponse)
def refresh_research_solution_intelligence(
    payload: ResearchSolutionDeliveryRequest,
) -> ResearchReportResponse:
    report = _require_formal_report(payload.report)
    market_intelligence = build_market_intelligence_pack(
        report,
        scenario=payload.scenario,
        target_customer=payload.target_customer,
        vertical_scene=payload.vertical_scene,
    )
    solution_delivery_pack = build_solution_delivery_pack(
        report,
        scenario=payload.scenario,
        target_customer=payload.target_customer,
        vertical_scene=payload.vertical_scene,
        supplemental_context=payload.supplemental_context,
        use_industry_skills=payload.use_industry_skills,
        industry_skill_ids=payload.industry_skill_ids,
        industry_knowledge_retrieval_strategy=payload.industry_knowledge_retrieval_strategy,
    )
    return report.model_copy(
        update={
            "market_intelligence": market_intelligence,
            "solution_delivery_pack": solution_delivery_pack,
        }
    )


@router.post("/retrieval-index/rebuild", response_model=ResearchRetrievalIndexRebuildOut)
def rebuild_research_retrieval_index(
    payload: ResearchRetrievalIndexRebuildRequest,
    db: Session = Depends(get_db),
) -> ResearchRetrievalIndexRebuildOut:
    ensure_demo_user(db)
    result = rebuild_persistent_research_retrieval_index(
        db,
        user_id=settings.single_user_id,
        limit_per_source=payload.limit_per_source,
        batch_size=payload.batch_size,
        max_chunks=payload.max_chunks,
        resume=payload.resume,
        reset=payload.reset,
    )
    return ResearchRetrievalIndexRebuildOut(**result.to_payload())


@router.get("/retrieval-index/status", response_model=ResearchRetrievalIndexStatusOut)
def get_research_retrieval_index_status(
    db: Session = Depends(get_db),
) -> ResearchRetrievalIndexStatusOut:
    ensure_demo_user(db)
    status = get_persistent_research_retrieval_index_status(db, user_id=settings.single_user_id)
    return ResearchRetrievalIndexStatusOut(**status.to_payload())


def _retrieval_hit_out(hit: object) -> ResearchRetrievalIndexSearchHitOut:
    chunk = hit.chunk  # type: ignore[attr-defined]
    snippet = str(chunk.text or "").strip()
    if len(snippet) > 260:
        snippet = f"{snippet[:260]}..."
    return ResearchRetrievalIndexSearchHitOut(
        chunk_id=chunk.chunk_id,
        document_id=chunk.document_id,
        document_type=chunk.document_type,
        title=chunk.title,
        snippet=snippet,
        field_key=chunk.field_key,
        label=chunk.label,
        source_tier=chunk.source_tier,
        source_url=chunk.source_url,
        parent_chunk_id=chunk.parent_chunk_id,
        topic_id=chunk.topic_id,
        topic_name=chunk.topic_name,
        region=chunk.region,
        industry=chunk.industry,
        score=round(float(getattr(hit, "score", 0.0) or 0.0), 4),
        matched_terms=list(getattr(hit, "matched_terms", ()) or ()),
        match_modes=list(getattr(hit, "match_modes", ()) or ()),
        metadata=dict(chunk.metadata or {}),
    )


def _split_query_filter_values(value: str | None) -> set[str]:
    if not value:
        return set()
    return {part.strip() for part in str(value).replace("，", ",").split(",") if part.strip()}


@router.get("/retrieval-index/search", response_model=ResearchRetrievalIndexSearchOut)
def search_research_retrieval_index_endpoint(
    query: str,
    limit: int = 10,
    topic_id: str | None = None,
    document_type: str | None = None,
    source_tier: str | None = None,
    region: str | None = None,
    industry: str | None = None,
    field_key: str | None = None,
    perspective: str | None = None,
    db: Session = Depends(get_db),
) -> ResearchRetrievalIndexSearchOut:
    ensure_demo_user(db)
    runtime_config = resolve_research_experiment_runtime_config(db, consumer="retrieval_search")
    effective_config = runtime_config.effective_config
    hits = search_persistent_research_retrieval_index(
        db,
        query,
        user_id=settings.single_user_id,
        limit=max(1, min(limit, 40)),
        topic_id=topic_id,
        document_types=_split_query_filter_values(document_type),
        source_tiers=_split_query_filter_values(source_tier),
        region=region,
        industry=industry,
        field_keys=_split_query_filter_values(field_key),
        perspectives=_split_query_filter_values(perspective),
        parent_block_boost=float(effective_config.get("parent_block_boost") or 1.0),
        official_source_bias=bool(effective_config.get("official_source_bias", True)),
    )
    return ResearchRetrievalIndexSearchOut(
        query=query,
        hit_count=len(hits),
        hits=[_retrieval_hit_out(hit) for hit in hits],
        runtime_strategy_status=runtime_config.status,
        runtime_strategy_config=effective_config,
        runtime_strategy_warnings=runtime_config.warnings,
    )


@router.get("/review-queue/low-quality", response_model=ResearchLowQualityReviewQueueOut)
def get_low_quality_research_review_queue(
    top: int = 12,
    include_resolved: bool = False,
    db: Session = Depends(get_db),
) -> ResearchLowQualityReviewQueueOut:
    ensure_demo_user(db)
    queue = list_low_quality_research_review_queue(
        db,
        top=max(1, min(top, 40)),
        include_resolved=include_resolved,
    )
    return ResearchLowQualityReviewQueueOut(**queue)


@router.post("/review-queue/low-quality/{entry_id}/rewrite", response_model=ResearchLowQualityReviewActionResponse)
def rewrite_low_quality_research_review_item(
    entry_id: str,
    db: Session = Depends(get_db),
) -> ResearchLowQualityReviewActionResponse:
    ensure_demo_user(db)
    try:
        payload = rewrite_low_quality_research_entry(db, entry_id)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ResearchLowQualityReviewActionResponse(**payload)


@router.post("/review-queue/low-quality/{entry_id}/resolve", response_model=ResearchLowQualityReviewActionResponse)
def resolve_low_quality_research_review_item(
    entry_id: str,
    payload: ResearchLowQualityReviewResolveRequest,
    db: Session = Depends(get_db),
) -> ResearchLowQualityReviewActionResponse:
    ensure_demo_user(db)
    try:
        result = resolve_low_quality_research_entry(
            db,
            entry_id=entry_id,
            action=payload.action,
        )
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return ResearchLowQualityReviewActionResponse(**result)


@router.post("/workspace/compare-snapshots", response_model=ResearchCompareSnapshotOut)
def create_research_compare_snapshot(
    payload: ResearchCompareSnapshotCreateRequest,
    db: Session = Depends(get_db),
) -> ResearchCompareSnapshotOut:
    ensure_demo_user(db)
    try:
        return ResearchCompareSnapshotOut(**save_compare_snapshot(db, payload.model_dump(mode="json")))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/workspace/compare-snapshots/{snapshot_id}", response_model=ResearchCompareSnapshotDetailOut)
def read_research_compare_snapshot(
    snapshot_id: str,
    db: Session = Depends(get_db),
) -> ResearchCompareSnapshotDetailOut:
    ensure_demo_user(db)
    snapshot = get_compare_snapshot(db, snapshot_id)
    if snapshot is None:
        raise HTTPException(status_code=404, detail="Compare snapshot not found")
    return ResearchCompareSnapshotDetailOut(**snapshot)


@router.delete("/workspace/compare-snapshots/{snapshot_id}")
def remove_research_compare_snapshot(
    snapshot_id: str,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    ensure_demo_user(db)
    if not delete_compare_snapshot(db, snapshot_id):
        raise HTTPException(status_code=404, detail="Compare snapshot not found")
    return {"ok": True}


@router.post("/workspace/markdown-archives", response_model=ResearchMarkdownArchiveOut)
def create_research_markdown_archive(
    payload: ResearchMarkdownArchiveCreateRequest,
    db: Session = Depends(get_db),
) -> ResearchMarkdownArchiveOut:
    ensure_demo_user(db)
    try:
        return ResearchMarkdownArchiveOut(**save_markdown_archive(db, payload.model_dump(mode="json")))
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/workspace/markdown-archives/{archive_id}", response_model=ResearchMarkdownArchiveDetailOut)
def read_research_markdown_archive(
    archive_id: str,
    db: Session = Depends(get_db),
) -> ResearchMarkdownArchiveDetailOut:
    ensure_demo_user(db)
    archive = get_markdown_archive(db, archive_id)
    if archive is None:
        raise HTTPException(status_code=404, detail="Markdown archive not found")
    return ResearchMarkdownArchiveDetailOut(**archive)


@router.delete("/workspace/markdown-archives/{archive_id}")
def remove_research_markdown_archive(
    archive_id: str,
    db: Session = Depends(get_db),
) -> dict[str, bool]:
    ensure_demo_user(db)
    if not delete_markdown_archive(db, archive_id):
        raise HTTPException(status_code=404, detail="Markdown archive not found")
    return {"ok": True}


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


@router.get("/workspace/topics/{topic_id}/timeline", response_model=list[ResearchTrackingTopicTimelineEventOut])
def get_research_tracking_topic_timeline(
    topic_id: str,
    db: Session = Depends(get_db),
) -> list[ResearchTrackingTopicTimelineEventOut]:
    ensure_demo_user(db)
    topic = get_tracking_topic(db, topic_id)
    if not topic:
        raise HTTPException(status_code=404, detail="Tracking topic not found")
    return [ResearchTrackingTopicTimelineEventOut(**item) for item in list_tracking_topic_timeline(db, topic_id)]


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


@router.get("/watchlists/automation-status", response_model=ResearchWatchlistAutomationStatusOut)
def get_research_watchlist_automation_status(db: Session = Depends(get_db)) -> ResearchWatchlistAutomationStatusOut:
    ensure_demo_user(db)
    return ResearchWatchlistAutomationStatusOut(**get_watchlist_automation_status())


@router.get("/watchlists/ops-summary", response_model=ResearchWatchlistOpsSummaryOut)
def get_research_watchlist_ops_summary(db: Session = Depends(get_db)) -> ResearchWatchlistOpsSummaryOut:
    ensure_demo_user(db)
    return ResearchWatchlistOpsSummaryOut(**build_watchlist_ops_summary(db))


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


@router.get("/watchlists/run-history", response_model=list[ResearchWatchlistRunOut])
def get_research_watchlist_run_history(
    limit: int = 30,
    status: str | None = None,
    watchlist_id: str | None = None,
    db: Session = Depends(get_db),
) -> list[ResearchWatchlistRunOut]:
    ensure_demo_user(db)
    return [
        ResearchWatchlistRunOut(**item)
        for item in list_watchlist_runs(
            db,
            limit=max(1, min(limit, 100)),
            status=status,
            watchlist_id=watchlist_id,
        )
    ]


@router.get("/watchlists/digest-export", response_model=ResearchWatchlistDigestExportOut)
def get_research_watchlist_digest_export(
    since_hours: int = 24,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> ResearchWatchlistDigestExportOut:
    ensure_demo_user(db)
    digest = build_watchlist_digest_export(
        db,
        since_hours=max(1, min(since_hours, 168)),
        limit=max(1, min(limit, 100)),
    )
    return ResearchWatchlistDigestExportOut(**digest)


@router.patch("/watchlists/{watchlist_id}", response_model=ResearchWatchlistOut)
def update_research_watchlist(
    watchlist_id: str,
    payload: ResearchWatchlistUpdateRequest,
    db: Session = Depends(get_db),
) -> ResearchWatchlistOut:
    ensure_demo_user(db)
    watchlist = get_watchlist_model(db, watchlist_id)
    if watchlist is None:
        raise HTTPException(status_code=404, detail="Watchlist not found")
    save_payload = _build_watchlist_save_payload(watchlist)
    if payload.name is not None:
        save_payload["name"] = payload.name
    if payload.query is not None:
        save_payload["query"] = payload.query
    if payload.region_filter is not None:
        save_payload["region_filter"] = payload.region_filter
    if payload.industry_filter is not None:
        save_payload["industry_filter"] = payload.industry_filter
    if payload.alert_level is not None:
        save_payload["alert_level"] = payload.alert_level
    if payload.schedule is not None:
        save_payload["schedule"] = payload.schedule
    if payload.status is not None:
        save_payload["status"] = payload.status
    if watchlist.tracking_topic_id and (
        payload.research_focus is not None
        or payload.perspective is not None
    ):
        topic = get_tracking_topic(db, str(watchlist.tracking_topic_id))
        if topic:
            save_tracking_topic(
                db,
                {
                    "id": str(watchlist.tracking_topic_id),
                    "name": topic["name"],
                    "keyword": topic["keyword"],
                    "research_focus": payload.research_focus if payload.research_focus is not None else topic["research_focus"],
                    "perspective": payload.perspective if payload.perspective is not None else topic["perspective"],
                    "region_filter": payload.region_filter if payload.region_filter is not None else topic["region_filter"],
                    "industry_filter": payload.industry_filter if payload.industry_filter is not None else topic["industry_filter"],
                    "notes": topic["notes"],
                },
            )
    return ResearchWatchlistOut(**save_watchlist(db, save_payload))


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
    return _refresh_watchlist_core(db, watchlist_id=watchlist_id, payload=payload)


@router.post("/watchlists/run-due", response_model=ResearchWatchlistRunDueResponse)
def run_due_research_watchlists(
    payload: ResearchTrackingTopicRefreshRequest,
    limit: int = 6,
    retry_failed: bool = True,
    max_retry_attempts: int = 1,
    db: Session = Depends(get_db),
) -> ResearchWatchlistRunDueResponse:
    ensure_demo_user(db)
    checked_at = datetime.now(timezone.utc)
    run_id = f"watchlist-run-{checked_at.strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
    due_watchlists = list_due_watchlists(db, now=checked_at, limit=max(1, min(limit, 12)))
    items: list[ResearchWatchlistRunDueItemOut] = []
    notifications: list[str] = []
    refreshed_count = 0
    failed_count = 0
    total_retry_count = 0
    allowed_retries = max(0, min(max_retry_attempts, 3)) if retry_failed else 0
    for watchlist in due_watchlists:
        started_at = datetime.now(timezone.utc)
        result: ResearchWatchlistRefreshResponse | None = None
        last_error = ""
        attempt_count = 0
        for attempt_index in range(allowed_retries + 1):
            attempt_count = attempt_index + 1
            try:
                result = _refresh_watchlist_core(db, watchlist_id=str(watchlist.id), payload=payload)
                last_error = ""
                break
            except HTTPException as exc:
                last_error = str(exc.detail)
            except Exception as exc:  # pragma: no cover - defensive guard for batch runs
                last_error = str(exc)
        retry_count = max(0, attempt_count - 1)
        total_retry_count += retry_count
        completed_at = datetime.now(timezone.utc)
        if result is not None:
            refreshed_count += 1
            current_payload = get_watchlist_payload(db, str(watchlist.id)) or {}
            change_count = len(result.changes)
            summary = result.changes[0].summary if result.changes else (result.topic.last_refresh_note or "专题已刷新")
            notification_level = "medium" if change_count else "low"
            notification = (
                f"{watchlist.name} 识别到 {change_count} 条变化。"
                if change_count
                else f"{watchlist.name} 已完成检查，暂无新增变化。"
            )
            if retry_count:
                notification = f"{notification} 已重试 {retry_count} 次后成功。"
            notifications.append(notification)
            item = ResearchWatchlistRunDueItemOut(
                watchlist_id=str(watchlist.id),
                name=watchlist.name,
                status="refreshed",
                change_count=change_count,
                attempt_count=attempt_count,
                retry_count=retry_count,
                summary=summary,
                next_due_at=current_payload.get("next_due_at"),
                notification_level=notification_level,
            )
            record_watchlist_run(
                db,
                run_id=run_id,
                watchlist_id=watchlist.id,
                watchlist_name=watchlist.name,
                status="refreshed",
                change_count=change_count,
                attempt_count=attempt_count,
                retry_count=retry_count,
                summary=summary,
                notification_level=notification_level,
                notification_payload={"message": notification, "next_due_at": current_payload.get("next_due_at")},
                started_at=started_at,
                completed_at=completed_at,
            )
            items.append(item)
            continue

        failed_count += 1
        notification = f"{watchlist.name} 刷新失败：{last_error or '未知错误'}"
        if retry_count:
            notification = f"{notification}；已重试 {retry_count} 次。"
        notifications.append(notification)
        item = ResearchWatchlistRunDueItemOut(
            watchlist_id=str(watchlist.id),
            name=watchlist.name,
            status="failed",
            change_count=0,
            attempt_count=attempt_count,
            retry_count=retry_count,
            error=last_error,
            summary="刷新失败",
            notification_level="high",
        )
        record_watchlist_run(
            db,
            run_id=run_id,
            watchlist_id=watchlist.id,
            watchlist_name=watchlist.name,
            status="failed",
            change_count=0,
            attempt_count=attempt_count,
            retry_count=retry_count,
            summary="刷新失败",
            error=last_error,
            notification_level="high",
            notification_payload={"message": notification},
            started_at=started_at,
            completed_at=completed_at,
        )
        items.append(item)
    return ResearchWatchlistRunDueResponse(
        checked_at=checked_at,
        run_id=run_id,
        due_count=len(due_watchlists),
        refreshed_count=refreshed_count,
        failed_count=failed_count,
        retry_count=total_retry_count,
        notifications=notifications,
        items=items,
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
def create_research_report(
    payload: ResearchReportRequest,
    db: Session = Depends(get_db),
) -> ResearchReportResponse:
    ensure_demo_user(db)
    return generate_research_report(_with_runtime_generation_strategy(db, payload))


@router.post("/jobs", response_model=ResearchJobOut)
def create_research_job(payload: ResearchJobCreateRequest, db: Session = Depends(get_db)) -> ResearchJobOut:
    ensure_demo_user(db)
    return start_research_job(_with_runtime_generation_strategy(db, payload))


@router.get("/jobs/{job_id}", response_model=ResearchJobOut)
def get_research_job_status(job_id: str) -> ResearchJobOut:
    job = get_research_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Research job not found")
    return job


@router.get(
    "/jobs/{job_id}/clarification",
    response_model=ResearchClarificationPacketOut,
)
def get_research_job_clarification(job_id: str) -> ResearchClarificationPacketOut:
    job = get_research_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Research job not found")
    return job.clarification_packet


@router.post(
    "/jobs/{job_id}/clarification",
    response_model=ResearchClarificationSubmitResponse,
)
def submit_research_job_clarification(
    job_id: str,
    payload: ResearchClarificationSubmitRequest,
) -> ResearchClarificationSubmitResponse:
    try:
        return submit_research_clarification(job_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post(
    "/jobs/{job_id}/experience-feedback",
    response_model=ResearchExperienceFeedbackOut,
)
def submit_research_job_experience_feedback(
    job_id: str,
    payload: ResearchExperienceFeedbackRequest,
) -> ResearchExperienceFeedbackOut:
    try:
        return record_research_experience_feedback(job_id, payload)
    except LookupError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/experience/metrics", response_model=ResearchExperienceMetricsOut)
def get_research_experience_metrics(
    db: Session = Depends(get_db),
) -> ResearchExperienceMetricsOut:
    return build_research_experience_metrics(db=db)


@router.get("/experience/readiness", response_model=ResearchExperienceReadinessOut)
def get_research_experience_readiness(
    db: Session = Depends(get_db),
) -> ResearchExperienceReadinessOut:
    return build_research_experience_readiness(db=db)


@router.get("/jobs/{job_id}/timeline", response_model=list[ResearchJobTimelineEventOut])
def get_research_job_timeline_items(job_id: str) -> list[ResearchJobTimelineEventOut]:
    timeline = get_research_job_timeline(job_id)
    if timeline is None:
        raise HTTPException(status_code=404, detail="Research job not found")
    return [ResearchJobTimelineEventOut(**item) for item in timeline]


@router.get("/jobs/{job_id}/metrics", response_model=ResearchRunMetricsOut)
def get_research_job_metrics_snapshot(job_id: str) -> ResearchRunMetricsOut:
    metrics = get_research_job_metrics(job_id)
    if metrics is None:
        raise HTTPException(status_code=404, detail="Research job metrics not found")
    return metrics


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
    report = _require_formal_report(payload.report)
    _, content = build_research_report_markdown(report, output_language=report.output_language)
    action_cards = build_research_action_cards(report)
    entry = upsert_research_knowledge_entry(
        db,
        keyword=report.keyword,
        title=report.report_title,
        content=content,
        collection_name=payload.collection_name,
        is_focus_reference=payload.is_focus_reference,
        metadata_payload=build_research_report_metadata(
            report,
            action_cards=action_cards,
        ),
    )
    return ResearchReportSaveResponse(
        entry_id=str(entry.id),
        title=entry.title,
        created_at=entry.created_at,
    )


@router.post("/action-plan", response_model=ResearchActionPlanResponse)
def create_research_action_plan(payload: ResearchActionPlanRequest) -> ResearchActionPlanResponse:
    report = _require_formal_report(payload.report)
    return ResearchActionPlanResponse(
        keyword=report.keyword,
        generated_at=datetime.now(timezone.utc),
        cards=build_research_action_cards(report),
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
