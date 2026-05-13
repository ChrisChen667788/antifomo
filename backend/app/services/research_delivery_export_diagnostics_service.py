from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.schemas.research import (
    ResearchDeliveryExportDiagnosticsOut,
    ResearchDeliveryExportTrendPointOut,
    ResearchDeliveryExportVersionDeltaOut,
)
from app.services.research_workspace_store import list_markdown_archives


def _record(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _safe_int(value: Any) -> int:
    try:
        return max(0, int(value or 0))
    except (TypeError, ValueError):
        return 0


def _metric_percent(snapshot: dict[str, Any], key: str) -> int:
    metrics = snapshot.get("metrics")
    if not isinstance(metrics, list):
        return 0
    for metric in metrics:
        row = _record(metric)
        if str(row.get("key") or "").strip() != key:
            continue
        return _safe_int(row.get("percent"))
    return 0


def _summary_list_count(summary: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = summary.get(key)
        if isinstance(value, list):
            return len(value)
    return 0


def _current_quality_snapshot(metadata: dict[str, Any]) -> dict[str, Any]:
    current = _record(metadata.get("current_offline_evaluation_snapshot"))
    if current:
        return current
    return _record(metadata.get("offline_evaluation_snapshot"))


def _current_followup_summary(metadata: dict[str, Any]) -> dict[str, Any]:
    current = _record(metadata.get("current_followup_impact_summary"))
    if current:
        return current
    return _record(metadata.get("followup_impact_summary"))


def _trend(value: int) -> str:
    if value > 0:
        return "up"
    if value < 0:
        return "down"
    return "flat"


def _version_delta(
    *,
    key: str,
    label: str,
    current_value: int,
    previous_value: int,
) -> ResearchDeliveryExportVersionDeltaOut:
    delta = current_value - previous_value
    return ResearchDeliveryExportVersionDeltaOut(
        key=key,  # type: ignore[arg-type]
        label=label,
        current_value=current_value,
        previous_value=previous_value,
        delta_value=delta,
        trend=_trend(delta),  # type: ignore[arg-type]
        summary=f"当前 {current_value}，上一版 {previous_value}，变化 {delta:+d}。",
    )


def build_delivery_export_diagnostics(
    db: Session,
    *,
    trend_limit: int = 8,
) -> ResearchDeliveryExportDiagnosticsOut:
    archives = list_markdown_archives(db)
    trend_points: list[ResearchDeliveryExportTrendPointOut] = []
    archives_with_quality_snapshot = 0
    archives_with_followup_summary = 0

    for archive in archives:
        metadata = _record(archive.get("metadata_payload"))
        quality_snapshot = _current_quality_snapshot(metadata)
        followup_summary = _current_followup_summary(metadata)
        changed_section_count = _safe_int(
            metadata.get("changed_section_count")
            or metadata.get("changedSectionCount")
        )
        if quality_snapshot:
            archives_with_quality_snapshot += 1
        if followup_summary:
            archives_with_followup_summary += 1
        if not quality_snapshot and not followup_summary and changed_section_count <= 0:
            continue

        trend_points.append(
            ResearchDeliveryExportTrendPointOut(
                archive_id=str(archive.get("id") or ""),
                archive_kind=str(archive.get("archive_kind") or "compare_markdown"),  # type: ignore[arg-type]
                archive_name=str(archive.get("name") or "未命名导出"),
                updated_at=archive.get("updated_at") or datetime.now(timezone.utc),
                solution_quality_percent=_metric_percent(
                    quality_snapshot,
                    "solution_delivery_quality_pass_rate",
                ),
                proposal_quality_percent=_metric_percent(
                    quality_snapshot,
                    "project_proposal_quality_pass_rate",
                ),
                self_review_gain_percent=_metric_percent(
                    quality_snapshot,
                    "delivery_self_review_gain_rate",
                ),
                followup_impacted_section_count=_summary_list_count(
                    followup_summary,
                    "current_impacted_sections",
                    "currentImpactedSections",
                ),
                changed_section_count=changed_section_count,
            )
        )
        if len(trend_points) >= max(1, min(trend_limit, 16)):
            break

    version_deltas: list[ResearchDeliveryExportVersionDeltaOut] = []
    if len(trend_points) >= 2:
        current = trend_points[0]
        previous = trend_points[1]
        version_deltas = [
            _version_delta(
                key="solution_delivery_quality_pass_rate",
                label="解决方案质量",
                current_value=current.solution_quality_percent,
                previous_value=previous.solution_quality_percent,
            ),
            _version_delta(
                key="project_proposal_quality_pass_rate",
                label="项目建议书质量",
                current_value=current.proposal_quality_percent,
                previous_value=previous.proposal_quality_percent,
            ),
            _version_delta(
                key="delivery_self_review_gain_rate",
                label="自修订增益",
                current_value=current.self_review_gain_percent,
                previous_value=previous.self_review_gain_percent,
            ),
            _version_delta(
                key="followup_impacted_section_count",
                label="追问影响章节",
                current_value=current.followup_impacted_section_count,
                previous_value=previous.followup_impacted_section_count,
            ),
            _version_delta(
                key="changed_section_count",
                label="导出差异章节",
                current_value=current.changed_section_count,
                previous_value=previous.changed_section_count,
            ),
        ]

    summary_lines = [
        f"Markdown 导出归档共 {len(archives)} 份，其中 {len(trend_points)} 份具备可比较诊断数据。",
        (
            f"质量快照归档 {archives_with_quality_snapshot} 份，"
            f"追问影响摘要归档 {archives_with_followup_summary} 份。"
        ),
    ]
    if trend_points:
        latest = trend_points[0]
        summary_lines.append(
            f"最新导出《{latest.archive_name}》的方案/建议书质量快照为 "
            f"{latest.solution_quality_percent}/{latest.proposal_quality_percent}。"
        )

    return ResearchDeliveryExportDiagnosticsOut(
        generated_at=datetime.now(timezone.utc),
        total_archives=len(archives),
        analyzed_archives=len(trend_points),
        archives_with_quality_snapshot=archives_with_quality_snapshot,
        archives_with_followup_summary=archives_with_followup_summary,
        trend_points=trend_points,
        version_deltas=version_deltas,
        summary_lines=summary_lines,
    )
