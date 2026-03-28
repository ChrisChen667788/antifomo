from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from threading import RLock, Thread
from typing import Any, Callable
import uuid

from sqlalchemy import desc, func, select

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.research_entities import ResearchJob
from app.schemas.research import ResearchJobCreateRequest, ResearchJobOut
from app.services.research_service import generate_research_report


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TMP_DIR = PROJECT_ROOT / ".tmp"
LEGACY_JOBS_FILE = TMP_DIR / "research_jobs.json"

settings = get_settings()
_LOCK = RLock()
_THREADS: dict[str, Thread] = {}
_JOBS_BACKFILL_ATTEMPTED = False

STAGE_LABELS = {
    "queued": "已进入研究队列",
    "starting": "正在准备研究范围",
    "planning": "正在生成检索计划",
    "adapters": "正在汇总定向信息源",
    "search": "正在检索公开网页与招采来源",
    "extracting": "正在抽取正文与证据片段",
    "scoping": "正在收敛区域、行业与客户范围",
    "company_contacts": "正在补充官网与公开联系方式",
    "expanding": "正在扩大搜索范围",
    "corrective": "正在执行纠错检索",
    "synthesizing": "正在综合多源证据生成研报",
    "ranking": "正在生成甲方、竞品与伙伴排序",
    "packaging": "正在整理结构化结论与来源",
    "completed": "研报已生成",
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


def _serialize_job(job: ResearchJob) -> ResearchJobOut:
    payload = {
        "id": str(job.id),
        "status": job.status,
        "keyword": job.keyword,
        "research_focus": job.research_focus,
        "output_language": job.output_language,
        "include_wechat": job.include_wechat,
        "research_mode": job.research_mode,
        "max_sources": job.max_sources,
        "deep_research": job.deep_research,
        "progress_percent": job.progress_percent,
        "stage_key": job.stage_key,
        "stage_label": job.stage_label,
        "message": job.message,
        "estimated_seconds": job.estimated_seconds,
        "created_at": job.created_at,
        "updated_at": job.updated_at,
        "started_at": job.started_at,
        "finished_at": job.finished_at,
        "error": job.error,
        "report": job.report_payload,
        "timeline": list(job.timeline_payload or []),
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
        for key, value in changes.items():
            if key in {"created_at", "updated_at", "started_at", "finished_at"}:
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


def create_research_job(payload: ResearchJobCreateRequest) -> ResearchJobOut:
    _maybe_backfill_jobs()
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
        )
        db.add(job)
        db.flush()
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
    def emit(stage_key: str, progress_percent: int, message: str) -> None:
        update_research_job(
            job_id,
            status="running",
            stage_key=stage_key,
            stage_label=STAGE_LABELS.get(stage_key, message),
            message=message,
            progress_percent=max(3, min(99, int(progress_percent))),
        )

    return emit


def _snapshot_callback(job_id: str) -> Callable[[Any], None]:
    def emit(report: Any) -> None:
        payload = report.model_dump(mode="json") if hasattr(report, "model_dump") else report
        update_research_job(job_id, report_payload=payload)

    return emit


def _run_research_job(job_id: str, payload: ResearchJobCreateRequest) -> None:
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
        report = generate_research_report(
            payload,
            progress_callback=_progress_callback(job_id),
            snapshot_callback=_snapshot_callback(job_id),
        )
        update_research_job(
            job_id,
            status="succeeded",
            progress_percent=100,
            stage_key="completed",
            stage_label=STAGE_LABELS["completed"],
            message="研报已生成",
            report_payload=report.model_dump(mode="json"),
            finished_at=_utc_now(),
            error=None,
        )
    except Exception as exc:  # pragma: no cover
        update_research_job(
            job_id,
            status="failed",
            progress_percent=100,
            stage_key="failed",
            stage_label=STAGE_LABELS["failed"],
            message="研报生成失败",
            finished_at=_utc_now(),
            error=str(exc),
        )


def start_research_job(payload: ResearchJobCreateRequest) -> ResearchJobOut:
    with _LOCK:
        job = create_research_job(payload)
        thread = Thread(
            target=_run_research_job,
            args=(job.id, payload),
            daemon=True,
            name=f"research-job-{job.id[:8]}",
        )
        _THREADS[job.id] = thread
        thread.start()
        return job


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
