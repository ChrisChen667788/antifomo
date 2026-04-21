from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Index, Integer, String, Text, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class CollectorIngestAttempt(Base):
    __tablename__ = "collector_ingest_attempts"
    __table_args__ = (
        Index("idx_collector_ingest_attempts_item_created_at", "item_id", "created_at"),
        Index("idx_collector_ingest_attempts_user_created_at", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    route_type: Mapped[str] = mapped_column(String(40), nullable=False)
    resolver: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    attempt_status: Mapped[str] = mapped_column(String(30), nullable=False)
    error_code: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    error_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    body_source: Mapped[Optional[str]] = mapped_column(String(60), nullable=True)
    body_length: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SessionExportArtifact(Base):
    __tablename__ = "session_export_artifacts"
    __table_args__ = (
        Index("idx_session_export_artifacts_session_created_at", "session_id", "created_at"),
        Index("idx_session_export_artifacts_work_task_id", "work_task_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    work_task_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("work_tasks.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("focus_sessions.id", ondelete="SET NULL"), nullable=True
    )
    artifact_type: Mapped[str] = mapped_column(String(40), nullable=False)
    markdown: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class SessionExportItem(Base):
    __tablename__ = "session_export_items"
    __table_args__ = (
        Index("idx_session_export_items_artifact_position", "artifact_id", "position"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("session_export_artifacts.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("items.id", ondelete="SET NULL"), nullable=True
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    included_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    title_snapshot: Mapped[str] = mapped_column(Text, nullable=False)
    source_url_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class OutputTemplate(Base):
    __tablename__ = "output_templates"
    __table_args__ = (
        Index("idx_output_templates_user_template", "user_id", "template_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    template_key: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(160), nullable=False, default="", server_default="")
    config_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class DailyBriefSnapshot(Base):
    __tablename__ = "daily_brief_snapshots"
    __table_args__ = (
        Index("idx_daily_brief_snapshots_user_date", "user_id", "brief_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    brief_date: Mapped[str] = mapped_column(String(10), nullable=False)
    items_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    audio_status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending", server_default="pending")
    audio_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audio_script: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
