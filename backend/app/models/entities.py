from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    Boolean,
    JSON,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    items: Mapped[list[Item]] = relationship(back_populates="user", cascade="all, delete-orphan")
    feedbacks: Mapped[list[Feedback]] = relationship(back_populates="user", cascade="all, delete-orphan")
    focus_sessions: Mapped[list[FocusSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    work_tasks: Mapped[list[WorkTask]] = relationship(back_populates="user", cascade="all, delete-orphan")
    topic_preferences: Mapped[list[TopicPreference]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    source_preferences: Mapped[list[SourcePreference]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    preference_snapshots: Mapped[list[PreferenceSnapshot]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    collector_sources: Mapped[list[CollectorSource]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    knowledge_entries: Mapped[list[KnowledgeEntry]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    knowledge_rule: Mapped[Optional[KnowledgeRule]] = relationship(
        back_populates="user", cascade="all, delete-orphan", uselist=False
    )


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        Index("idx_items_user_id", "user_id"),
        Index("idx_items_status", "status"),
        Index("idx_items_created_at", "created_at"),
        Index("idx_items_source_domain", "source_domain"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)  # url / text / plugin
    source_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    source_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    clean_content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    short_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    long_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    score_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(3, 2), nullable=True)
    action_suggestion: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)  # skip / later / deep_read
    output_language: Mapped[str] = mapped_column(
        String(10), nullable=False, default="zh-CN", server_default="zh-CN"
    )
    ingest_route: Mapped[Optional[str]] = mapped_column(String(40), nullable=True)
    content_acquisition_status: Mapped[str] = mapped_column(
        String(30), nullable=False, default="pending", server_default="pending"
    )
    content_acquisition_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_from_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    fallback_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    processing_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    processing_started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    processing_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="items")
    tags: Mapped[list[ItemTag]] = relationship(back_populates="item", cascade="all, delete-orphan")
    feedbacks: Mapped[list[Feedback]] = relationship(back_populates="item", cascade="all, delete-orphan")
    sessions: Mapped[list[SessionItem]] = relationship(back_populates="item", cascade="all, delete-orphan")
    knowledge_entries: Mapped[list[KnowledgeEntry]] = relationship(
        back_populates="item", cascade="all, delete-orphan"
    )


class ItemTag(Base):
    __tablename__ = "item_tags"
    __table_args__ = (
        Index("idx_item_tags_item_id", "item_id"),
        Index("idx_item_tags_tag_name", "tag_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    tag_name: Mapped[str] = mapped_column(String(100), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    item: Mapped[Item] = relationship(back_populates="tags")


class Feedback(Base):
    __tablename__ = "feedbacks"
    __table_args__ = (
        Index("idx_feedbacks_user_id", "user_id"),
        Index("idx_feedbacks_item_id", "item_id"),
        Index("idx_feedbacks_type", "feedback_type"),
        Index("idx_feedbacks_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    feedback_type: Mapped[str] = mapped_column(String(30), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="feedbacks")
    item: Mapped[Item] = relationship(back_populates="feedbacks")


class FocusSession(Base):
    __tablename__ = "focus_sessions"
    __table_args__ = (
        Index("idx_focus_sessions_user_id", "user_id"),
        Index("idx_focus_sessions_status", "status"),
        Index("idx_focus_sessions_start_time", "start_time"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    goal_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    output_language: Mapped[str] = mapped_column(
        String(10), nullable=False, default="zh-CN", server_default="zh-CN"
    )
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="running", server_default="running")
    summary_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="focus_sessions")
    session_items: Mapped[list[SessionItem]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )
    work_tasks: Mapped[list[WorkTask]] = relationship(back_populates="session")


class SessionItem(Base):
    __tablename__ = "session_items"
    __table_args__ = (
        Index("idx_session_items_session_id", "session_id"),
        Index("idx_session_items_item_id", "item_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    session_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("focus_sessions.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("items.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    session: Mapped[FocusSession] = relationship(back_populates="session_items")
    item: Mapped[Item] = relationship(back_populates="sessions")


class WorkTask(Base):
    __tablename__ = "work_tasks"
    __table_args__ = (
        Index("idx_work_tasks_user_id", "user_id"),
        Index("idx_work_tasks_session_id", "session_id"),
        Index("idx_work_tasks_status", "status"),
        Index("idx_work_tasks_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    session_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("focus_sessions.id", ondelete="SET NULL"), nullable=True
    )
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    input_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending", server_default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[User] = relationship(back_populates="work_tasks")
    session: Mapped[Optional[FocusSession]] = relationship(back_populates="work_tasks")


class TopicPreference(Base):
    __tablename__ = "topic_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "tag_name", name="uq_topic_preferences_user_tag"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tag_name: Mapped[str] = mapped_column(String(100), nullable=False)
    preference_score: Mapped[Decimal] = mapped_column(
        Numeric(6, 3), nullable=False, default=Decimal("0"), server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="topic_preferences")


class SourcePreference(Base):
    __tablename__ = "source_preferences"
    __table_args__ = (
        UniqueConstraint("user_id", "source_domain", name="uq_source_preferences_user_domain"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    preference_score: Mapped[Decimal] = mapped_column(
        Numeric(6, 3), nullable=False, default=Decimal("0"), server_default="0"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="source_preferences")


class PreferenceSnapshot(Base):
    __tablename__ = "preference_snapshots"
    __table_args__ = (
        Index("idx_preference_snapshots_user_id", "user_id"),
        Index("idx_preference_snapshots_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    top_tags: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    top_domains: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    snapshot_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="preference_snapshots")


class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"
    __table_args__ = (
        Index("idx_knowledge_entries_user_id", "user_id"),
        Index("idx_knowledge_entries_item_id", "item_id"),
        Index("idx_knowledge_entries_created_at", "created_at"),
        Index("idx_knowledge_entries_pinned", "user_id", "is_pinned"),
        Index("idx_knowledge_entries_focus_reference", "user_id", "is_focus_reference"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    item_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("items.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    metadata_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    collection_name: Mapped[Optional[str]] = mapped_column(String(80), nullable=True)
    is_pinned: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    is_focus_reference: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="knowledge_entries")
    item: Mapped[Optional[Item]] = relationship(back_populates="knowledge_entries")


class KnowledgeRule(Base):
    __tablename__ = "knowledge_rules"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_knowledge_rules_user_id"),
        Index("idx_knowledge_rules_user_id", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    min_score_value: Mapped[Decimal] = mapped_column(
        Numeric(3, 2), nullable=False, default=Decimal("4.00"), server_default="4.00"
    )
    archive_on_like: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    archive_on_save: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="knowledge_rule")


class CollectorSource(Base):
    __tablename__ = "collector_sources"
    __table_args__ = (
        UniqueConstraint("user_id", "source_url", name="uq_collector_sources_user_url"),
        Index("idx_collector_sources_user_id", "user_id"),
        Index("idx_collector_sources_enabled", "enabled"),
        Index("idx_collector_sources_updated_at", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_domain: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="1"
    )
    last_collected_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="collector_sources")
