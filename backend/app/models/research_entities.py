from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


def new_uuid() -> uuid.UUID:
    return uuid.uuid4()


class ResearchSavedView(Base):
    __tablename__ = "research_saved_views"
    __table_args__ = (
        Index("idx_research_saved_views_user_updated_at", "user_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    query: Mapped[str] = mapped_column(String(120), nullable=False, default="", server_default="")
    filter_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="all", server_default="all")
    perspective: Mapped[str] = mapped_column(String(30), nullable=False, default="all", server_default="all")
    region_filter: Mapped[str] = mapped_column(String(40), nullable=False, default="", server_default="")
    industry_filter: Mapped[str] = mapped_column(String(40), nullable=False, default="", server_default="")
    action_type_filter: Mapped[str] = mapped_column(String(40), nullable=False, default="", server_default="")
    focus_only: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ResearchTrackingTopic(Base):
    __tablename__ = "research_tracking_topics"
    __table_args__ = (
        Index("idx_research_tracking_topics_user_updated_at", "user_id", "updated_at"),
        Index("idx_research_tracking_topics_last_refreshed_at", "last_refreshed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    keyword: Mapped[str] = mapped_column(String(120), nullable=False)
    research_focus: Mapped[str] = mapped_column(String(280), nullable=False, default="", server_default="")
    perspective: Mapped[str] = mapped_column(String(30), nullable=False, default="all", server_default="all")
    region_filter: Mapped[str] = mapped_column(String(40), nullable=False, default="", server_default="")
    industry_filter: Mapped[str] = mapped_column(String(40), nullable=False, default="", server_default="")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    last_refreshed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    last_refresh_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="idle", server_default="idle"
    )
    last_refresh_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_refresh_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_refresh_new_targets: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    last_refresh_new_competitors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    last_refresh_new_budget_signals: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    last_report_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_report_versions.id", ondelete="SET NULL"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    report_versions: Mapped[list["ResearchReportVersion"]] = relationship(
        back_populates="topic",
        cascade="all, delete-orphan",
        foreign_keys="ResearchReportVersion.topic_id",
    )
    last_report_version: Mapped[Optional["ResearchReportVersion"]] = relationship(
        foreign_keys=[last_report_version_id],
        post_update=True,
    )


class ResearchReportVersion(Base):
    __tablename__ = "research_report_versions"
    __table_args__ = (
        Index("idx_research_report_versions_topic_created_at", "topic_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_tracking_topics.id", ondelete="CASCADE"),
        nullable=False,
    )
    knowledge_entry_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("knowledge_entries.id", ondelete="SET NULL"),
        nullable=True,
    )
    report_title: Mapped[str] = mapped_column(Text, nullable=False)
    report_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    action_cards_payload: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    evidence_density: Mapped[str] = mapped_column(String(20), nullable=False, default="low", server_default="low")
    source_quality: Mapped[str] = mapped_column(String(20), nullable=False, default="low", server_default="low")
    refresh_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    new_targets: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    new_competitors: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    new_budget_signals: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    topic: Mapped["ResearchTrackingTopic"] = relationship(
        back_populates="report_versions",
        foreign_keys=[topic_id],
    )


class ResearchWatchlist(Base):
    __tablename__ = "research_watchlists"
    __table_args__ = (
        Index("idx_research_watchlists_user_updated_at", "user_id", "updated_at"),
        Index("idx_research_watchlists_tracking_topic_id", "tracking_topic_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tracking_topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_tracking_topics.id", ondelete="SET NULL"),
        nullable=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    watch_type: Mapped[str] = mapped_column(String(30), nullable=False, default="topic", server_default="topic")
    query: Mapped[str] = mapped_column(String(120), nullable=False, default="", server_default="")
    region_filter: Mapped[str] = mapped_column(String(40), nullable=False, default="", server_default="")
    industry_filter: Mapped[str] = mapped_column(String(40), nullable=False, default="", server_default="")
    alert_level: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", server_default="medium")
    schedule: Mapped[str] = mapped_column(String(30), nullable=False, default="manual", server_default="manual")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    last_checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    tracking_topic: Mapped[Optional["ResearchTrackingTopic"]] = relationship(
        foreign_keys=[tracking_topic_id]
    )
    change_events: Mapped[list["ResearchWatchlistChangeEvent"]] = relationship(
        back_populates="watchlist",
        cascade="all, delete-orphan",
    )


class ResearchWatchlistChangeEvent(Base):
    __tablename__ = "research_watchlist_change_events"
    __table_args__ = (
        Index("idx_research_watchlist_change_events_watchlist_created", "watchlist_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_watchlists.id", ondelete="CASCADE"),
        nullable=False,
    )
    change_type: Mapped[str] = mapped_column(String(20), nullable=False, default="rewritten", server_default="rewritten")
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    severity: Mapped[str] = mapped_column(String(20), nullable=False, default="medium", server_default="medium")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    watchlist: Mapped["ResearchWatchlist"] = relationship(back_populates="change_events")


class ResearchCanonicalEntity(Base):
    __tablename__ = "research_canonical_entities"
    __table_args__ = (
        UniqueConstraint("user_id", "canonical_name", "entity_type", name="uq_research_entity_user_name_type"),
        Index("idx_research_entities_user_updated_at", "user_id", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    canonical_name: Mapped[str] = mapped_column(String(160), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(20), nullable=False, default="generic", server_default="generic")
    region_hint: Mapped[str] = mapped_column(String(80), nullable=False, default="", server_default="")
    industry_hint: Mapped[str] = mapped_column(String(80), nullable=False, default="", server_default="")
    profile_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    last_seen_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )

    aliases: Mapped[list["ResearchEntityAlias"]] = relationship(
        back_populates="entity",
        cascade="all, delete-orphan",
    )
    outgoing_relations: Mapped[list["ResearchEntityRelation"]] = relationship(
        back_populates="from_entity",
        foreign_keys="ResearchEntityRelation.from_entity_id",
        cascade="all, delete-orphan",
    )
    incoming_relations: Mapped[list["ResearchEntityRelation"]] = relationship(
        back_populates="to_entity",
        foreign_keys="ResearchEntityRelation.to_entity_id",
        cascade="all, delete-orphan",
    )


class ResearchEntityAlias(Base):
    __tablename__ = "research_entity_aliases"
    __table_args__ = (
        UniqueConstraint("entity_id", "alias_name", name="uq_research_entity_alias"),
        Index("idx_research_entity_aliases_alias_name", "alias_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_canonical_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    alias_name: Mapped[str] = mapped_column(String(160), nullable=False)
    confidence: Mapped[int] = mapped_column(Integer, nullable=False, default=80, server_default="80")
    source_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    entity: Mapped["ResearchCanonicalEntity"] = relationship(back_populates="aliases")


class ResearchEntityRelation(Base):
    __tablename__ = "research_entity_relations"
    __table_args__ = (
        UniqueConstraint(
            "from_entity_id",
            "to_entity_id",
            "relation_type",
            name="uq_research_entity_relation_pair_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    from_entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_canonical_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    to_entity_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_canonical_entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    relation_type: Mapped[str] = mapped_column(String(30), nullable=False)
    evidence_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    weight: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    from_entity: Mapped["ResearchCanonicalEntity"] = relationship(
        back_populates="outgoing_relations",
        foreign_keys=[from_entity_id],
    )
    to_entity: Mapped["ResearchCanonicalEntity"] = relationship(
        back_populates="incoming_relations",
        foreign_keys=[to_entity_id],
    )


class ResearchJob(Base):
    __tablename__ = "research_jobs"
    __table_args__ = (
        Index("idx_research_jobs_user_created_at", "user_id", "created_at"),
        Index("idx_research_jobs_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_tracking_topics.id", ondelete="SET NULL"),
        nullable=True,
    )
    keyword: Mapped[str] = mapped_column(String(120), nullable=False)
    research_focus: Mapped[Optional[str]] = mapped_column(String(280), nullable=True)
    output_language: Mapped[str] = mapped_column(String(10), nullable=False, default="zh-CN", server_default="zh-CN")
    include_wechat: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    research_mode: Mapped[str] = mapped_column(String(20), nullable=False, default="deep", server_default="deep")
    max_sources: Mapped[int] = mapped_column(Integer, nullable=False, default=14, server_default="14")
    deep_research: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued", server_default="queued")
    progress_percent: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    stage_key: Mapped[str] = mapped_column(String(40), nullable=False, default="queued", server_default="queued")
    stage_label: Mapped[str] = mapped_column(String(120), nullable=False, default="", server_default="")
    message: Mapped[str] = mapped_column(Text, nullable=False, default="", server_default="")
    estimated_seconds: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    report_payload: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    timeline_payload: Mapped[list[dict]] = mapped_column(JSON, nullable=False, default=list)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class ResearchConversation(Base):
    __tablename__ = "research_conversations"
    __table_args__ = (
        Index("idx_research_conversations_user_updated_at", "user_id", "updated_at"),
        Index("idx_research_conversations_topic_id", "topic_id"),
        Index("idx_research_conversations_job_id", "job_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    topic_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_tracking_topics.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_jobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False, default="", server_default="")
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="active", server_default="active")
    context_payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


class ResearchMessage(Base):
    __tablename__ = "research_messages"
    __table_args__ = (
        Index("idx_research_messages_conversation_created_at", "conversation_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=new_uuid)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("research_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    message_type: Mapped[str] = mapped_column(String(30), nullable=False, default="text", server_default="text")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
