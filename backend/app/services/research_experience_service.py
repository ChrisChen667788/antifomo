from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
from statistics import median
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import SessionLocal
from app.models.research_entities import ResearchJob
from app.schemas.research import (
    ResearchExperienceMetricsOut,
    ResearchExperienceReadinessOut,
)
from app.services.content_extractor import normalize_text


EXPERIENCE_RELEASE_VERSION = "2.3.1"
EXPERIENCE_SAMPLE_TARGET = 120
EXPERIENCE_INDUSTRY_TARGET = 3
EXPERIENCE_FEEDBACK_TARGET = 30
EXPERIENCE_CLARIFICATION_TARGET = 20


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _report_payload(job: ResearchJob) -> dict[str, Any]:
    return job.report_payload if isinstance(job.report_payload, dict) else {}


def _interaction_state(job: ResearchJob) -> str:
    report = _report_payload(job)
    return normalize_text(
        str(report.get("interaction_state") or job.interaction_state or "")
    ) or "recovering"


def _industry_bucket(job: ResearchJob) -> str:
    report = _report_payload(job)
    contract = report.get("research_scope_contract")
    if isinstance(contract, dict):
        industries = contract.get("industries")
        if isinstance(industries, list):
            for industry in industries:
                normalized = normalize_text(str(industry))
                if normalized:
                    return normalized
        task_type = normalize_text(str(contract.get("task_type") or ""))
        if task_type:
            return task_type
    return "general_research"


def _events(job: ResearchJob) -> list[dict[str, Any]]:
    payload = job.experience_payload if isinstance(job.experience_payload, dict) else {}
    return [row for row in list(payload.get("events") or []) if isinstance(row, dict)]


def _feedback(job: ResearchJob) -> list[dict[str, Any]]:
    payload = job.experience_payload if isinstance(job.experience_payload, dict) else {}
    return [row for row in list(payload.get("feedback") or []) if isinstance(row, dict)]


def _is_instrumented(job: ResearchJob) -> bool:
    return any(row.get("event") == "job_created" for row in _events(job))


def build_research_experience_metrics(
    *,
    now: datetime | None = None,
    limit: int = 500,
    db: Session | None = None,
) -> ResearchExperienceMetricsOut:
    settings = get_settings()
    generated_at = now or _utc_now()
    query = (
        select(ResearchJob)
        .where(ResearchJob.user_id == settings.single_user_id)
        .order_by(desc(ResearchJob.created_at))
        .limit(max(1, int(limit)))
    )
    if db is not None:
        jobs = list(db.scalars(query).all())
    else:
        with SessionLocal() as owned_db:
            jobs = list(owned_db.scalars(query).all())
    instrumented = [job for job in jobs if _is_instrumented(job)]
    completed = [
        job
        for job in instrumented
        if job.status in {"succeeded", "needs_evidence", "failed"}
        and job.finished_at is not None
    ]
    states = Counter(_interaction_state(job) for job in completed)
    clarification_parents = [
        job
        for job in instrumented
        if job.resumed_child_job_id is not None
        or any(row.get("event") == "clarification_submitted" for row in _events(job))
    ]
    clarification_children = [job for job in instrumented if job.parent_job_id is not None]
    recovered_children = [
        job
        for job in clarification_children
        if job.status == "succeeded" and _interaction_state(job) == "ready"
    ]
    stale_cutoff = generated_at - timedelta(hours=24)
    stale_recoveries = [
        job
        for job in instrumented
        if _interaction_state(job) in {"awaiting_user", "provisional", "system_degraded"}
        and job.resumed_child_job_id is None
        and (_as_utc(job.updated_at) or generated_at) < stale_cutoff
    ]
    durations = [
        max(
            0,
            int(
                (
                    (_as_utc(job.finished_at) or generated_at)
                    - (_as_utc(job.created_at) or generated_at)
                ).total_seconds()
            ),
        )
        for job in completed
    ]
    industry_distribution = Counter(_industry_bucket(job) for job in completed)
    user_supplied_source_count = 0
    provenance_missing_count = 0
    formal_gate_bypass_count = 0
    for job in completed:
        report = _report_payload(job)
        sources = report.get("sources")
        if isinstance(sources, list):
            for source in sources:
                if not isinstance(source, dict):
                    continue
                origin = normalize_text(str(source.get("source_origin") or ""))
                if origin == "user_supplied":
                    user_supplied_source_count += 1
                if origin not in {
                    "search",
                    "adapter",
                    "snapshot_cache",
                    "user_supplied",
                }:
                    provenance_missing_count += 1
        gate = report.get("research_evidence_gate")
        formal_allowed = bool(
            isinstance(gate, dict) and gate.get("formal_report_allowed") is True
        )
        if (
            job.status == "succeeded"
            or _interaction_state(job) == "ready"
        ) and not formal_allowed:
            formal_gate_bypass_count += 1

    feedback_rows = [row for job in instrumented for row in _feedback(job)]
    feedback_scores = [
        int(row.get("score") or 0)
        for row in feedback_rows
        if 1 <= int(row.get("score") or 0) <= 5
    ]
    feedback_reasons = Counter(
        normalize_text(str(row.get("reason") or "other")) or "other"
        for row in feedback_rows
    )
    idempotent_replay_count = sum(
        row.get("event") == "idempotent_replay"
        for job in instrumented
        for row in _events(job)
    )
    return ResearchExperienceMetricsOut(
        generated_at=generated_at,
        sample_size=len(completed),
        completed_count=len(completed),
        ready_count=states["ready"],
        provisional_count=states["provisional"],
        awaiting_user_count=states["awaiting_user"],
        system_degraded_count=states["system_degraded"],
        clarification_started_count=len(clarification_parents),
        clarification_resumed_count=len(clarification_children),
        clarification_recovery_count=len(recovered_children),
        clarification_conversion_rate=round(
            len(recovered_children) * 100 / max(1, len(clarification_parents)),
            1,
        ),
        stale_recovery_count=len(stale_recoveries),
        idempotent_replay_count=idempotent_replay_count,
        median_time_to_result_seconds=int(median(durations)) if durations else 0,
        industry_bucket_count=len(industry_distribution),
        industry_distribution=dict(industry_distribution.most_common(12)),
        user_supplied_source_count=user_supplied_source_count,
        provenance_missing_count=provenance_missing_count,
        formal_gate_bypass_count=formal_gate_bypass_count,
        feedback_count=len(feedback_scores),
        average_feedback_score=round(
            sum(feedback_scores) / max(1, len(feedback_scores)),
            2,
        ),
        too_technical_feedback_rate=round(
            feedback_reasons["too_technical"] * 100 / max(1, len(feedback_rows)),
            1,
        ),
        top_feedback_reasons=[
            f"{reason}:{count}"
            for reason, count in feedback_reasons.most_common(5)
        ],
    )


def build_research_experience_readiness(
    *,
    now: datetime | None = None,
    db: Session | None = None,
) -> ResearchExperienceReadinessOut:
    metrics = build_research_experience_metrics(now=now, db=db)
    blockers: list[str] = []
    warnings: list[str] = []
    if metrics.sample_size < EXPERIENCE_SAMPLE_TARGET:
        blockers.append(
            f"真实体验样本 {metrics.sample_size}/{EXPERIENCE_SAMPLE_TARGET}，尚未达到发布样本量。"
        )
    if metrics.industry_bucket_count < EXPERIENCE_INDUSTRY_TARGET:
        blockers.append(
            f"跨行业覆盖 {metrics.industry_bucket_count}/{EXPERIENCE_INDUSTRY_TARGET}，需补齐行业盲测。"
        )
    if metrics.clarification_started_count < EXPERIENCE_CLARIFICATION_TARGET:
        blockers.append(
            "澄清恢复链路的真实样本不足 20 条，不能确认恢复转化率。"
        )
    elif metrics.clarification_conversion_rate < 65:
        blockers.append(
            f"澄清恢复转化率 {metrics.clarification_conversion_rate:.1f}% 低于 65% 目标。"
        )
    if metrics.feedback_count < EXPERIENCE_FEEDBACK_TARGET:
        blockers.append(
            f"人工体验反馈 {metrics.feedback_count}/{EXPERIENCE_FEEDBACK_TARGET}，客户验收证据不足。"
        )
    elif metrics.average_feedback_score < 4:
        blockers.append(
            f"平均体验评分 {metrics.average_feedback_score:.2f}/5 低于 4.0。"
        )
    if metrics.formal_gate_bypass_count:
        blockers.append(
            f"发现 {metrics.formal_gate_bypass_count} 条正式门禁绕过记录。"
        )
    if metrics.provenance_missing_count:
        blockers.append(
            f"发现 {metrics.provenance_missing_count} 条来源缺少可识别血缘。"
        )
    if metrics.too_technical_feedback_rate > 10:
        warnings.append(
            f"“过于技术化”反馈占 {metrics.too_technical_feedback_rate:.1f}%，高于 10% 目标。"
        )
    stale_rate = (
        metrics.stale_recovery_count * 100
        / max(1, metrics.awaiting_user_count + metrics.provisional_count + metrics.system_degraded_count)
    )
    if stale_rate > 15:
        warnings.append(f"超过 24 小时未恢复的任务占 {stale_rate:.1f}%。")

    score = round(
        min(1, metrics.sample_size / EXPERIENCE_SAMPLE_TARGET) * 25
        + min(1, metrics.industry_bucket_count / EXPERIENCE_INDUSTRY_TARGET) * 15
        + (20 if metrics.formal_gate_bypass_count == 0 else 0)
        + min(1, metrics.clarification_conversion_rate / 65) * 15
        + min(1, metrics.feedback_count / EXPERIENCE_FEEDBACK_TARGET) * 15
        + (10 if metrics.provenance_missing_count == 0 else 0)
    )
    status = "blocked" if blockers else ("watch" if warnings else "pass")
    return ResearchExperienceReadinessOut(
        generated_at=metrics.generated_at,
        release_version=EXPERIENCE_RELEASE_VERSION,
        status=status,
        score=score,
        sample_target=EXPERIENCE_SAMPLE_TARGET,
        metrics=metrics,
        blockers=blockers,
        warnings=warnings,
        next_actions=[
            "运行 3 个以上行业、共 120 条真实任务并记录澄清链路。",
            "采集至少 30 条人工体验反馈，重点关注解释是否易懂。",
            "逐条修复门禁绕过、来源血缘缺失和停滞恢复任务。",
        ],
    )
