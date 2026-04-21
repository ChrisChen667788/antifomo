from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.entities import Item, WorkTask
from app.models.workflow_entities import SessionExportArtifact, SessionExportItem


def persist_session_artifact(
    db: Session,
    *,
    task: WorkTask,
    artifact_type: str,
    markdown: str,
    items: list[dict[str, Any]],
) -> SessionExportArtifact:
    artifact = SessionExportArtifact(
        work_task_id=task.id,
        session_id=task.session_id,
        artifact_type=artifact_type,
        markdown=markdown,
    )
    db.add(artifact)
    db.flush()

    for index, item in enumerate(items):
        item_id = item.get("item_id")
        parsed_item_id = None
        if item_id:
            parsed_item_id = UUID(str(item_id))
        db.add(
            SessionExportItem(
                artifact_id=artifact.id,
                item_id=parsed_item_id,
                position=index,
                included_reason=str(item.get("included_reason") or "") or None,
                title_snapshot=str(item.get("title_snapshot") or "未命名内容"),
                source_url_snapshot=str(item.get("source_url_snapshot") or "") or None,
            )
        )
    return artifact


def serialize_session_artifact(
    artifact: SessionExportArtifact,
    artifact_items: list[SessionExportItem],
) -> dict[str, Any]:
    return {
        "id": str(artifact.id),
        "work_task_id": str(artifact.work_task_id),
        "session_id": str(artifact.session_id) if artifact.session_id else None,
        "artifact_type": artifact.artifact_type,
        "markdown": artifact.markdown,
        "created_at": artifact.created_at,
        "items": [
            {
                "id": str(item.id),
                "item_id": str(item.item_id) if item.item_id else None,
                "position": item.position,
                "included_reason": item.included_reason,
                "title_snapshot": item.title_snapshot,
                "source_url_snapshot": item.source_url_snapshot,
                "created_at": item.created_at,
            }
            for item in artifact_items
        ],
    }


def list_session_artifacts(db: Session, session_id: UUID) -> list[dict[str, Any]]:
    artifacts = list(
        db.scalars(
            select(SessionExportArtifact)
            .where(SessionExportArtifact.session_id == session_id)
            .order_by(desc(SessionExportArtifact.created_at))
        )
    )
    if not artifacts:
        return []
    artifact_ids = [artifact.id for artifact in artifacts]
    artifact_items = list(
        db.scalars(
            select(SessionExportItem)
            .where(SessionExportItem.artifact_id.in_(artifact_ids))
            .order_by(SessionExportItem.position.asc())
        )
    )
    grouped: dict[UUID, list[SessionExportItem]] = {artifact.id: [] for artifact in artifacts}
    for item in artifact_items:
        grouped.setdefault(item.artifact_id, []).append(item)
    return [serialize_session_artifact(artifact, grouped.get(artifact.id, [])) for artifact in artifacts]
