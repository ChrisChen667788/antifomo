from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any
import uuid

from sqlalchemy import desc, false, func, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import KnowledgeEntry
from app.models.research_entities import (
    ResearchCompareSnapshot,
    ResearchMarkdownArchive,
    ResearchReportVersion,
    ResearchSavedView,
    ResearchTrackingTopic,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
TMP_DIR = PROJECT_ROOT / ".tmp"
LEGACY_WORKSPACE_FILE = TMP_DIR / "research_workspace.json"

settings = get_settings()
_WORKSPACE_BACKFILL_ATTEMPTED = False


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        if value.tzinfo is None or value.tzinfo.utcoffset(value) is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str) and value.strip():
        try:
            parsed = datetime.fromisoformat(value.strip())
        except ValueError:
            return _utc_now()
        if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    return _utc_now()


def _coerce_uuid(value: Any) -> uuid.UUID:
    if isinstance(value, uuid.UUID):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return uuid.UUID(value.strip())
        except ValueError:
            pass
    return uuid.uuid4()


def _read_legacy_workspace() -> dict[str, list[dict[str, Any]]]:
    if not LEGACY_WORKSPACE_FILE.exists():
        return {"saved_views": [], "tracking_topics": [], "markdown_archives": []}
    try:
        payload = json.loads(LEGACY_WORKSPACE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"saved_views": [], "tracking_topics": [], "markdown_archives": []}
    if not isinstance(payload, dict):
        return {"saved_views": [], "tracking_topics": [], "markdown_archives": []}
    return {
        "saved_views": list(payload.get("saved_views") or []),
        "tracking_topics": list(payload.get("tracking_topics") or []),
        "markdown_archives": list(payload.get("markdown_archives") or []),
    }


def _serialize_report_version(version: ResearchReportVersion) -> dict[str, Any]:
    return {
        "id": str(version.id),
        "entry_id": str(version.knowledge_entry_id) if version.knowledge_entry_id else None,
        "title": version.report_title,
        "refreshed_at": version.created_at,
        "source_count": int(version.source_count or 0),
        "evidence_density": str(version.evidence_density or "low"),
        "source_quality": str(version.source_quality or "low"),
        "new_target_count": len(version.new_targets or []),
        "new_competitor_count": len(version.new_competitors or []),
        "new_budget_signal_count": len(version.new_budget_signals or []),
    }


def _serialize_topic(topic: ResearchTrackingTopic, *, versions: list[ResearchReportVersion] | None = None) -> dict[str, Any]:
    ordered_versions = versions or sorted(topic.report_versions, key=lambda item: item.created_at, reverse=True)
    latest_version = topic.last_report_version or (ordered_versions[0] if ordered_versions else None)
    return {
        "id": str(topic.id),
        "name": topic.name,
        "keyword": topic.keyword,
        "research_focus": topic.research_focus or "",
        "perspective": topic.perspective,
        "region_filter": topic.region_filter or "",
        "industry_filter": topic.industry_filter or "",
        "notes": topic.notes or "",
        "created_at": topic.created_at,
        "updated_at": topic.updated_at,
        "last_refreshed_at": topic.last_refreshed_at,
        "last_refresh_status": topic.last_refresh_status or "idle",
        "last_refresh_error": topic.last_refresh_error,
        "last_refresh_note": topic.last_refresh_note,
        "last_refresh_new_targets": list(topic.last_refresh_new_targets or []),
        "last_refresh_new_competitors": list(topic.last_refresh_new_competitors or []),
        "last_refresh_new_budget_signals": list(topic.last_refresh_new_budget_signals or []),
        "last_report_entry_id": str(latest_version.knowledge_entry_id) if latest_version and latest_version.knowledge_entry_id else None,
        "last_report_title": latest_version.report_title if latest_version else None,
        "report_history": [_serialize_report_version(item) for item in ordered_versions[:8]],
    }


def _serialize_saved_view(view: ResearchSavedView) -> dict[str, Any]:
    return {
        "id": str(view.id),
        "name": view.name,
        "query": view.query,
        "filter_mode": view.filter_mode,
        "perspective": view.perspective,
        "region_filter": view.region_filter,
        "industry_filter": view.industry_filter,
        "action_type_filter": view.action_type_filter,
        "focus_only": bool(view.focus_only),
        "created_at": view.created_at,
        "updated_at": view.updated_at,
    }


def _serialize_version_detail(version: ResearchReportVersion) -> dict[str, Any]:
    return {
        "id": str(version.id),
        "topic_id": str(version.topic_id),
        "entry_id": str(version.knowledge_entry_id) if version.knowledge_entry_id else None,
        "title": version.report_title,
        "refreshed_at": version.created_at,
        "source_count": int(version.source_count or 0),
        "evidence_density": str(version.evidence_density or "low"),
        "source_quality": str(version.source_quality or "low"),
        "refresh_note": version.refresh_note,
        "new_targets": list(version.new_targets or []),
        "new_competitors": list(version.new_competitors or []),
        "new_budget_signals": list(version.new_budget_signals or []),
        "report": version.report_payload or None,
        "action_cards": list(version.action_cards_payload or []),
    }


def _build_version_timeline_summary(version: ResearchReportVersion) -> str:
    parts: list[str] = []
    if version.refresh_note:
        parts.append(str(version.refresh_note))
    if version.new_targets:
        parts.append(f"新增甲方 {len(version.new_targets)}")
    if version.new_competitors:
        parts.append(f"新增竞品 {len(version.new_competitors)}")
    if version.new_budget_signals:
        parts.append(f"新增预算线索 {len(version.new_budget_signals)}")
    return " · ".join(parts[:3])


def _serialize_version_timeline_event(version: ResearchReportVersion) -> dict[str, Any]:
    return {
        "id": str(version.id),
        "topic_id": str(version.topic_id),
        "event_type": "report_version",
        "occurred_at": version.created_at,
        "title": version.report_title,
        "summary": _build_version_timeline_summary(version),
        "query": str((version.report_payload or {}).get("keyword") or ""),
        "entry_id": str(version.knowledge_entry_id) if version.knowledge_entry_id else None,
        "report_version_id": str(version.id),
        "linked_report_version_id": None,
        "linked_report_version_title": None,
        "linked_report_version_refreshed_at": None,
        "source_count": int(version.source_count or 0),
        "evidence_density": str(version.evidence_density or "low"),
        "source_quality": str(version.source_quality or "low"),
        "new_targets": list(version.new_targets or []),
        "new_competitors": list(version.new_competitors or []),
        "new_budget_signals": list(version.new_budget_signals or []),
        "compare_snapshot_id": None,
        "compare_snapshot_name": None,
        "markdown_archive_id": None,
        "markdown_archive_kind": None,
        "current_markdown_archive_id": None,
        "compare_markdown_archive_id": None,
        "row_count": 0,
        "source_entry_count": 0,
        "roles": [],
        "preview_names": [],
        "linked_report_diff_summary": [],
    }


def _snapshot_row_value(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _normalize_text_list(values: Any, *, limit: int | None = None) -> list[str]:
    normalized: list[str] = []
    for value in list(values or []):
        text = str(value or "").strip()
        if not text or text in normalized:
            continue
        normalized.append(text)
        if limit is not None and len(normalized) >= limit:
            break
    return normalized


def _normalize_dict_name_list(values: Any, *, limit: int | None = None) -> list[str]:
    normalized: list[str] = []
    for value in list(values or []):
        if not isinstance(value, dict):
            continue
        text = str(value.get("name") or "").strip()
        if not text or text in normalized:
            continue
        normalized.append(text)
        if limit is not None and len(normalized) >= limit:
            break
    return normalized


def _snapshot_preview_names(rows: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for row in rows:
        name = _snapshot_row_value(row, "name")
        if name and name not in names:
            names.append(name)
        if len(names) >= 3:
            break
    return names


def _snapshot_roles(rows: list[dict[str, Any]]) -> list[str]:
    allowed = {"甲方", "中标方", "竞品", "伙伴"}
    roles: list[str] = []
    for row in rows:
        role = _snapshot_row_value(row, "role")
        if role in allowed and role not in roles:
            roles.append(role)
    return roles


def _snapshot_source_entry_count(rows: list[dict[str, Any]]) -> int:
    entry_ids: set[str] = set()
    for row in rows:
        entry_id = _snapshot_row_value(row, "sourceEntryId", "source_entry_id")
        if entry_id:
            entry_ids.add(entry_id)
    return len(entry_ids)


def _snapshot_role_names(rows: list[dict[str, Any]], role: str) -> list[str]:
    names: list[str] = []
    for row in rows:
        row_role = _snapshot_row_value(row, "role")
        if row_role != role:
            continue
        name = _snapshot_row_value(row, "name", "clue")
        if name and name not in names:
            names.append(name)
    return names


def _snapshot_candidate_profile_companies(rows: list[dict[str, Any]]) -> list[str]:
    names: list[str] = []
    for row in rows:
        for value in list(row.get("candidateProfileCompanies") or row.get("candidate_profile_companies") or []):
            text = str(value or "").strip()
            if text and text not in names:
                names.append(text)
    return names


def _snapshot_budget_signals(rows: list[dict[str, Any]]) -> list[str]:
    signals: list[str] = []
    for row in rows:
        value = _snapshot_row_value(row, "budgetSignal", "budget_signal")
        if value and value not in {"—", "未明确"} and value not in signals:
            signals.append(value)
    return signals


def _compare_axis(
    *,
    key: str,
    label: str,
    snapshot_values: list[str],
    linked_values: list[str],
) -> dict[str, Any]:
    snapshot_unique = _normalize_text_list(snapshot_values)
    linked_unique = _normalize_text_list(linked_values)
    linked_set = set(linked_unique)
    snapshot_set = set(snapshot_unique)
    return {
        "key": key,
        "label": label,
        "snapshot_count": len(snapshot_unique),
        "linked_count": len(linked_unique),
        "overlap_count": len(snapshot_set & linked_set),
        "snapshot_only": [item for item in snapshot_unique if item not in linked_set][:4],
        "linked_only": [item for item in linked_unique if item not in snapshot_set][:4],
    }


def _join_summary_items(values: list[str], *, limit: int = 3) -> str:
    trimmed = [item for item in values if str(item or "").strip()][:limit]
    return "、".join(trimmed)


def _build_snapshot_vs_linked_version_diff(
    rows: list[dict[str, Any]],
    report_payload: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not isinstance(report_payload, dict):
        return None

    axes = [
        _compare_axis(
            key="targets",
            label="甲方",
            snapshot_values=_snapshot_role_names(rows, "甲方"),
            linked_values=_normalize_text_list(report_payload.get("target_accounts") or [])
            or _normalize_dict_name_list(report_payload.get("top_target_accounts") or []),
        ),
        _compare_axis(
            key="winners",
            label="中标方",
            snapshot_values=_snapshot_role_names(rows, "中标方"),
            linked_values=_normalize_text_list(report_payload.get("winner_peer_moves") or []),
        ),
        _compare_axis(
            key="competitors",
            label="竞品",
            snapshot_values=_snapshot_role_names(rows, "竞品"),
            linked_values=_normalize_text_list(report_payload.get("competitor_profiles") or [])
            or _normalize_dict_name_list(report_payload.get("top_competitors") or []),
        ),
        _compare_axis(
            key="partners",
            label="伙伴",
            snapshot_values=_snapshot_role_names(rows, "伙伴"),
            linked_values=_normalize_text_list(report_payload.get("ecosystem_partners") or [])
            or _normalize_dict_name_list(report_payload.get("top_ecosystem_partners") or []),
        ),
        _compare_axis(
            key="budget_signals",
            label="预算线索",
            snapshot_values=_snapshot_budget_signals(rows),
            linked_values=_normalize_text_list(report_payload.get("budget_signals") or []),
        ),
        _compare_axis(
            key="candidate_profiles",
            label="候选补证公司",
            snapshot_values=_snapshot_candidate_profile_companies(rows),
            linked_values=_normalize_text_list(
                ((report_payload.get("source_diagnostics") or {}) if isinstance(report_payload.get("source_diagnostics"), dict) else {}).get(
                    "candidate_profile_companies"
                )
                or []
            ),
        ),
    ]

    considered_axes = [axis for axis in axes if axis["snapshot_count"] or axis["linked_count"]]
    if not considered_axes:
        return {
            "status": "unavailable",
            "headline": "当前没有足够字段可用于快照和关联版本对照",
            "summary_lines": [],
            "axes": [],
        }

    snapshot_only_total = sum(len(axis["snapshot_only"]) for axis in considered_axes)
    linked_only_total = sum(len(axis["linked_only"]) for axis in considered_axes)
    overlap_total = sum(int(axis["overlap_count"]) for axis in considered_axes)
    if snapshot_only_total == 0 and linked_only_total == 0:
        status = "aligned"
    elif snapshot_only_total > 0 and linked_only_total > 0:
        status = "mixed"
    elif snapshot_only_total > 0:
        status = "expanded"
    else:
        status = "trimmed"

    headline = {
        "aligned": "快照与关联版本主线基本一致",
        "expanded": "快照在关联版本基础上扩展了更多线索",
        "trimmed": "快照是关联版本的筛选子集",
        "mixed": "快照与关联版本存在双向差异",
        "unavailable": "当前没有足够字段可用于快照和关联版本对照",
    }[status]

    summary_lines: list[str] = []
    role_axes = [axis for axis in considered_axes if axis["key"] in {"targets", "winners", "competitors", "partners"}]
    snapshot_roles = [axis["label"] for axis in role_axes if axis["snapshot_count"]]
    linked_roles = [axis["label"] for axis in role_axes if axis["linked_count"]]
    if snapshot_roles or linked_roles:
        if snapshot_roles == linked_roles:
            summary_lines.append(f"快照覆盖角色与关联版本一致：{_join_summary_items(snapshot_roles, limit=4) or '主线一致'}。")
        else:
            summary_lines.append(
                f"快照覆盖 {_join_summary_items(snapshot_roles, limit=4) or '无明确角色'}；关联版本覆盖 {_join_summary_items(linked_roles, limit=4) or '无明确角色'}。"
            )

    top_snapshot_only_axis = max(considered_axes, key=lambda axis: len(axis["snapshot_only"]))
    if top_snapshot_only_axis["snapshot_only"]:
        summary_lines.append(
            f"快照额外保留的{top_snapshot_only_axis['label']}：{_join_summary_items(top_snapshot_only_axis['snapshot_only'])}。"
        )

    top_linked_only_axis = max(considered_axes, key=lambda axis: len(axis["linked_only"]))
    if top_linked_only_axis["linked_only"]:
        summary_lines.append(
            f"关联版本仍包含但快照未纳入的{top_linked_only_axis['label']}：{_join_summary_items(top_linked_only_axis['linked_only'])}。"
        )

    candidate_axis = next((axis for axis in considered_axes if axis["key"] == "candidate_profiles"), None)
    if candidate_axis and (candidate_axis["snapshot_count"] or candidate_axis["linked_count"]):
        if candidate_axis["snapshot_count"] != candidate_axis["linked_count"]:
            summary_lines.append(
                f"候选补证公司覆盖 {candidate_axis['snapshot_count']} vs {candidate_axis['linked_count']}，说明快照与关联版本的补证范围存在变化。"
            )
        elif candidate_axis["snapshot_count"]:
            summary_lines.append(f"候选补证公司覆盖一致，共 {candidate_axis['snapshot_count']} 家。")

    if not summary_lines:
        if overlap_total:
            summary_lines.append(f"快照与关联版本共用 {overlap_total} 条已命名线索，整体结构较稳定。")
        else:
            summary_lines.append("当前快照与关联版本都缺少稳定的命名线索，建议继续补证。")

    return {
        "status": status,
        "headline": headline,
        "summary_lines": summary_lines[:4],
        "axes": considered_axes[:6],
    }


def _serialize_compare_snapshot(
    snapshot: ResearchCompareSnapshot,
    *,
    include_rows: bool = False,
) -> dict[str, Any]:
    rows = [row for row in (snapshot.rows_payload or []) if isinstance(row, dict)]
    linked_report_diff = _build_snapshot_vs_linked_version_diff(
        rows,
        snapshot.report_version.report_payload if snapshot.report_version and isinstance(snapshot.report_version.report_payload, dict) else None,
    )
    payload = {
        "id": str(snapshot.id),
        "name": snapshot.name,
        "query": snapshot.query or "",
        "region_filter": snapshot.region_filter or "",
        "industry_filter": snapshot.industry_filter or "",
        "role_filter": snapshot.role_filter or "all",
        "tracking_topic_id": str(snapshot.tracking_topic_id) if snapshot.tracking_topic_id else None,
        "tracking_topic_name": snapshot.tracking_topic.name if snapshot.tracking_topic else None,
        "report_version_id": str(snapshot.report_version_id) if snapshot.report_version_id else None,
        "report_version_title": snapshot.report_version.report_title if snapshot.report_version else None,
        "report_version_refreshed_at": snapshot.report_version.created_at if snapshot.report_version else None,
        "summary": snapshot.summary or "",
        "row_count": len(rows),
        "source_entry_count": _snapshot_source_entry_count(rows),
        "roles": _snapshot_roles(rows),
        "preview_names": _snapshot_preview_names(rows),
        "linked_report_diff": linked_report_diff,
        "created_at": snapshot.created_at,
        "updated_at": snapshot.updated_at,
    }
    if include_rows:
        payload["rows"] = rows
    return payload


def _serialize_compare_snapshot_timeline_event(snapshot: ResearchCompareSnapshot) -> dict[str, Any]:
    payload = _serialize_compare_snapshot(snapshot)
    return {
        "id": payload["id"],
        "topic_id": str(snapshot.tracking_topic_id) if snapshot.tracking_topic_id else "",
        "event_type": "compare_snapshot",
        "occurred_at": snapshot.created_at,
        "title": snapshot.name,
        "summary": snapshot.summary or "",
        "query": snapshot.query or "",
        "entry_id": None,
        "report_version_id": None,
        "linked_report_version_id": payload["report_version_id"],
        "linked_report_version_title": payload["report_version_title"],
        "linked_report_version_refreshed_at": payload["report_version_refreshed_at"],
        "source_count": 0,
        "evidence_density": None,
        "source_quality": None,
        "new_targets": [],
        "new_competitors": [],
        "new_budget_signals": [],
        "compare_snapshot_id": payload["id"],
        "compare_snapshot_name": payload["name"],
        "markdown_archive_id": None,
        "markdown_archive_kind": None,
        "current_markdown_archive_id": None,
        "compare_markdown_archive_id": None,
        "row_count": int(payload["row_count"]),
        "source_entry_count": int(payload["source_entry_count"]),
        "roles": list(payload["roles"]),
        "preview_names": list(payload["preview_names"]),
        "linked_report_diff_summary": list((payload.get("linked_report_diff") or {}).get("summary_lines") or []),
    }


def _build_markdown_archive_preview(content: str) -> str:
    parts: list[str] = []
    for raw_line in str(content or "").splitlines():
        line = str(raw_line or "").strip()
        if not line:
            continue
        normalized = line.lstrip("#").strip()
        normalized = normalized.lstrip("-").strip()
        if not normalized:
            continue
        parts.append(normalized)
        if len(" ".join(parts)) >= 240:
            break
    preview = " ".join(parts).strip()
    if len(preview) <= 240:
        return preview
    return f"{preview[:239].rstrip()}…"


def _serialize_markdown_archive(
    archive: ResearchMarkdownArchive,
    *,
    include_content: bool = False,
) -> dict[str, Any]:
    content = str(archive.content or "")
    payload = {
        "id": str(archive.id),
        "archive_kind": archive.archive_kind or "compare_markdown",
        "name": archive.name,
        "filename": archive.filename,
        "query": archive.query or "",
        "region_filter": archive.region_filter or "",
        "industry_filter": archive.industry_filter or "",
        "tracking_topic_id": str(archive.tracking_topic_id) if archive.tracking_topic_id else None,
        "tracking_topic_name": archive.tracking_topic.name if archive.tracking_topic else None,
        "compare_snapshot_id": str(archive.compare_snapshot_id) if archive.compare_snapshot_id else None,
        "compare_snapshot_name": archive.compare_snapshot.name if archive.compare_snapshot else None,
        "report_version_id": str(archive.report_version_id) if archive.report_version_id else None,
        "report_version_title": archive.report_version.report_title if archive.report_version else None,
        "report_version_refreshed_at": archive.report_version.created_at if archive.report_version else None,
        "summary": archive.summary or "",
        "preview_text": _build_markdown_archive_preview(content),
        "content_length": len(content),
        "metadata_payload": archive.metadata_payload or {},
        "created_at": archive.created_at,
        "updated_at": archive.updated_at,
    }
    if include_content:
        payload["content"] = content
    return payload


def _markdown_archive_timeline_preview_names(archive: ResearchMarkdownArchive) -> list[str]:
    metadata = archive.metadata_payload if isinstance(archive.metadata_payload, dict) else {}
    preview_names: list[str] = []
    for key in ("current_archive_name", "compare_archive_name"):
        value = str(metadata.get(key) or "").strip()
        if value and value not in preview_names:
            preview_names.append(value)
    if preview_names:
        return preview_names[:3]
    if archive.compare_snapshot and archive.compare_snapshot.name:
        preview_names.append(archive.compare_snapshot.name)
    if archive.report_version and archive.report_version.report_title:
        preview_names.append(archive.report_version.report_title)
    return preview_names[:3]


def _markdown_archive_timeline_detail_lines(archive: ResearchMarkdownArchive) -> list[str]:
    metadata = archive.metadata_payload if isinstance(archive.metadata_payload, dict) else {}
    lines: list[str] = []
    if archive.archive_kind == "archive_diff_recap":
        shared_count = int(metadata.get("shared_section_count") or 0)
        changed_count = int(metadata.get("changed_section_count") or 0)
        added_count = int(metadata.get("added_section_count") or 0)
        removed_count = int(metadata.get("removed_section_count") or 0)
        if shared_count or changed_count:
            lines.append(f"共享 section {shared_count} · 变更 section {changed_count}")
        if added_count or removed_count:
            lines.append(f"当前新增 {added_count} · 对照独有 {removed_count}")
    elif archive.archive_kind == "topic_version_recap":
        baseline_title = str(metadata.get("baseline_version_title") or "").strip()
        current_title = str(metadata.get("current_version_title") or "").strip()
        if baseline_title or current_title:
            lines.append(f"{baseline_title or '基线版本'} vs {current_title or '对照版本'}")
    elif archive.compare_snapshot and archive.compare_snapshot.name:
        lines.append(f"关联快照 · {archive.compare_snapshot.name}")
    return lines[:2]


def _serialize_markdown_archive_timeline_event(archive: ResearchMarkdownArchive) -> dict[str, Any]:
    payload = _serialize_markdown_archive(archive)
    metadata = archive.metadata_payload if isinstance(archive.metadata_payload, dict) else {}
    return {
        "id": payload["id"],
        "topic_id": str(archive.tracking_topic_id) if archive.tracking_topic_id else "",
        "event_type": "markdown_archive",
        "occurred_at": archive.created_at,
        "title": archive.name,
        "summary": archive.summary or payload["preview_text"],
        "query": archive.query or "",
        "entry_id": None,
        "report_version_id": None,
        "linked_report_version_id": payload["report_version_id"],
        "linked_report_version_title": payload["report_version_title"],
        "linked_report_version_refreshed_at": payload["report_version_refreshed_at"],
        "source_count": 0,
        "evidence_density": None,
        "source_quality": None,
        "new_targets": [],
        "new_competitors": [],
        "new_budget_signals": [],
        "compare_snapshot_id": payload["compare_snapshot_id"],
        "compare_snapshot_name": payload["compare_snapshot_name"],
        "markdown_archive_id": payload["id"],
        "markdown_archive_kind": payload["archive_kind"],
        "current_markdown_archive_id": str(metadata.get("current_archive_id") or "").strip() or None,
        "compare_markdown_archive_id": str(metadata.get("compare_archive_id") or "").strip() or None,
        "row_count": 0,
        "source_entry_count": 0,
        "roles": [],
        "preview_names": _markdown_archive_timeline_preview_names(archive),
        "linked_report_diff_summary": _markdown_archive_timeline_detail_lines(archive),
    }


def _maybe_backfill_workspace(db: Session) -> None:
    global _WORKSPACE_BACKFILL_ATTEMPTED
    if _WORKSPACE_BACKFILL_ATTEMPTED:
        return
    has_views = bool(db.scalar(select(func.count(ResearchSavedView.id)).where(ResearchSavedView.user_id == settings.single_user_id)))
    has_topics = bool(db.scalar(select(func.count(ResearchTrackingTopic.id)).where(ResearchTrackingTopic.user_id == settings.single_user_id)))
    if has_views or has_topics:
        _WORKSPACE_BACKFILL_ATTEMPTED = True
        return

    legacy = _read_legacy_workspace()
    if not legacy["saved_views"] and not legacy["tracking_topics"]:
        _WORKSPACE_BACKFILL_ATTEMPTED = True
        return

    knowledge_entry_ids: list[uuid.UUID] = []
    for topic in legacy["tracking_topics"]:
        for item in list(topic.get("report_history") or []):
            entry_id = item.get("entry_id")
            if isinstance(entry_id, str) and entry_id.strip():
                try:
                    knowledge_entry_ids.append(uuid.UUID(entry_id))
                except ValueError:
                    continue
    knowledge_entries = {
        entry.id: entry
        for entry in db.scalars(
            select(KnowledgeEntry).where(KnowledgeEntry.id.in_(knowledge_entry_ids))
        ).all()
    } if knowledge_entry_ids else {}

    for view in legacy["saved_views"]:
        db.add(
            ResearchSavedView(
                id=_coerce_uuid(view.get("id")),
                user_id=settings.single_user_id,
                name=str(view.get("name") or "未命名视图"),
                query=str(view.get("query") or ""),
                filter_mode=str(view.get("filter_mode") or "all"),
                perspective=str(view.get("perspective") or "all"),
                region_filter=str(view.get("region_filter") or ""),
                industry_filter=str(view.get("industry_filter") or ""),
                action_type_filter=str(view.get("action_type_filter") or ""),
                focus_only=bool(view.get("focus_only") or False),
                created_at=_normalize_datetime(view.get("created_at")),
                updated_at=_normalize_datetime(view.get("updated_at") or view.get("created_at")),
            )
        )

    for topic_payload in legacy["tracking_topics"]:
        topic = ResearchTrackingTopic(
            id=_coerce_uuid(topic_payload.get("id")),
            user_id=settings.single_user_id,
            name=str(topic_payload.get("name") or "未命名专题"),
            keyword=str(topic_payload.get("keyword") or ""),
            research_focus=str(topic_payload.get("research_focus") or ""),
            perspective=str(topic_payload.get("perspective") or "all"),
            region_filter=str(topic_payload.get("region_filter") or ""),
            industry_filter=str(topic_payload.get("industry_filter") or ""),
            notes=str(topic_payload.get("notes") or ""),
            last_refreshed_at=_normalize_datetime(topic_payload.get("last_refreshed_at")) if topic_payload.get("last_refreshed_at") else None,
            last_refresh_status=str(topic_payload.get("last_refresh_status") or "idle"),
            last_refresh_error=topic_payload.get("last_refresh_error"),
            last_refresh_note=topic_payload.get("last_refresh_note"),
            last_refresh_new_targets=list(topic_payload.get("last_refresh_new_targets") or []),
            last_refresh_new_competitors=list(topic_payload.get("last_refresh_new_competitors") or []),
            last_refresh_new_budget_signals=list(topic_payload.get("last_refresh_new_budget_signals") or []),
            created_at=_normalize_datetime(topic_payload.get("created_at")),
            updated_at=_normalize_datetime(topic_payload.get("updated_at") or topic_payload.get("created_at")),
        )
        db.add(topic)
        db.flush()

        versions: list[ResearchReportVersion] = []
        for version_payload in list(topic_payload.get("report_history") or []):
            entry_id_value = version_payload.get("entry_id")
            knowledge_entry_id: uuid.UUID | None = None
            if isinstance(entry_id_value, str) and entry_id_value.strip():
                try:
                    knowledge_entry_id = uuid.UUID(entry_id_value)
                except ValueError:
                    knowledge_entry_id = None
            linked_entry = knowledge_entries.get(knowledge_entry_id) if knowledge_entry_id else None
            metadata_payload = linked_entry.metadata_payload if linked_entry and isinstance(linked_entry.metadata_payload, dict) else {}
            report_payload = metadata_payload.get("report") if isinstance(metadata_payload.get("report"), dict) else {}
            action_cards_payload = metadata_payload.get("action_cards") if isinstance(metadata_payload.get("action_cards"), list) else []
            version = ResearchReportVersion(
                topic_id=topic.id,
                knowledge_entry_id=knowledge_entry_id,
                report_title=str(version_payload.get("title") or linked_entry.title if linked_entry else "未命名研报"),
                report_payload=report_payload or {},
                action_cards_payload=action_cards_payload or [],
                source_count=int(version_payload.get("source_count") or 0),
                evidence_density=str(version_payload.get("evidence_density") or "low"),
                source_quality=str(version_payload.get("source_quality") or "low"),
                refresh_note=str(topic_payload.get("last_refresh_note") or "") or None,
                new_targets=[],
                new_competitors=[],
                new_budget_signals=[],
                created_at=_normalize_datetime(version_payload.get("refreshed_at")),
            )
            db.add(version)
            db.flush()
            versions.append(version)

        if versions:
            ordered_versions = sorted(versions, key=lambda item: item.created_at, reverse=True)
            topic.last_report_version_id = ordered_versions[0].id

    db.commit()
    _WORKSPACE_BACKFILL_ATTEMPTED = True


def list_saved_views(db: Session) -> list[dict[str, Any]]:
    _maybe_backfill_workspace(db)
    views = db.scalars(
        select(ResearchSavedView)
        .where(ResearchSavedView.user_id == settings.single_user_id)
        .order_by(desc(ResearchSavedView.updated_at), desc(ResearchSavedView.created_at))
    ).all()
    return [_serialize_saved_view(item) for item in views]


def list_tracking_topics(db: Session) -> list[dict[str, Any]]:
    _maybe_backfill_workspace(db)
    topics = db.scalars(
        select(ResearchTrackingTopic)
        .where(ResearchTrackingTopic.user_id == settings.single_user_id)
        .order_by(desc(ResearchTrackingTopic.updated_at), desc(ResearchTrackingTopic.created_at))
    ).all()
    return [_serialize_topic(item) for item in topics]


def list_compare_snapshots(db: Session) -> list[dict[str, Any]]:
    _maybe_backfill_workspace(db)
    snapshots = db.scalars(
        select(ResearchCompareSnapshot)
        .where(ResearchCompareSnapshot.user_id == settings.single_user_id)
        .order_by(desc(ResearchCompareSnapshot.updated_at), desc(ResearchCompareSnapshot.created_at))
    ).all()
    return [_serialize_compare_snapshot(item) for item in snapshots]


def list_markdown_archives(db: Session) -> list[dict[str, Any]]:
    _maybe_backfill_workspace(db)
    archives = db.scalars(
        select(ResearchMarkdownArchive)
        .where(ResearchMarkdownArchive.user_id == settings.single_user_id)
        .order_by(desc(ResearchMarkdownArchive.updated_at), desc(ResearchMarkdownArchive.created_at))
    ).all()
    return [_serialize_markdown_archive(item) for item in archives]


def save_saved_view(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    _maybe_backfill_workspace(db)
    view_id = _coerce_uuid(payload.get("id")) if payload.get("id") else None
    existing = None
    if view_id is not None:
        existing = db.scalar(
            select(ResearchSavedView)
            .where(ResearchSavedView.id == view_id)
            .where(ResearchSavedView.user_id == settings.single_user_id)
        )
    view = existing or ResearchSavedView(id=view_id or uuid.uuid4(), user_id=settings.single_user_id)
    view.name = str(payload.get("name") or "未命名视图")
    view.query = str(payload.get("query") or "")
    view.filter_mode = str(payload.get("filter_mode") or "all")
    view.perspective = str(payload.get("perspective") or "all")
    view.region_filter = str(payload.get("region_filter") or "")
    view.industry_filter = str(payload.get("industry_filter") or "")
    view.action_type_filter = str(payload.get("action_type_filter") or "")
    view.focus_only = bool(payload.get("focus_only") or False)
    if existing is None and payload.get("created_at"):
        view.created_at = _normalize_datetime(payload.get("created_at"))
    db.add(view)
    db.commit()
    db.refresh(view)
    return _serialize_saved_view(view)


def delete_saved_view(db: Session, view_id: str) -> bool:
    _maybe_backfill_workspace(db)
    try:
        parsed_view_id = uuid.UUID(str(view_id))
    except ValueError:
        return False
    existing = db.scalar(
        select(ResearchSavedView)
        .where(ResearchSavedView.id == parsed_view_id)
        .where(ResearchSavedView.user_id == settings.single_user_id)
    )
    if existing is None:
        return False
    db.delete(existing)
    db.commit()
    return True


def save_compare_snapshot(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    _maybe_backfill_workspace(db)
    tracking_topic_id: uuid.UUID | None = None
    report_version_id: uuid.UUID | None = None
    raw_topic_id = payload.get("tracking_topic_id")
    if isinstance(raw_topic_id, str) and raw_topic_id.strip():
        try:
            tracking_topic_id = uuid.UUID(raw_topic_id.strip())
        except ValueError as exc:
            raise ValueError("Invalid tracking topic id") from exc
        topic = db.scalar(
            select(ResearchTrackingTopic)
            .where(ResearchTrackingTopic.id == tracking_topic_id)
            .where(ResearchTrackingTopic.user_id == settings.single_user_id)
        )
        if topic is None:
            raise LookupError("Tracking topic not found")
        report_version_id = topic.last_report_version_id

    rows = [row for row in list(payload.get("rows") or []) if isinstance(row, dict)]
    snapshot = ResearchCompareSnapshot(
        user_id=settings.single_user_id,
        tracking_topic_id=tracking_topic_id,
        report_version_id=report_version_id,
        name=str(payload.get("name") or "未命名对比快照"),
        query=str(payload.get("query") or ""),
        region_filter=str(payload.get("region_filter") or ""),
        industry_filter=str(payload.get("industry_filter") or ""),
        role_filter=str(payload.get("role_filter") or "all"),
        summary=str(payload.get("summary") or ""),
        rows_payload=rows,
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return _serialize_compare_snapshot(snapshot)


def save_markdown_archive(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    _maybe_backfill_workspace(db)
    tracking_topic_id: uuid.UUID | None = None
    compare_snapshot_id: uuid.UUID | None = None
    report_version_id: uuid.UUID | None = None
    topic: ResearchTrackingTopic | None = None
    snapshot: ResearchCompareSnapshot | None = None
    report_version: ResearchReportVersion | None = None

    raw_topic_id = payload.get("tracking_topic_id")
    if isinstance(raw_topic_id, str) and raw_topic_id.strip():
        try:
            tracking_topic_id = uuid.UUID(raw_topic_id.strip())
        except ValueError as exc:
            raise ValueError("Invalid tracking topic id") from exc
        topic = db.scalar(
            select(ResearchTrackingTopic)
            .where(ResearchTrackingTopic.id == tracking_topic_id)
            .where(ResearchTrackingTopic.user_id == settings.single_user_id)
        )
        if topic is None:
            raise LookupError("Tracking topic not found")

    raw_snapshot_id = payload.get("compare_snapshot_id")
    if isinstance(raw_snapshot_id, str) and raw_snapshot_id.strip():
        try:
            compare_snapshot_id = uuid.UUID(raw_snapshot_id.strip())
        except ValueError as exc:
            raise ValueError("Invalid compare snapshot id") from exc
        snapshot = db.scalar(
            select(ResearchCompareSnapshot)
            .where(ResearchCompareSnapshot.id == compare_snapshot_id)
            .where(ResearchCompareSnapshot.user_id == settings.single_user_id)
        )
        if snapshot is None:
            raise LookupError("Compare snapshot not found")
        if tracking_topic_id is None and snapshot.tracking_topic_id:
            tracking_topic_id = snapshot.tracking_topic_id
            topic = snapshot.tracking_topic
        if report_version_id is None and snapshot.report_version_id:
            report_version_id = snapshot.report_version_id
            report_version = snapshot.report_version

    raw_report_version_id = payload.get("report_version_id")
    if isinstance(raw_report_version_id, str) and raw_report_version_id.strip():
        try:
            report_version_id = uuid.UUID(raw_report_version_id.strip())
        except ValueError as exc:
            raise ValueError("Invalid report version id") from exc
        report_version = db.scalar(
            select(ResearchReportVersion)
            .join(ResearchTrackingTopic, ResearchTrackingTopic.id == ResearchReportVersion.topic_id)
            .where(ResearchTrackingTopic.user_id == settings.single_user_id)
            .where(ResearchReportVersion.id == report_version_id)
        )
        if report_version is None:
            raise LookupError("Report version not found")
        if tracking_topic_id is None:
            tracking_topic_id = report_version.topic_id
            topic = report_version.topic

    if snapshot and tracking_topic_id and snapshot.tracking_topic_id and snapshot.tracking_topic_id != tracking_topic_id:
        raise ValueError("Compare snapshot does not belong to tracking topic")
    if report_version and tracking_topic_id and report_version.topic_id != tracking_topic_id:
        raise ValueError("Report version does not belong to tracking topic")
    if snapshot and report_version_id and snapshot.report_version_id and snapshot.report_version_id != report_version_id:
        raise ValueError("Compare snapshot does not belong to report version")

    archive = ResearchMarkdownArchive(
        user_id=settings.single_user_id,
        tracking_topic_id=tracking_topic_id,
        compare_snapshot_id=compare_snapshot_id,
        report_version_id=report_version_id,
        archive_kind=str(payload.get("archive_kind") or "compare_markdown"),
        name=str(payload.get("name") or "未命名 Markdown 归档"),
        filename=str(payload.get("filename") or "research-export.md"),
        query=str(payload.get("query") or ""),
        region_filter=str(payload.get("region_filter") or ""),
        industry_filter=str(payload.get("industry_filter") or ""),
        summary=str(payload.get("summary") or ""),
        content=str(payload.get("content") or ""),
        metadata_payload=payload.get("metadata_payload") if isinstance(payload.get("metadata_payload"), dict) else {},
    )
    db.add(archive)
    db.commit()
    db.refresh(archive)
    return _serialize_markdown_archive(archive)


def get_compare_snapshot(db: Session, snapshot_id: str) -> dict[str, Any] | None:
    _maybe_backfill_workspace(db)
    try:
        parsed_snapshot_id = uuid.UUID(str(snapshot_id))
    except ValueError:
        return None
    snapshot = db.scalar(
        select(ResearchCompareSnapshot)
        .where(ResearchCompareSnapshot.id == parsed_snapshot_id)
        .where(ResearchCompareSnapshot.user_id == settings.single_user_id)
    )
    if snapshot is None:
        return None
    return _serialize_compare_snapshot(snapshot, include_rows=True)


def get_markdown_archive(db: Session, archive_id: str) -> dict[str, Any] | None:
    _maybe_backfill_workspace(db)
    try:
        parsed_archive_id = uuid.UUID(str(archive_id))
    except ValueError:
        return None
    archive = db.scalar(
        select(ResearchMarkdownArchive)
        .where(ResearchMarkdownArchive.id == parsed_archive_id)
        .where(ResearchMarkdownArchive.user_id == settings.single_user_id)
    )
    if archive is None:
        return None
    return _serialize_markdown_archive(archive, include_content=True)


def delete_compare_snapshot(db: Session, snapshot_id: str) -> bool:
    _maybe_backfill_workspace(db)
    try:
        parsed_snapshot_id = uuid.UUID(str(snapshot_id))
    except ValueError:
        return False
    snapshot = db.scalar(
        select(ResearchCompareSnapshot)
        .where(ResearchCompareSnapshot.id == parsed_snapshot_id)
        .where(ResearchCompareSnapshot.user_id == settings.single_user_id)
    )
    if snapshot is None:
        return False
    linked_archives = db.scalars(
        select(ResearchMarkdownArchive)
        .where(ResearchMarkdownArchive.user_id == settings.single_user_id)
        .where(ResearchMarkdownArchive.compare_snapshot_id == parsed_snapshot_id)
    ).all()
    for archive in linked_archives:
        archive.compare_snapshot_id = None
        db.add(archive)
    db.delete(snapshot)
    db.commit()
    return True


def delete_markdown_archive(db: Session, archive_id: str) -> bool:
    _maybe_backfill_workspace(db)
    try:
        parsed_archive_id = uuid.UUID(str(archive_id))
    except ValueError:
        return False
    archive = db.scalar(
        select(ResearchMarkdownArchive)
        .where(ResearchMarkdownArchive.id == parsed_archive_id)
        .where(ResearchMarkdownArchive.user_id == settings.single_user_id)
    )
    if archive is None:
        return False
    db.delete(archive)
    db.commit()
    return True


def save_tracking_topic(db: Session, payload: dict[str, Any]) -> dict[str, Any]:
    _maybe_backfill_workspace(db)
    topic_id = _coerce_uuid(payload.get("id")) if payload.get("id") else None
    existing = None
    if topic_id is not None:
        existing = db.scalar(
            select(ResearchTrackingTopic)
            .where(ResearchTrackingTopic.id == topic_id)
            .where(ResearchTrackingTopic.user_id == settings.single_user_id)
        )
    topic = existing or ResearchTrackingTopic(id=topic_id or uuid.uuid4(), user_id=settings.single_user_id)
    topic.name = str(payload.get("name") or "未命名专题")
    topic.keyword = str(payload.get("keyword") or "")
    topic.research_focus = str(payload.get("research_focus") or "")
    topic.perspective = str(payload.get("perspective") or "all")
    topic.region_filter = str(payload.get("region_filter") or "")
    topic.industry_filter = str(payload.get("industry_filter") or "")
    topic.notes = str(payload.get("notes") or "")
    if existing is None and payload.get("created_at"):
        topic.created_at = _normalize_datetime(payload.get("created_at"))
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return _serialize_topic(topic)


def get_tracking_topic(db: Session, topic_id: str) -> dict[str, Any] | None:
    _maybe_backfill_workspace(db)
    try:
        parsed_topic_id = uuid.UUID(str(topic_id))
    except ValueError:
        return None
    topic = db.scalar(
        select(ResearchTrackingTopic)
        .where(ResearchTrackingTopic.id == parsed_topic_id)
        .where(ResearchTrackingTopic.user_id == settings.single_user_id)
    )
    if topic is None:
        return None
    return _serialize_topic(topic)


def get_latest_tracking_topic_report_payload(db: Session, topic_id: str) -> dict[str, Any] | None:
    _maybe_backfill_workspace(db)
    try:
        parsed_topic_id = uuid.UUID(str(topic_id))
    except ValueError:
        return None
    version = db.scalar(
        select(ResearchReportVersion)
        .where(ResearchReportVersion.topic_id == parsed_topic_id)
        .order_by(desc(ResearchReportVersion.created_at))
        .limit(1)
    )
    if version is None or not isinstance(version.report_payload, dict):
        return None
    return version.report_payload


def list_tracking_topic_versions(db: Session, topic_id: str) -> list[dict[str, Any]]:
    _maybe_backfill_workspace(db)
    try:
        parsed_topic_id = uuid.UUID(str(topic_id))
    except ValueError:
        return []
    versions = db.scalars(
        select(ResearchReportVersion)
        .join(ResearchTrackingTopic, ResearchTrackingTopic.id == ResearchReportVersion.topic_id)
        .where(ResearchTrackingTopic.user_id == settings.single_user_id)
        .where(ResearchReportVersion.topic_id == parsed_topic_id)
        .order_by(desc(ResearchReportVersion.created_at))
    ).all()
    return [_serialize_version_detail(item) for item in versions]


def list_tracking_topic_timeline(db: Session, topic_id: str) -> list[dict[str, Any]]:
    _maybe_backfill_workspace(db)
    try:
        parsed_topic_id = uuid.UUID(str(topic_id))
    except ValueError:
        return []
    topic = db.scalar(
        select(ResearchTrackingTopic)
        .where(ResearchTrackingTopic.id == parsed_topic_id)
        .where(ResearchTrackingTopic.user_id == settings.single_user_id)
    )
    if topic is None:
        return []
    versions = list_tracking_topic_version_models(db, parsed_topic_id)
    snapshots = db.scalars(
        select(ResearchCompareSnapshot)
        .where(ResearchCompareSnapshot.user_id == settings.single_user_id)
        .where(ResearchCompareSnapshot.tracking_topic_id == parsed_topic_id)
        .order_by(desc(ResearchCompareSnapshot.created_at))
    ).all()
    archives = db.scalars(
        select(ResearchMarkdownArchive)
        .where(ResearchMarkdownArchive.user_id == settings.single_user_id)
        .where(ResearchMarkdownArchive.tracking_topic_id == parsed_topic_id)
        .where(ResearchMarkdownArchive.archive_kind == "archive_diff_recap")
        .order_by(desc(ResearchMarkdownArchive.created_at))
    ).all()
    events = [
        *[_serialize_version_timeline_event(item) for item in versions],
        *[_serialize_compare_snapshot_timeline_event(item) for item in snapshots],
        *[_serialize_markdown_archive_timeline_event(item) for item in archives],
    ]
    timeline_priority = {
        "report_version": 0,
        "compare_snapshot": 1,
        "markdown_archive": 2,
    }
    return sorted(
        events,
        key=lambda item: (
            _normalize_datetime(item.get("occurred_at")),
            timeline_priority.get(str(item.get("event_type") or ""), 0),
        ),
        reverse=True,
    )


def get_tracking_topic_version(db: Session, topic_id: str, version_id: str) -> dict[str, Any] | None:
    _maybe_backfill_workspace(db)
    try:
        parsed_topic_id = uuid.UUID(str(topic_id))
        parsed_version_id = uuid.UUID(str(version_id))
    except ValueError:
        return None
    version = db.scalar(
        select(ResearchReportVersion)
        .join(ResearchTrackingTopic, ResearchTrackingTopic.id == ResearchReportVersion.topic_id)
        .where(ResearchTrackingTopic.user_id == settings.single_user_id)
        .where(ResearchReportVersion.topic_id == parsed_topic_id)
        .where(ResearchReportVersion.id == parsed_version_id)
    )
    if version is None:
        return None
    return _serialize_version_detail(version)


def mark_tracking_topic_refreshed(
    db: Session,
    topic_id: str,
    *,
    last_refreshed_at: str | datetime,
    last_report_entry_id: str | None,
    last_report_title: str | None,
    source_count: int = 0,
    evidence_density: str = "low",
    source_quality: str = "low",
    last_refresh_note: str | None = None,
    last_refresh_new_targets: list[str] | None = None,
    last_refresh_new_competitors: list[str] | None = None,
    last_refresh_new_budget_signals: list[str] | None = None,
    report_payload: dict[str, Any] | None = None,
    action_cards_payload: list[dict[str, Any]] | None = None,
) -> dict[str, Any] | None:
    _maybe_backfill_workspace(db)
    try:
        parsed_topic_id = uuid.UUID(str(topic_id))
    except ValueError:
        return None
    topic = db.scalar(
        select(ResearchTrackingTopic)
        .where(ResearchTrackingTopic.id == parsed_topic_id)
        .where(ResearchTrackingTopic.user_id == settings.single_user_id)
    )
    if topic is None:
        return None

    entry_uuid: uuid.UUID | None = None
    if last_report_entry_id:
        try:
            entry_uuid = uuid.UUID(str(last_report_entry_id))
        except ValueError:
            entry_uuid = None
    version = ResearchReportVersion(
        topic_id=topic.id,
        knowledge_entry_id=entry_uuid,
        report_title=str(last_report_title or "未命名研报"),
        report_payload=report_payload or {},
        action_cards_payload=action_cards_payload or [],
        source_count=int(source_count or 0),
        evidence_density=str(evidence_density or "low"),
        source_quality=str(source_quality or "low"),
        refresh_note=str(last_refresh_note or "") or None,
        new_targets=list(last_refresh_new_targets or []),
        new_competitors=list(last_refresh_new_competitors or []),
        new_budget_signals=list(last_refresh_new_budget_signals or []),
        created_at=_normalize_datetime(last_refreshed_at),
    )
    db.add(version)
    db.flush()

    topic.last_refreshed_at = _normalize_datetime(last_refreshed_at)
    topic.last_refresh_status = "succeeded"
    topic.last_refresh_error = None
    topic.last_refresh_note = str(last_refresh_note or "")
    topic.last_refresh_new_targets = list(last_refresh_new_targets or [])
    topic.last_refresh_new_competitors = list(last_refresh_new_competitors or [])
    topic.last_refresh_new_budget_signals = list(last_refresh_new_budget_signals or [])
    topic.last_report_version_id = version.id
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return _serialize_topic(topic, versions=list_tracking_topic_version_models(db, topic.id))


def mark_tracking_topic_refresh_started(db: Session, topic_id: str, *, note: str | None = None) -> dict[str, Any] | None:
    _maybe_backfill_workspace(db)
    try:
        parsed_topic_id = uuid.UUID(str(topic_id))
    except ValueError:
        return None
    topic = db.scalar(
        select(ResearchTrackingTopic)
        .where(ResearchTrackingTopic.id == parsed_topic_id)
        .where(ResearchTrackingTopic.user_id == settings.single_user_id)
    )
    if topic is None:
        return None
    topic.last_refresh_status = "running"
    topic.last_refresh_error = None
    topic.last_refresh_note = str(note or "")
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return _serialize_topic(topic)


def mark_tracking_topic_refresh_failed(db: Session, topic_id: str, *, error: str, note: str | None = None) -> dict[str, Any] | None:
    _maybe_backfill_workspace(db)
    try:
        parsed_topic_id = uuid.UUID(str(topic_id))
    except ValueError:
        return None
    topic = db.scalar(
        select(ResearchTrackingTopic)
        .where(ResearchTrackingTopic.id == parsed_topic_id)
        .where(ResearchTrackingTopic.user_id == settings.single_user_id)
    )
    if topic is None:
        return None
    topic.last_refresh_status = "failed"
    topic.last_refresh_error = str(error or "")
    topic.last_refresh_note = str(note or "")
    db.add(topic)
    db.commit()
    db.refresh(topic)
    return _serialize_topic(topic)


def delete_tracking_topic(db: Session, topic_id: str) -> bool:
    _maybe_backfill_workspace(db)
    try:
        parsed_topic_id = uuid.UUID(str(topic_id))
    except ValueError:
        return False
    topic = db.scalar(
        select(ResearchTrackingTopic)
        .where(ResearchTrackingTopic.id == parsed_topic_id)
        .where(ResearchTrackingTopic.user_id == settings.single_user_id)
    )
    if topic is None:
        return False
    version_ids = [item.id for item in list_tracking_topic_version_models(db, topic.id)]
    snapshot_ids = [
        item.id
        for item in db.scalars(
            select(ResearchCompareSnapshot)
            .where(ResearchCompareSnapshot.user_id == settings.single_user_id)
            .where(ResearchCompareSnapshot.tracking_topic_id == topic.id)
        ).all()
    ]
    linked_archives = db.scalars(
        select(ResearchMarkdownArchive)
        .where(ResearchMarkdownArchive.user_id == settings.single_user_id)
        .where(
            (ResearchMarkdownArchive.tracking_topic_id == topic.id)
            | (ResearchMarkdownArchive.report_version_id.in_(version_ids) if version_ids else false())
            | (ResearchMarkdownArchive.compare_snapshot_id.in_(snapshot_ids) if snapshot_ids else false())
        )
    ).all()
    for archive in linked_archives:
        if archive.tracking_topic_id == topic.id:
            archive.tracking_topic_id = None
        if archive.report_version_id in version_ids:
            archive.report_version_id = None
        if archive.compare_snapshot_id in snapshot_ids:
            archive.compare_snapshot_id = None
        db.add(archive)
    db.delete(topic)
    db.commit()
    return True


def list_tracking_topic_version_models(db: Session, topic_id: uuid.UUID) -> list[ResearchReportVersion]:
    return db.scalars(
        select(ResearchReportVersion)
        .where(ResearchReportVersion.topic_id == topic_id)
        .order_by(desc(ResearchReportVersion.created_at))
    ).all()
