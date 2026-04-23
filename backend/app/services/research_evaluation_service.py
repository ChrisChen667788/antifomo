from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import KnowledgeEntry
from app.schemas.research import (
    ResearchOfflineEvaluationMetricOut,
    ResearchOfflineEvaluationOut,
    ResearchOfflineEvaluationWeakReportOut,
    ResearchReportResponse,
)
from app.services.content_extractor import normalize_text

_METRIC_BENCHMARKS: dict[str, float] = {
    "retrieval_hit_rate": 0.72,
    "target_support_rate": 0.68,
    "section_quota_pass_rate": 0.74,
}


def _metric_status(rate: float, *, benchmark: float) -> str:
    if rate >= benchmark:
        return "good"
    if rate >= max(0.0, benchmark - 0.12):
        return "watch"
    return "bad"


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return max(0.0, min(float(numerator) / float(denominator), 1.0))


def _percent(rate: float) -> int:
    return int(round(rate * 100))


def _parse_stored_report(entry: KnowledgeEntry) -> ResearchReportResponse | None:
    payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else None
    report_payload = payload.get("report") if isinstance(payload, dict) else None
    if not isinstance(report_payload, dict):
        return None
    try:
        return ResearchReportResponse.model_validate(report_payload)
    except Exception:
        return None


def _ranked_entity_names(values: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(values, list):
        return names
    for item in values:
        if isinstance(item, dict):
            candidate = normalize_text(str(item.get("name") or ""))
        else:
            candidate = normalize_text(str(getattr(item, "name", "") or ""))
        if candidate and candidate not in names:
            names.append(candidate)
    return names


def _declared_target_accounts(report: ResearchReportResponse) -> list[str]:
    names: list[str] = []
    for value in [*report.target_accounts, *_ranked_entity_names(report.top_target_accounts)]:
        normalized = normalize_text(value)
        if normalized and normalized not in names:
            names.append(normalized)
    return names


def _supported_target_accounts(report: ResearchReportResponse) -> list[str]:
    names: list[str] = []
    for value in report.source_diagnostics.supported_target_accounts:
        normalized = normalize_text(value)
        if normalized and normalized not in names:
            names.append(normalized)
    return names


def _unsupported_target_accounts(report: ResearchReportResponse) -> list[str]:
    supported = set(_supported_target_accounts(report))
    names: list[str] = []
    for value in report.source_diagnostics.unsupported_target_accounts:
        normalized = normalize_text(value)
        if normalized and normalized not in supported and normalized not in names:
            names.append(normalized)
    if names:
        return names
    for value in _declared_target_accounts(report):
        if value not in supported and value not in names:
            names.append(value)
    return names


def _quota_sections(report: ResearchReportResponse) -> list[Any]:
    return [section for section in report.sections if int(getattr(section, "evidence_quota", 0) or 0) > 0]


def _report_retrieval_hit(report: ResearchReportResponse) -> bool:
    diagnostics = report.source_diagnostics
    if int(diagnostics.strict_topic_source_count or 0) <= 0:
        return False
    if float(diagnostics.strict_match_ratio or 0.0) >= 0.34:
        return True
    if diagnostics.retrieval_quality in {"medium", "high"} and report.source_count >= 4:
        return True
    return report.evidence_density != "low" and report.source_quality != "low"


def _weakness_score(report: ResearchReportResponse) -> int:
    diagnostics = report.source_diagnostics
    supported_targets = _supported_target_accounts(report)
    unsupported_targets = _unsupported_target_accounts(report)
    quota_sections = _quota_sections(report)
    failing_sections = [section for section in quota_sections if not bool(getattr(section, "meets_evidence_quota", False))]
    score = 0
    if not _report_retrieval_hit(report):
        score += 34
    score += len(unsupported_targets) * 12
    score += sum(max(int(getattr(section, "quota_gap", 0) or 0), 1) * 8 for section in failing_sections)
    if diagnostics.official_source_ratio < 0.25:
        score += 8
    if report.report_readiness.status != "ready":
        score += 6
    if not supported_targets and _declared_target_accounts(report):
        score += 8
    return score


def build_offline_research_evaluation(
    db: Session,
    *,
    weakest_limit: int = 6,
) -> ResearchOfflineEvaluationOut:
    settings = get_settings()
    entries = db.scalars(
        select(KnowledgeEntry)
        .where(KnowledgeEntry.user_id == settings.single_user_id)
        .where(KnowledgeEntry.source_domain == "research.report")
        .order_by(desc(KnowledgeEntry.updated_at), desc(KnowledgeEntry.created_at))
    ).all()

    reports: list[tuple[KnowledgeEntry, ResearchReportResponse]] = []
    invalid_payloads = 0
    for entry in entries:
        report = _parse_stored_report(entry)
        if report is None:
            invalid_payloads += 1
            continue
        reports.append((entry, report))

    retrieval_hits = 0
    supported_target_total = 0
    total_target_total = 0
    passed_quota_sections = 0
    total_quota_sections = 0
    weak_reports: list[ResearchOfflineEvaluationWeakReportOut] = []

    for entry, report in reports:
        retrieval_hit = _report_retrieval_hit(report)
        if retrieval_hit:
            retrieval_hits += 1

        supported_targets = _supported_target_accounts(report)
        unsupported_targets = _unsupported_target_accounts(report)
        supported_target_total += len(supported_targets)
        total_target_total += len(supported_targets) + len(unsupported_targets)

        quota_sections = _quota_sections(report)
        total_quota_sections += len(quota_sections)
        quota_passed_count = sum(1 for section in quota_sections if bool(getattr(section, "meets_evidence_quota", False)))
        passed_quota_sections += quota_passed_count
        failing_sections = [
            normalize_text(str(getattr(section, "title", "") or "")) or "关键章节"
            for section in quota_sections
            if not bool(getattr(section, "meets_evidence_quota", False))
        ]

        weakness_score = _weakness_score(report)
        if weakness_score <= 0:
            continue
        weak_reports.append(
            ResearchOfflineEvaluationWeakReportOut(
                entry_id=str(entry.id),
                entry_title=normalize_text(entry.title or "") or normalize_text(report.report_title or "") or "知识卡片",
                report_title=normalize_text(report.report_title or ""),
                keyword=normalize_text(report.keyword or ""),
                weakness_score=weakness_score,
                retrieval_hit=retrieval_hit,
                supported_target_accounts=len(supported_targets),
                unsupported_target_accounts=len(unsupported_targets),
                unsupported_targets=unsupported_targets[:3],
                quota_passed_section_count=quota_passed_count,
                quota_total_section_count=len(quota_sections),
                failing_sections=failing_sections[:3],
                official_source_ratio=float(report.source_diagnostics.official_source_ratio or 0.0),
                strict_match_ratio=float(report.source_diagnostics.strict_match_ratio or 0.0),
                retrieval_quality=report.source_diagnostics.retrieval_quality,
            )
        )

    retrieval_hit_rate = _safe_rate(retrieval_hits, len(reports))
    target_support_rate = _safe_rate(supported_target_total, total_target_total)
    section_quota_pass_rate = _safe_rate(passed_quota_sections, total_quota_sections)

    metrics = [
        ResearchOfflineEvaluationMetricOut(
            key="retrieval_hit_rate",
            label="检索命中率",
            numerator=retrieval_hits,
            denominator=len(reports),
            rate=retrieval_hit_rate,
            percent=_percent(retrieval_hit_rate),
            benchmark=_METRIC_BENCHMARKS["retrieval_hit_rate"],
            status=_metric_status(retrieval_hit_rate, benchmark=_METRIC_BENCHMARKS["retrieval_hit_rate"]),
            summary="按研报口径统计：严格主题命中且检索质量不低于中档的比例。",
        ),
        ResearchOfflineEvaluationMetricOut(
            key="target_support_rate",
            label="目标账户支撑率",
            numerator=supported_target_total,
            denominator=total_target_total,
            rate=target_support_rate,
            percent=_percent(target_support_rate),
            benchmark=_METRIC_BENCHMARKS["target_support_rate"],
            status=_metric_status(target_support_rate, benchmark=_METRIC_BENCHMARKS["target_support_rate"]),
            summary="按账户口径统计：研报中被保留的目标账户里，有来源直接支撑的占比。",
        ),
        ResearchOfflineEvaluationMetricOut(
            key="section_quota_pass_rate",
            label="章节证据配额通过率",
            numerator=passed_quota_sections,
            denominator=total_quota_sections,
            rate=section_quota_pass_rate,
            percent=_percent(section_quota_pass_rate),
            benchmark=_METRIC_BENCHMARKS["section_quota_pass_rate"],
            status=_metric_status(section_quota_pass_rate, benchmark=_METRIC_BENCHMARKS["section_quota_pass_rate"]),
            summary="按章节口径统计：带 evidence_quota 的章节中，已满足配额的比例。",
        ),
    ]

    weak_reports.sort(
        key=lambda item: (
            item.weakness_score,
            item.unsupported_target_accounts,
            item.quota_total_section_count - item.quota_passed_section_count,
            1.0 - item.official_source_ratio,
        ),
        reverse=True,
    )

    summary_lines = [
        f"已扫描 {len(entries)} 份存量研报，其中可评估 {len(reports)} 份。",
        (
            f"当前检索命中率 {_percent(retrieval_hit_rate)}%，目标账户支撑率 {_percent(target_support_rate)}%，"
            f"章节证据配额通过率 {_percent(section_quota_pass_rate)}%。"
        ),
    ]
    if weak_reports:
        sample = weak_reports[0]
        summary_lines.append(
            f"当前最需要优先回归的样本是《{sample.report_title or sample.entry_title}》，主要问题集中在"
            f"{'检索命中' if not sample.retrieval_hit else '目标账户支撑/章节配额'}。"
        )

    return ResearchOfflineEvaluationOut(
        generated_at=datetime.now(timezone.utc),
        total_reports=len(entries),
        evaluated_reports=len(reports),
        invalid_payloads=invalid_payloads,
        metrics=metrics,
        weakest_reports=weak_reports[: max(1, min(weakest_limit, 12))],
        summary_lines=summary_lines,
    )
