from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
from threading import Event, RLock, Thread
from typing import Any, Callable
from urllib import parse
import uuid

from sqlalchemy import desc, func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.research_entities import ResearchJob
from app.schemas.research import (
    ResearchClarificationPacketOut,
    ResearchClarificationSubmitRequest,
    ResearchClarificationSubmitResponse,
    ResearchExperienceFeedbackOut,
    ResearchExperienceFeedbackRequest,
    ResearchJobCreateRequest,
    ResearchJobOut,
    ResearchReportResponse,
    ResearchSupplementalDocumentIn,
)
from app.schemas.research_runtime import ResearchRunMetricsOut
from app.services.content_extractor import normalize_text
from app.services.decision_studio.parsing import parse_document
from app.services.research.clarification import attach_research_interaction
from app.services.research.run_metrics import ResearchRunMetrics
from app.services.gateway_usage_meter import calculate_gateway_billing, capture_gateway_usage
from app.services.research_service import execute_research_report_workflow, rewrite_stored_research_report


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TMP_DIR = PROJECT_ROOT / ".tmp"
LEGACY_JOBS_FILE = TMP_DIR / "research_jobs.json"

settings = get_settings()
_LOCK = RLock()
_WORKER_STOP = Event()
_WORKER_WAKE = Event()
_WORKER_THREAD: Thread | None = None
_WORKER_ID = f"research-worker-{os.getpid()}-{uuid.uuid4().hex[:8]}"
_JOBS_BACKFILL_ATTEMPTED = False
_LEGACY_REPORT_READ_CACHE: dict[tuple[str, str], dict[str, Any]] = {}

# A clarification continuation is a new, fully metered research execution.  Keep
# the limit explicit and server-side so a client cannot accidentally create an
# unbounded parent/child chain when the evidence gate continues to reject every
# candidate source.
MAX_CLARIFICATION_RECOVERY_ATTEMPTS = 3

STAGE_LABELS = {
    "queued": "已进入研究队列",
    "starting": "正在准备研究范围",
    "planning": "正在生成检索计划",
    "adapters": "正在取数 · 汇总定向信息源",
    "search": "正在取数 · 检索公开网页与招采来源",
    "extracting": "正在清洗 · 抽取正文与证据片段",
    "scoping": "正在清洗 · 收敛区域、行业与客户范围",
    "company_contacts": "正在清洗 · 补充官网与公开联系方式",
    "expanding": "正在清洗 · 扩大搜索范围",
    "corrective": "正在清洗 · 执行纠错检索",
    "question_recovery": "正在清洗 · 按证据硬门槛补检",
    "snapshot_recovery": "正在清洗 · 复用近期同题证据并重新校验",
    "synthesizing": "正在分析 · 综合多源证据生成研报",
    "ranking": "正在分析 · 生成甲方、竞品与伙伴排序",
    "packaging": "正在分析 · 整理结构化结论与来源",
    "completed": "研报已生成",
    "needs_evidence": "质量或证据未达标 · 暂不可交付",
    "awaiting_user": "等待补充信息",
    "recovering": "正在从已有证据继续",
    "failed": "研报生成失败",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_datetime(value: Any) -> datetime | None:
    if value in (None, ""):
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            return None
        if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return None


def _materialize_supplemental_documents(
    documents: list[ResearchSupplementalDocumentIn],
) -> list[ResearchSupplementalDocumentIn]:
    materialized: list[ResearchSupplementalDocumentIn] = []
    for document in documents[:4]:
        extracted_text = normalize_text(document.extracted_text)
        if not extracted_text:
            try:
                file_bytes = base64.b64decode(document.file_base64 or "", validate=True)
            except (ValueError, binascii.Error) as exc:
                raise ValueError(f"{document.file_name} 不是有效的 Base64 文件") from exc
            if len(file_bytes) > 10 * 1024 * 1024:
                raise ValueError(f"{document.file_name} 超过 10MB 限制")
            parsed = parse_document(
                file_bytes,
                file_name=document.file_name,
                mime_type=document.mime_type,
                prefer_docling=False,
            )
            extracted_text = normalize_text(parsed.text)
        if not extracted_text:
            raise ValueError(f"{document.file_name} 未抽取到可用文本")
        materialized.append(
            document.model_copy(
                update={
                    "extracted_text": extracted_text[:24000],
                    "file_base64": None,
                }
            )
        )
    return materialized


def _attach_interaction_to_report_payload(
    report_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(report_payload, dict):
        return report_payload
    try:
        report = attach_research_interaction(
            ResearchReportResponse.model_validate(report_payload)
        )
    except Exception:
        return report_payload
    return report.model_dump(mode="json")


def _system_degraded_packet() -> dict[str, Any]:
    return ResearchClarificationPacketOut(
        active=True,
        interaction_state="system_degraded",
        reason_code="system_execution_failed",
        title="系统执行未完成",
        summary="已保留任务参数；请从当前任务重试，无需重新填写研究主题。",
        system_retryable=True,
        recovery_options=[
            {
                "action": "retry_system",
                "label": "重试当前任务",
                "description": "恢复服务后从已有任务参数继续。",
                "recommended": True,
            }
        ],
    ).model_dump(mode="json")


def _enrich_report_with_generation_metrics(
    report_payload: dict[str, Any] | None,
    metrics_payload: dict[str, Any] | None,
    *,
    output_language: str,
) -> dict[str, Any] | None:
    if not isinstance(report_payload, dict) or not isinstance(metrics_payload, dict):
        return report_payload
    cost_ledger = metrics_payload.get("cost_ledger")
    entries = cost_ledger.get("entries") if isinstance(cost_ledger, dict) else None
    if not isinstance(entries, list):
        return report_payload
    generation_entry = next(
        (
            entry
            for entry in reversed(entries)
            if isinstance(entry, dict) and entry.get("operation") == "research_report.txt"
        ),
        None,
    )
    if not generation_entry:
        return report_payload
    metadata = generation_entry.get("metadata") if isinstance(generation_entry.get("metadata"), dict) else {}
    fallback_used = bool(
        generation_entry.get("status") == "fallback"
        or generation_entry.get("provider") == "mock"
        or generation_entry.get("model") == "deterministic-mock"
        or metadata.get("fallback_used") is True
    )
    if not fallback_used:
        return report_payload

    if output_language == "en":
        risk = "The formal report model timed out; this is a degraded draft and cannot be delivered as a final report."
        next_action = "Restore model quota and connectivity, then regenerate the formal report."
    elif output_language == "zh-TW":
        risk = "正式研報模型逾時，當前為降級草稿，不可作為正式交付稿。"
        next_action = "恢復模型額度與連線後重新生成正式研報。"
    else:
        risk = "正式研报模型超时，当前为降级草稿，不可作为正式交付稿。"
        next_action = "恢复模型额度与连接后重新生成正式研报。"

    enriched = dict(report_payload)
    diagnostics = dict(enriched.get("source_diagnostics") or {})
    diagnostics.update(
        generation_provider=str(generation_entry.get("provider") or "mock"),
        generation_model=str(generation_entry.get("model") or "deterministic-mock"),
        generation_status="fallback",
        generation_fallback_used=True,
        generation_notes=list(diagnostics.get("generation_notes") or [risk, next_action]),
    )
    enriched["source_diagnostics"] = diagnostics

    readiness = dict(enriched.get("report_readiness") or {})
    readiness.update(
        status="needs_evidence",
        score=min(int(readiness.get("score") or 45), 45),
        actionable=False,
        evidence_gate_passed=False,
        reasons=list(dict.fromkeys([risk, *(readiness.get("reasons") or [])])),
        missing_axes=list(dict.fromkeys(["正式模型输出", *(readiness.get("missing_axes") or [])])),
        next_verification_steps=list(
            dict.fromkeys([next_action, *(readiness.get("next_verification_steps") or [])])
        ),
    )
    enriched["report_readiness"] = readiness

    quality_profile = enriched.get("quality_profile")
    if isinstance(quality_profile, dict):
        quality_profile = dict(quality_profile)
        quality_profile.update(
            overall_score=min(int(quality_profile.get("overall_score") or 45), 45),
            status="needs_evidence",
            headline=risk,
        )
        enriched["quality_profile"] = quality_profile
    return enriched


def _rewrite_legacy_report_for_read(
    report_payload: dict[str, Any] | None,
    *,
    cache_key: tuple[str, str],
) -> dict[str, Any] | None:
    if not isinstance(report_payload, dict):
        return report_payload
    gate = report_payload.get("research_entity_authenticity_gate")
    if isinstance(gate, dict) and gate.get("enforced") is True and gate.get("passed") is True:
        return report_payload
    with _LOCK:
        cached = _LEGACY_REPORT_READ_CACHE.get(cache_key)
    if cached is not None:
        return cached

    rewritten = rewrite_stored_research_report(
        ResearchReportResponse.model_validate(report_payload)
    ).model_dump(mode="json")
    with _LOCK:
        _LEGACY_REPORT_READ_CACHE[cache_key] = rewritten
        while len(_LEGACY_REPORT_READ_CACHE) > 24:
            _LEGACY_REPORT_READ_CACHE.pop(next(iter(_LEGACY_REPORT_READ_CACHE)))
    return rewritten


def _report_payload_needs_evidence(report_payload: dict[str, Any] | None) -> bool:
    if not isinstance(report_payload, dict):
        return False
    gate = report_payload.get("research_evidence_gate")
    readiness = report_payload.get("report_readiness")
    diagnostics = report_payload.get("source_diagnostics")
    if isinstance(gate, dict) and gate.get("enforced") is True and gate.get("formal_report_allowed") is not True:
        return True
    if isinstance(readiness, dict) and readiness.get("status") == "needs_evidence":
        return True
    if isinstance(diagnostics, dict) and diagnostics.get("generation_fallback_used") is True:
        return True
    return "source_count" in report_payload and int(report_payload.get("source_count") or 0) <= 0


def _needs_evidence_message(report_payload: dict[str, Any] | None) -> str:
    payload = report_payload or {}
    gate = payload.get("research_evidence_gate")
    citation_gate = payload.get("research_citation_gate")
    readiness = payload.get("report_readiness")
    diagnostics = payload.get("source_diagnostics")
    if isinstance(diagnostics, dict) and diagnostics.get("generation_fallback_used") is True:
        return "模型生成已降级，当前草稿暂不可交付"
    if isinstance(gate, dict) and gate.get("enforced") is True and gate.get("formal_report_allowed") is not True:
        accepted = int(gate.get("accepted_source_count") or 0)
        minimum = int(gate.get("minimum_source_count") or 0)
        return (
            f"证据门未通过，正式研报未生成（有效来源 {accepted}/{minimum}）"
            if minimum
            else "证据门未通过，正式研报未生成"
        )
    if "source_count" in payload and int(payload.get("source_count") or 0) <= 0:
        return "有效证据为空，正式研报未生成"
    if isinstance(citation_gate, dict) and citation_gate.get("enforced") is True and citation_gate.get("passed") is not True:
        completeness = int(citation_gate.get("citation_completeness_percent") or 0)
        critical = int(citation_gate.get("critical_claim_coverage_percent") or 0)
        return f"正文已生成，但主张引用门未通过（事实完整率 {completeness}%，关键主张 {critical}%）"
    if isinstance(readiness, dict) and readiness.get("status") == "needs_evidence":
        return f"正文已生成，但交付质量门未通过（质量分 {int(readiness.get('score') or 0)}）"
    return "证据或质量不足，当前结果暂不可交付"


def _apply_clarification_recovery_policy(
    clarification_packet: dict[str, Any] | None,
    *,
    status: str,
    recovery_attempt: int,
) -> tuple[dict[str, Any], bool, bool]:
    packet = dict(clarification_packet or {})
    attempt = max(0, int(recovery_attempt or 0))
    active = bool(packet.get("active"))
    accepted_source_count = max(0, int(packet.get("accepted_source_count") or 0))
    recovery_exhausted = bool(
        active
        and status == "needs_evidence"
        and attempt >= MAX_CLARIFICATION_RECOVERY_ATTEMPTS
    )
    requires_evidence_input = bool(
        active
        and status == "needs_evidence"
        and accepted_source_count == 0
        and attempt >= 1
        and not recovery_exhausted
    )
    recovery_blocked_reason = ""
    packet.update(
        {
            "recovery_attempt": attempt,
            "recovery_limit": MAX_CLARIFICATION_RECOVERY_ATTEMPTS,
            "recovery_exhausted": recovery_exhausted,
            "requires_evidence_input": requires_evidence_input,
        }
    )

    if recovery_exhausted:
        recovery_blocked_reason = "recovery_limit_reached"
        packet.update(
            {
                "interaction_state": "blocked",
                "reason_code": recovery_blocked_reason,
                "title": "补证复核已达到上限",
                "summary": (
                    f"历史任务已完成 {attempt} 次补证复核（当前上限 "
                    f"{MAX_CLARIFICATION_RECOVERY_ATTEMPTS} 次），"
                    "系统已停止自动创建子任务；当前结果仍受证据门禁保护。"
                ),
                "system_retryable": False,
                "questions": [],
                "recovery_options": [
                    option
                    for option in list(packet.get("recovery_options") or [])
                    if isinstance(option, dict)
                    and option.get("action") == "view_provisional"
                    and bool(packet.get("can_view_provisional"))
                ],
                "next_steps": [
                    "当前任务不会再自动续跑，已完成进度和证据快照保持不变。",
                    "如需继续，请新建范围更明确的研究，并随任务附上官方 URL 或可核验文件。",
                    "正式报告仍须通过原有证据、引用和交付质量门禁。",
                ],
            }
        )
    elif requires_evidence_input:
        recovery_blocked_reason = "evidence_input_required"
        recovery_options = [
            {
                "action": "submit_answers",
                "label": "添加来源或文件后补证复核",
                "description": "至少添加 1 个 http(s) 来源或 1 个可抽取文件；仅补充文字不会创建新任务。",
                "recommended": True,
            }
        ]
        if bool(packet.get("can_view_provisional")):
            recovery_options.append(
                {
                    "action": "view_provisional",
                    "label": "先查看受限草稿",
                    "description": "不会解除正式交付保护。",
                    "recommended": False,
                }
            )
        packet.update(
            {
                "interaction_state": "awaiting_user",
                "reason_code": recovery_blocked_reason,
                "title": "需要可核验来源才能继续",
                "summary": (
                    "上一轮补证复核仍未采纳任何来源。为避免重复空跑，"
                    "下一轮必须附上可核验 URL 或文件；文字答案可与来源一并提交，但不能单独启动续跑。"
                ),
                "recovery_options": recovery_options,
                "next_steps": [
                    "补充至少 1 个 http(s) 来源或 1 个可抽取文件。",
                    "可同时回答范围、建设单位或覆盖问题，作为差量检索上下文。",
                    "正式报告仍须通过原有证据、引用和交付质量门禁。",
                ],
            }
        )

    packet["recovery_blocked_reason"] = recovery_blocked_reason
    return packet, recovery_exhausted, requires_evidence_input


def _serialize_job(job: ResearchJob) -> ResearchJobOut:
    report_payload = job.report_payload
    if job.status == "succeeded":
        report_payload = _rewrite_legacy_report_for_read(
            report_payload,
            cache_key=(str(job.id), str(job.updated_at)),
        )
    report_payload = _enrich_report_with_generation_metrics(
        report_payload,
        job.metrics_payload,
        output_language=job.output_language,
    )
    report_payload = _attach_interaction_to_report_payload(report_payload)
    effective_status = job.status
    effective_stage_key = job.stage_key
    effective_stage_label = job.stage_label
    effective_message = job.message
    if job.status == "succeeded" and _report_payload_needs_evidence(report_payload):
        effective_status = "needs_evidence"
        effective_stage_key = "needs_evidence"
        effective_stage_label = STAGE_LABELS["needs_evidence"]
        effective_message = _needs_evidence_message(report_payload)
    report_interaction_state = (
        str(report_payload.get("interaction_state") or "")
        if isinstance(report_payload, dict)
        else ""
    )
    interaction_state = report_interaction_state or str(job.interaction_state or "recovering")
    if effective_status in {"queued", "running"}:
        interaction_state = "recovering"
    elif effective_status == "failed":
        interaction_state = "system_degraded"
    clarification_packet = (
        report_payload.get("clarification_packet")
        if isinstance(report_payload, dict)
        and isinstance(report_payload.get("clarification_packet"), dict)
        else job.clarification_payload or {}
    )
    if effective_status == "failed" and not clarification_packet:
        clarification_packet = _system_degraded_packet()
    clarification_packet, recovery_exhausted, requires_evidence_input = (
        _apply_clarification_recovery_policy(
            clarification_packet,
            status=effective_status,
            recovery_attempt=int(job.recovery_attempt or 0),
        )
    )
    if recovery_exhausted:
        interaction_state = "blocked"
    elif requires_evidence_input:
        interaction_state = "awaiting_user"
    formal_delivery_allowed = bool(
        isinstance(clarification_packet, dict)
        and clarification_packet.get("formal_delivery_allowed")
    )
    accepted_snapshot_digest = str(
        job.accepted_snapshot_digest
        or (
            clarification_packet.get("evidence_snapshot_digest")
            if isinstance(clarification_packet, dict)
            else ""
        )
        or ""
    )
    payload = {
        "id": str(job.id),
        "status": effective_status,
        "keyword": job.keyword,
        "research_focus": job.research_focus,
        "output_language": job.output_language,
        "include_wechat": job.include_wechat,
        "research_mode": job.research_mode,
        "max_sources": job.max_sources,
        "deep_research": job.deep_research,
        "progress_percent": job.progress_percent,
        "stage_key": effective_stage_key,
        "stage_label": effective_stage_label,
        "message": effective_message,
        "estimated_seconds": job.estimated_seconds,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "error": job.error,
        "report": report_payload,
        "timeline": list(job.timeline_payload or []),
        "metrics": job.metrics_payload or None,
        "interaction_state": interaction_state,
        "clarification_packet": clarification_packet,
        "parent_job_id": str(job.parent_job_id) if job.parent_job_id else None,
        "root_job_id": str(job.root_job_id) if job.root_job_id else None,
        "resumed_child_job_id": str(job.resumed_child_job_id) if job.resumed_child_job_id else None,
        "recovery_attempt": int(job.recovery_attempt or 0),
        "recovery_limit": MAX_CLARIFICATION_RECOVERY_ATTEMPTS,
        "recovery_exhausted": recovery_exhausted,
        "requires_evidence_input": requires_evidence_input,
        "accepted_snapshot_digest": accepted_snapshot_digest,
        "formal_delivery_allowed": formal_delivery_allowed,
    }
    return ResearchJobOut.model_validate(payload)


def _append_job_timeline(
    job: ResearchJob,
    *,
    stage_key: str,
    progress_percent: int,
    message: str,
) -> None:
    timeline = list(job.timeline_payload or [])
    timeline.append(
        {
            "stage_key": stage_key,
            "stage_label": STAGE_LABELS.get(stage_key, message),
            "message": message,
            "progress_percent": max(0, min(100, int(progress_percent))),
            "created_at": _utc_now().isoformat(),
        }
    )
    job.timeline_payload = timeline[-24:]


def _read_legacy_jobs() -> list[dict[str, Any]]:
    if not LEGACY_JOBS_FILE.exists():
        return []
    try:
        payload = json.loads(LEGACY_JOBS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(payload, dict):
        return []
    return list(payload.get("jobs") or [])


def _maybe_backfill_jobs() -> None:
    global _JOBS_BACKFILL_ATTEMPTED
    if _JOBS_BACKFILL_ATTEMPTED:
        return
    with SessionLocal() as db:
        has_jobs = bool(db.scalar(select(func.count(ResearchJob.id)).where(ResearchJob.user_id == settings.single_user_id)))
        if has_jobs:
            _JOBS_BACKFILL_ATTEMPTED = True
            return
        legacy_jobs = _read_legacy_jobs()
        if not legacy_jobs:
            _JOBS_BACKFILL_ATTEMPTED = True
            return
        for item in legacy_jobs[:32]:
            db.add(
                ResearchJob(
                    id=uuid.UUID(str(item["id"])) if item.get("id") else uuid.uuid4(),
                    user_id=settings.single_user_id,
                    keyword=str(item.get("keyword") or ""),
                    research_focus=item.get("research_focus"),
                    output_language=str(item.get("output_language") or "zh-CN"),
                    include_wechat=bool(item.get("include_wechat", True)),
                    research_mode=str(item.get("research_mode") or "deep"),
                    max_sources=int(item.get("max_sources") or 14),
                    deep_research=bool(item.get("deep_research", True)),
                    status=str(item.get("status") or "queued"),
                    progress_percent=int(item.get("progress_percent") or 0),
                    stage_key=str(item.get("stage_key") or "queued"),
                    stage_label=str(item.get("stage_label") or ""),
                    message=str(item.get("message") or ""),
                    estimated_seconds=item.get("estimated_seconds"),
                    error=item.get("error"),
                    report_payload=item.get("report") if isinstance(item.get("report"), dict) else None,
                    timeline_payload=item.get("timeline") if isinstance(item.get("timeline"), list) else [],
                    created_at=_normalize_datetime(item.get("created_at")) or _utc_now(),
                    updated_at=_normalize_datetime(item.get("updated_at")) or _utc_now(),
                    started_at=_normalize_datetime(item.get("started_at")),
                    finished_at=_normalize_datetime(item.get("finished_at")),
                )
            )
        db.commit()
    _JOBS_BACKFILL_ATTEMPTED = True


def get_research_job(job_id: str) -> ResearchJobOut | None:
    _maybe_backfill_jobs()
    try:
        parsed_job_id = uuid.UUID(str(job_id))
    except ValueError:
        return None
    with SessionLocal() as db:
        job = db.scalar(
            select(ResearchJob)
            .where(ResearchJob.id == parsed_job_id)
            .where(ResearchJob.user_id == settings.single_user_id)
        )
        if job is None:
            return None
        return _serialize_job(job)


def update_research_job(job_id: str, **changes: Any) -> ResearchJobOut | None:
    _maybe_backfill_jobs()
    try:
        parsed_job_id = uuid.UUID(str(job_id))
    except ValueError:
        return None
    with SessionLocal() as db:
        job = db.scalar(
            select(ResearchJob)
            .where(ResearchJob.id == parsed_job_id)
            .where(ResearchJob.user_id == settings.single_user_id)
        )
        if job is None:
            return None
        if "report" in changes and "report_payload" not in changes:
            changes["report_payload"] = changes.pop("report")
        experience_event = changes.pop("experience_event", None)
        if isinstance(experience_event, dict):
            experience_payload = dict(job.experience_payload or {})
            events = list(experience_payload.get("events") or [])
            events.append(dict(experience_event))
            experience_payload["events"] = events[-40:]
            changes["experience_payload"] = experience_payload
        for key, value in changes.items():
            if key in {"created_at", "updated_at", "started_at", "finished_at", "lease_expires_at"}:
                setattr(job, key, _normalize_datetime(value))
            else:
                setattr(job, key, value)
        if changes.get("stage_key") or changes.get("message"):
            _append_job_timeline(
                job,
                stage_key=str(changes.get("stage_key") or job.stage_key or "queued"),
                progress_percent=int(changes.get("progress_percent") or job.progress_percent or 0),
                message=str(changes.get("message") or job.message or ""),
            )
        job.updated_at = _utc_now()
        db.add(job)
        db.commit()
        db.refresh(job)
        return _serialize_job(job)


def create_research_job(
    payload: ResearchJobCreateRequest,
    *,
    parent_job_id: str | None = None,
    root_job_id: str | None = None,
    recovery_attempt: int = 0,
    idempotency_key: str | None = None,
    recovery_payload: dict[str, Any] | None = None,
) -> ResearchJobOut:
    _maybe_backfill_jobs()
    parsed_parent_job_id = uuid.UUID(parent_job_id) if parent_job_id else None
    parsed_root_job_id = uuid.UUID(root_job_id) if root_job_id else None
    with SessionLocal() as db:
        job = ResearchJob(
            user_id=settings.single_user_id,
            keyword=payload.keyword,
            research_focus=payload.research_focus,
            output_language=payload.output_language,
            include_wechat=payload.include_wechat,
            research_mode=payload.research_mode,
            max_sources=payload.max_sources,
            deep_research=payload.deep_research,
            status="queued",
            progress_percent=2,
            stage_key="queued",
            stage_label="已进入研究队列",
            message="正在初始化关键词研究任务",
            estimated_seconds=420 if payload.research_mode == "deep" else 180,
            timeline_payload=[],
            metrics_payload={},
            request_payload=payload.model_dump(mode="json"),
            interaction_state="recovering",
            clarification_payload={},
            recovery_payload=dict(recovery_payload or {}),
            experience_payload={
                "events": [
                    {
                        "event": "job_created",
                        "at": _utc_now().isoformat(),
                        "recovery_attempt": max(0, int(recovery_attempt)),
                    }
                ]
            },
            parent_job_id=parsed_parent_job_id,
            root_job_id=parsed_root_job_id,
            recovery_attempt=max(0, int(recovery_attempt)),
            idempotency_key=idempotency_key,
        )
        db.add(job)
        db.flush()
        if job.root_job_id is None:
            job.root_job_id = job.id
        _append_job_timeline(
            job,
            stage_key="queued",
            progress_percent=2,
            message="正在初始化关键词研究任务",
        )
        db.commit()
        db.refresh(job)
        return _serialize_job(job)


def _progress_callback(job_id: str) -> Callable[[str, int, str], None]:
    highest_progress = 3

    def emit(stage_key: str, progress_percent: int, message: str) -> None:
        nonlocal highest_progress
        highest_progress = max(highest_progress, max(3, min(99, int(progress_percent))))
        update_research_job(
            job_id,
            status="running",
            stage_key=stage_key,
            stage_label=STAGE_LABELS.get(stage_key, message),
            message=message,
            progress_percent=highest_progress,
            lease_expires_at=_utc_now() + timedelta(seconds=max(60, int(settings.research_job_lease_seconds))),
        )

    return emit


def _snapshot_callback(job_id: str) -> Callable[[Any], None]:
    def emit(report: Any) -> None:
        payload = report.model_dump(mode="json") if hasattr(report, "model_dump") else report
        update_research_job(job_id, report_payload=payload)

    return emit


def _research_job_completion_state(report: ResearchReportResponse) -> tuple[str, str, str]:
    gate = report.research_evidence_gate
    readiness = report.report_readiness
    diagnostics = report.source_diagnostics
    evidence_blocked = bool(gate.enforced and not gate.formal_report_allowed)
    generation_degraded = bool(diagnostics and diagnostics.generation_fallback_used)
    if (
        report.interaction_state != "ready"
        or evidence_blocked
        or generation_degraded
        or readiness.status == "needs_evidence"
        or report.source_count <= 0
    ):
        return (
            "needs_evidence",
            "needs_evidence",
            _needs_evidence_message(report.model_dump(mode="json")),
        )
    return "succeeded", "completed", "研报已生成"


def _run_research_job(job_id: str, payload: ResearchJobCreateRequest) -> None:
    metrics = ResearchRunMetrics()
    usage_before = capture_gateway_usage(settings)
    try:
        update_research_job(
            job_id,
            status="running",
            started_at=_utc_now(),
            stage_key="starting",
            stage_label=STAGE_LABELS["starting"],
            message="正在准备多源研究范围",
            progress_percent=4,
        )
        execution = execute_research_report_workflow(
            payload,
            progress_callback=_progress_callback(job_id),
            snapshot_callback=_snapshot_callback(job_id),
            metrics=metrics,
        )
        interaction_report = attach_research_interaction(execution.report)
        completion_status, completion_stage, completion_message = _research_job_completion_state(interaction_report)
        completion_payload = interaction_report.model_dump(mode="json")
        metrics.set_billing(
            calculate_gateway_billing(
                usage_before,
                capture_gateway_usage(settings),
                quota_units_per_cny=settings.gateway_quota_units_per_cny,
            )
        )
        update_research_job(
            job_id,
            status=completion_status,
            progress_percent=100,
            stage_key=completion_stage,
            stage_label=STAGE_LABELS[completion_stage],
            message=completion_message,
            report_payload=completion_payload,
            metrics_payload=execution.metrics.snapshot(),
            interaction_state=interaction_report.interaction_state,
            clarification_payload=interaction_report.clarification_packet.model_dump(mode="json"),
            accepted_snapshot_digest=interaction_report.clarification_packet.evidence_snapshot_digest,
            experience_event={
                "event": "job_completed",
                "at": _utc_now().isoformat(),
                "interaction_state": interaction_report.interaction_state,
            },
            finished_at=_utc_now(),
            error=None,
            worker_id="",
            lease_expires_at=None,
        )
    except Exception as exc:  # pragma: no cover
        if metrics.finished_at is None:
            metrics.finish("failed")
        metrics.set_billing(
            calculate_gateway_billing(
                usage_before,
                capture_gateway_usage(settings),
                quota_units_per_cny=settings.gateway_quota_units_per_cny,
            )
        )
        update_research_job(
            job_id,
            status="failed",
            progress_percent=100,
            stage_key="failed",
            stage_label=STAGE_LABELS["failed"],
            message="研报生成失败",
            finished_at=_utc_now(),
            error=str(exc),
            metrics_payload=metrics.snapshot(),
            interaction_state="system_degraded",
            clarification_payload=_system_degraded_packet(),
            worker_id="",
            lease_expires_at=None,
            experience_event={
                "event": "job_failed",
                "at": _utc_now().isoformat(),
                "error_type": type(exc).__name__,
            },
        )


def start_research_job(
    payload: ResearchJobCreateRequest,
    *,
    parent_job_id: str | None = None,
    root_job_id: str | None = None,
    recovery_attempt: int = 0,
    idempotency_key: str | None = None,
    recovery_payload: dict[str, Any] | None = None,
) -> ResearchJobOut:
    with _LOCK:
        job = create_research_job(
            payload,
            parent_job_id=parent_job_id,
            root_job_id=root_job_id,
            recovery_attempt=recovery_attempt,
            idempotency_key=idempotency_key,
            recovery_payload=recovery_payload,
        )
        _WORKER_WAKE.set()
        return job


def _request_from_job(job: ResearchJob) -> ResearchJobCreateRequest:
    payload = dict(job.request_payload or {})
    payload.setdefault("keyword", job.keyword)
    payload.setdefault("research_focus", job.research_focus)
    payload.setdefault("output_language", job.output_language)
    payload.setdefault("include_wechat", job.include_wechat)
    payload.setdefault("research_mode", job.research_mode)
    payload.setdefault("max_sources", job.max_sources)
    payload.setdefault("deep_research", job.deep_research)
    return ResearchJobCreateRequest.model_validate(payload)


def _claim_next_research_job() -> tuple[str, ResearchJobCreateRequest] | None:
    with _LOCK:
        with SessionLocal() as db:
            job = db.scalar(
                select(ResearchJob)
                .where(ResearchJob.user_id == settings.single_user_id)
                .where(ResearchJob.status == "queued")
                .order_by(ResearchJob.created_at.asc())
            )
            if job is None:
                return None
            try:
                payload = _request_from_job(job)
            except Exception as exc:
                job.status = "failed"
                job.stage_key = "failed"
                job.stage_label = STAGE_LABELS["failed"]
                job.message = "任务参数无法恢复"
                job.error = f"invalid persisted request payload: {exc}"
                job.finished_at = _utc_now()
                db.add(job)
                db.commit()
                return None
            job.status = "running"
            job.worker_id = _WORKER_ID
            job.execution_attempts = int(job.execution_attempts or 0) + 1
            job.lease_expires_at = _utc_now() + timedelta(
                seconds=max(60, int(settings.research_job_lease_seconds))
            )
            job.updated_at = _utc_now()
            db.add(job)
            db.commit()
            return str(job.id), payload


def recover_interrupted_research_jobs() -> int:
    if not settings.research_job_recover_running_on_startup:
        return 0
    recovered = 0
    recovery_cutoff = _utc_now() - timedelta(
        hours=max(1, int(settings.research_job_recovery_max_age_hours))
    )
    with _LOCK:
        with SessionLocal() as db:
            jobs = db.scalars(
                select(ResearchJob)
                .where(ResearchJob.user_id == settings.single_user_id)
                .where(ResearchJob.status == "running")
            ).all()
            for job in jobs:
                updated_at = _normalize_datetime(job.updated_at) or _normalize_datetime(job.started_at)
                if not job.request_payload or updated_at is None or updated_at < recovery_cutoff:
                    job.status = "failed"
                    job.stage_key = "failed"
                    job.stage_label = STAGE_LABELS["failed"]
                    job.message = "任务中断且缺少有效恢复快照，请重新发起"
                    job.error = "durable recovery snapshot missing or expired"
                    job.worker_id = ""
                    job.lease_expires_at = None
                    job.finished_at = _utc_now()
                    job.updated_at = _utc_now()
                    _append_job_timeline(
                        job,
                        stage_key="failed",
                        progress_percent=100,
                        message=job.message,
                    )
                    db.add(job)
                    continue
                job.status = "queued"
                job.stage_key = "recovering"
                job.stage_label = STAGE_LABELS["recovering"]
                job.message = "服务重启后已恢复到持久队列"
                job.worker_id = ""
                job.lease_expires_at = None
                job.updated_at = _utc_now()
                _append_job_timeline(
                    job,
                    stage_key="recovering",
                    progress_percent=max(3, int(job.progress_percent or 0)),
                    message=job.message,
                )
                db.add(job)
                recovered += 1
            if jobs:
                db.commit()
    return recovered


def _research_job_worker_loop() -> None:
    while not _WORKER_STOP.is_set():
        claimed = _claim_next_research_job()
        if claimed is None:
            _WORKER_WAKE.wait(timeout=max(0.2, float(settings.research_job_worker_poll_seconds)))
            _WORKER_WAKE.clear()
            continue
        job_id, payload = claimed
        _run_research_job(job_id, payload)


def start_research_job_worker() -> dict[str, Any]:
    global _WORKER_THREAD
    with _LOCK:
        if _WORKER_THREAD is not None and _WORKER_THREAD.is_alive():
            return research_job_worker_status()
        if not settings.research_job_worker_enabled:
            return research_job_worker_status()
        recovered = recover_interrupted_research_jobs()
        _WORKER_STOP.clear()
        _WORKER_WAKE.set()
        _WORKER_THREAD = Thread(
            target=_research_job_worker_loop,
            daemon=False,
            name="research-job-worker",
        )
        _WORKER_THREAD.start()
        status = research_job_worker_status()
        status["recovered_jobs"] = recovered
        return status


def stop_research_job_worker(*, timeout_seconds: float = 10.0) -> dict[str, Any]:
    global _WORKER_THREAD
    _WORKER_STOP.set()
    _WORKER_WAKE.set()
    thread = _WORKER_THREAD
    if thread is not None:
        thread.join(timeout=max(0.1, float(timeout_seconds)))
        if not thread.is_alive():
            _WORKER_THREAD = None
    return research_job_worker_status()


def research_job_worker_status() -> dict[str, Any]:
    thread = _WORKER_THREAD
    with SessionLocal() as db:
        queued = int(
            db.scalar(
                select(func.count(ResearchJob.id))
                .where(ResearchJob.user_id == settings.single_user_id)
                .where(ResearchJob.status == "queued")
            )
            or 0
        )
        running = int(
            db.scalar(
                select(func.count(ResearchJob.id))
                .where(ResearchJob.user_id == settings.single_user_id)
                .where(ResearchJob.status == "running")
            )
            or 0
        )
    return {
        "enabled": settings.research_job_worker_enabled,
        "running": bool(thread and thread.is_alive()),
        "worker_id": _WORKER_ID,
        "queued_jobs": queued,
        "running_jobs": running,
        "durable_backend": "sqlalchemy",
    }


def _is_http_url(value: str) -> bool:
    parsed = parse.urlparse(value)
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def _clarification_answer_lines(payload: ResearchClarificationSubmitRequest) -> list[str]:
    lines: list[str] = []
    for answer in payload.answers:
        values = [normalize_text(value) for value in answer.values if normalize_text(value)]
        if values:
            lines.append(f"{answer.question_id}：{'；'.join(values)}")
    return lines


def _offered_recovery_actions(parent: ResearchJobOut) -> set[str]:
    return {
        option.action
        for option in parent.clarification_packet.recovery_options
    }


def _validate_recovery_action(parent: ResearchJobOut, action: str) -> None:
    offered_actions = _offered_recovery_actions(parent)
    if action == "retry_system":
        if (
            parent.status != "failed"
            or not parent.clarification_packet.system_retryable
            or action not in offered_actions
        ):
            raise ValueError("当前任务不是可系统重试状态")
        return
    if action not in {"submit_answers", "continue_search"}:
        raise ValueError("当前任务不支持该补证动作")
    if (
        parent.status != "needs_evidence"
        or not parent.clarification_packet.active
        or action not in offered_actions
    ):
        raise ValueError("当前任务未提供该补证动作")


def _idempotent_child_job(
    *,
    parent_job_id: str,
    idempotency_key: str,
) -> ResearchJobOut | None:
    with SessionLocal() as db:
        job = db.scalar(
            select(ResearchJob)
            .where(ResearchJob.user_id == settings.single_user_id)
            .where(ResearchJob.idempotency_key == idempotency_key)
        )
        if job is None:
            return None
        if str(job.parent_job_id or "") != parent_job_id:
            raise ValueError("该 idempotency_key 已用于另一条续跑任务")
        return _serialize_job(job)


def submit_research_clarification(
    job_id: str,
    payload: ResearchClarificationSubmitRequest,
) -> ResearchClarificationSubmitResponse:
    with _LOCK:
        parent = get_research_job(job_id)
        if parent is None:
            raise LookupError("research job not found")
        if payload.action == "view_provisional":
            if not parent.clarification_packet.can_view_provisional:
                raise ValueError("当前任务没有可查看的受限草稿")
            refreshed_parent = update_research_job(
                job_id,
                recovery_payload={
                    "last_action": payload.action,
                    "idempotency_key": payload.idempotency_key,
                    "recorded_at": _utc_now().isoformat(),
                },
                experience_event={
                    "event": "provisional_viewed",
                    "at": _utc_now().isoformat(),
                },
            )
            if refreshed_parent is None:
                raise LookupError("research job not found")
            return ResearchClarificationSubmitResponse(
                parent_job_id=job_id,
                action=payload.action,
                outcome="provisional_viewed",
                message="已打开受限草稿；正式交付门禁保持不变。",
                parent_job=refreshed_parent,
            )

        replay = _idempotent_child_job(
            parent_job_id=job_id,
            idempotency_key=payload.idempotency_key,
        )
        if replay is not None:
            refreshed_parent = update_research_job(
                job_id,
                experience_event={
                    "event": "idempotent_replay",
                    "at": _utc_now().isoformat(),
                    "child_job_id": replay.id,
                },
            )
            if refreshed_parent is None:
                raise LookupError("research job not found")
            return ResearchClarificationSubmitResponse(
                parent_job_id=job_id,
                action=payload.action,
                outcome="idempotent_replay",
                message="该补证请求已受理，返回原续跑任务。",
                idempotent_replay=True,
                recovery_exhausted=replay.recovery_exhausted,
                requires_evidence_input=replay.requires_evidence_input,
                child_job=replay,
                parent_job=refreshed_parent,
            )

        if parent.recovery_exhausted:
            return ResearchClarificationSubmitResponse(
                parent_job_id=job_id,
                action=payload.action,
                outcome="recovery_blocked",
                message=(
                    f"已达到 {parent.recovery_limit} 次补证复核上限，本次没有创建新任务。"
                    "请新建范围更明确的研究，并附上官方 URL 或可核验文件。"
                ),
                recovery_exhausted=True,
                parent_job=parent,
            )

        _validate_recovery_action(parent, payload.action)

        answer_lines = _clarification_answer_lines(payload)
        supplemental_text = normalize_text(payload.supplemental_text)
        urls = [
            normalize_text(url)
            for url in payload.supplemental_urls
            if normalize_text(url)
        ]
        invalid_urls = [url for url in urls if not _is_http_url(url)]
        if invalid_urls:
            raise ValueError(f"补充来源必须使用 http(s) URL：{invalid_urls[0]}")
        documents = _materialize_supplemental_documents(payload.supplemental_documents)
        if (
            payload.action == "submit_answers"
            and not answer_lines
            and not supplemental_text
            and not urls
            and not documents
        ):
            raise ValueError("请至少回答一个问题或补充一条来源/文档")
        if (
            parent.requires_evidence_input
            and payload.action in {"submit_answers", "continue_search"}
            and not urls
            and not documents
        ):
            return ResearchClarificationSubmitResponse(
                parent_job_id=job_id,
                action=payload.action,
                outcome="recovery_blocked",
                message=(
                    "连续补证后仍无合格来源，本次没有创建新任务。"
                    "请至少添加 1 个 http(s) 来源或 1 个可抽取文件；"
                    "文字答案可与来源一并提交，但不能单独再次续跑。"
                ),
                requires_evidence_input=True,
                parent_job=parent,
            )

        report = parent.report
        packet = parent.clarification_packet
        action_requirement = {
            "submit_answers": "根据用户补充内容差量补检，并只重建受影响章节。",
            "continue_search": "沿当前证据缺口继续一次有界自动检索。",
            "retry_system": "恢复系统能力后复用父任务证据快照重新执行。",
        }[payload.action]
        child_payload = ResearchJobCreateRequest(
            keyword=parent.keyword,
            research_focus=parent.research_focus,
            followup_report_title=report.report_title if report else None,
            followup_report_summary=report.executive_summary if report else None,
            supplemental_context="\n".join(
                [*answer_lines, supplemental_text]
            )[:2400]
            or None,
            supplemental_evidence="\n".join(urls)[:3200] or None,
            supplemental_requirements=action_requirement,
            supplemental_documents=documents,
            output_language=parent.output_language,
            include_wechat=parent.include_wechat,
            research_mode=parent.research_mode,
            max_sources=parent.max_sources,
            deep_research=parent.deep_research,
            runtime_strategy_config={
                "clarification_recovery": {
                    "parent_job_id": parent.id,
                    "parent_snapshot_digest": (
                        parent.accepted_snapshot_digest
                        or packet.evidence_snapshot_digest
                    ),
                    "action": payload.action,
                    "answer_question_ids": [
                        answer.question_id for answer in payload.answers
                    ],
                    "delta_rebuild": True,
                    "snapshot_max_age_hours": 168,
                }
            },
        )
        root_job_id = parent.root_job_id or parent.id
        recovery_payload = {
            "parent_job_id": parent.id,
            "action": payload.action,
            "answer_count": len(answer_lines),
            "supplemental_url_count": len(urls),
            "supplemental_document_count": len(documents),
            "parent_snapshot_digest": (
                parent.accepted_snapshot_digest
                or packet.evidence_snapshot_digest
            ),
            "delta_rebuild": True,
        }
        child = start_research_job(
            child_payload,
            parent_job_id=parent.id,
            root_job_id=root_job_id,
            recovery_attempt=parent.recovery_attempt + 1,
            idempotency_key=payload.idempotency_key,
            recovery_payload=recovery_payload,
        )
        refreshed_parent = update_research_job(
            parent.id,
            resumed_child_job_id=uuid.UUID(child.id),
            recovery_payload={
                **recovery_payload,
                "child_job_id": child.id,
                "idempotency_key": payload.idempotency_key,
                "submitted_at": _utc_now().isoformat(),
            },
            experience_event={
                "event": "clarification_submitted",
                "at": _utc_now().isoformat(),
                "action": payload.action,
                "child_job_id": child.id,
            },
        )
        if refreshed_parent is None:
            raise LookupError("research job not found")
        return ResearchClarificationSubmitResponse(
            parent_job_id=parent.id,
            action=payload.action,
            outcome="recovery_started",
            message=(
                f"已启动第 {child.recovery_attempt}/{child.recovery_limit} 次补证复核；"
                "父任务进度和证据快照已保留。"
            ),
            recovery_exhausted=child.recovery_exhausted,
            requires_evidence_input=child.requires_evidence_input,
            child_job=child,
            parent_job=refreshed_parent,
        )


def record_research_experience_feedback(
    job_id: str,
    payload: ResearchExperienceFeedbackRequest,
) -> ResearchExperienceFeedbackOut:
    try:
        parsed_job_id = uuid.UUID(str(job_id))
    except ValueError as exc:
        raise LookupError("research job not found") from exc
    recorded_at = _utc_now()
    with SessionLocal() as db:
        job = db.scalar(
            select(ResearchJob)
            .where(ResearchJob.id == parsed_job_id)
            .where(ResearchJob.user_id == settings.single_user_id)
        )
        if job is None:
            raise LookupError("research job not found")
        experience = dict(job.experience_payload or {})
        feedback = list(experience.get("feedback") or [])
        feedback.append(
            {
                "score": payload.score,
                "reason": payload.reason,
                "comment": normalize_text(payload.comment),
                "recorded_at": recorded_at.isoformat(),
            }
        )
        experience["feedback"] = feedback[-10:]
        events = list(experience.get("events") or [])
        events.append(
            {
                "event": "experience_feedback",
                "at": recorded_at.isoformat(),
                "score": payload.score,
                "reason": payload.reason,
            }
        )
        experience["events"] = events[-40:]
        job.experience_payload = experience
        job.updated_at = recorded_at
        db.add(job)
        db.commit()
    return ResearchExperienceFeedbackOut(
        job_id=job_id,
        score=payload.score,
        reason=payload.reason,
        comment=normalize_text(payload.comment),
        recorded_at=recorded_at,
    )


def get_research_job_timeline(job_id: str) -> list[dict[str, Any]] | None:
    _maybe_backfill_jobs()
    try:
        parsed_job_id = uuid.UUID(str(job_id))
    except ValueError:
        return None
    with SessionLocal() as db:
        job = db.scalar(
            select(ResearchJob)
            .where(ResearchJob.id == parsed_job_id)
            .where(ResearchJob.user_id == settings.single_user_id)
        )
        if job is None:
            return None
        return list(job.timeline_payload or [])


def get_research_job_metrics(job_id: str) -> ResearchRunMetricsOut | None:
    _maybe_backfill_jobs()
    try:
        parsed_job_id = uuid.UUID(str(job_id))
    except ValueError:
        return None
    with SessionLocal() as db:
        job = db.scalar(
            select(ResearchJob)
            .where(ResearchJob.id == parsed_job_id)
            .where(ResearchJob.user_id == settings.single_user_id)
        )
        if job is None or not job.metrics_payload:
            return None
        return ResearchRunMetricsOut.model_validate(job.metrics_payload)
