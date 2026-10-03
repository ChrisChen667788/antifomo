from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.types import CompatibleUuid as Uuid
from app.db.base import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class CollectorSourceItem(Base):
    """Stable connector-native identity; Item remains the mutable UI projection."""

    __tablename__ = "collector_source_items"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "connector",
            "account_scope",
            "native_item_id",
            name="uq_collector_source_items_native_identity",
        ),
        Index("idx_collector_source_items_user_seen", "user_id", "last_seen_at"),
        Index("idx_collector_source_items_item", "item_id"),
        Index("idx_collector_source_items_state", "state"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=True
    )
    connector: Mapped[str] = mapped_column(String(80), nullable=False)
    account_scope: Mapped[str] = mapped_column(String(160), nullable=False, default="local", server_default="local")
    native_item_id: Mapped[str] = mapped_column(String(512), nullable=False)
    native_version: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    canonical_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="active", server_default="active")
    current_revision_key: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    metadata_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    tombstoned_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    revisions: Mapped[list["CollectorDocumentRevision"]] = relationship(
        back_populates="source_item", cascade="all, delete-orphan"
    )


class CollectorRawAsset(Base):
    __tablename__ = "collector_raw_assets"
    __table_args__ = (
        UniqueConstraint("user_id", "sha256", name="uq_collector_raw_assets_user_sha256"),
        Index("idx_collector_raw_assets_user_created", "user_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime_type: Mapped[str] = mapped_column(
        String(120), nullable=False, default="text/plain", server_default="text/plain"
    )
    byte_size: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_uri: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    metadata_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class CollectorDocumentRevision(Base):
    __tablename__ = "collector_document_revisions"
    __table_args__ = (
        UniqueConstraint("source_item_id", "revision_key", name="uq_collector_document_revisions_key"),
        Index("idx_collector_document_revisions_source_created", "source_item_id", "created_at"),
        Index("idx_collector_document_revisions_item", "item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    source_item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("collector_source_items.id", ondelete="CASCADE"), nullable=False
    )
    raw_asset_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("collector_raw_assets.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=True
    )
    revision_key: Mapped[str] = mapped_column(String(64), nullable=False)
    native_version: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    normalized_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    parser_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    parse_status: Mapped[str] = mapped_column(String(30), nullable=False, default="captured", server_default="captured")
    diagnostics_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    source_item: Mapped[CollectorSourceItem] = relationship(back_populates="revisions")
    raw_asset: Mapped[CollectorRawAsset] = relationship()
    spans: Mapped[list["CollectorSourceSpan"]] = relationship(
        back_populates="revision", cascade="all, delete-orphan"
    )


class CollectorSourceSpan(Base):
    __tablename__ = "collector_source_spans"
    __table_args__ = (
        UniqueConstraint("revision_id", "span_key", name="uq_collector_source_spans_key"),
        Index("idx_collector_source_spans_revision", "revision_id"),
        Index("idx_collector_source_spans_text_sha", "text_sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    revision_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("collector_document_revisions.id", ondelete="CASCADE"), nullable=False
    )
    span_key: Mapped[str] = mapped_column(String(160), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False, default="text", server_default="text")
    text: Mapped[str] = mapped_column(Text, nullable=False)
    text_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    page_no: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    bbox_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    dom_selector: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    char_start: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    char_end: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    metadata_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    revision: Mapped[CollectorDocumentRevision] = relationship(back_populates="spans")


class CollectorTransformReceipt(Base):
    __tablename__ = "collector_transform_receipts"
    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "revision_id",
            "stage",
            "input_hash",
            "stage_fingerprint",
            "output_hash",
            name="uq_collector_transform_receipts_run",
        ),
        Index("idx_collector_transform_receipts_revision", "revision_id"),
        Index("idx_collector_transform_receipts_item", "item_id"),
        Index("idx_collector_transform_receipts_stage_status", "stage", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    revision_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("collector_document_revisions.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    stage: Mapped[str] = mapped_column(String(80), nullable=False)
    input_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    stage_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    output_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    provider: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    prompt_name: Mapped[Optional[str]] = mapped_column(String(160), nullable=True)
    schema_fingerprint: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    usage_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    diagnostics_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict, server_default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
