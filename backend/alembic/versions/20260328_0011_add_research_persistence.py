"""add research persistence tables

Revision ID: 20260328_0011
Revises: 20260320_0010
Create Date: 2026-03-28 12:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260328_0011"
down_revision = "20260320_0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_saved_views",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("query", sa.String(length=120), server_default=sa.text("''"), nullable=False),
        sa.Column("filter_mode", sa.String(length=20), server_default=sa.text("'all'"), nullable=False),
        sa.Column("perspective", sa.String(length=30), server_default=sa.text("'all'"), nullable=False),
        sa.Column("region_filter", sa.String(length=40), server_default=sa.text("''"), nullable=False),
        sa.Column("industry_filter", sa.String(length=40), server_default=sa.text("''"), nullable=False),
        sa.Column("action_type_filter", sa.String(length=40), server_default=sa.text("''"), nullable=False),
        sa.Column("focus_only", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_research_saved_views_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_research_saved_views"),
    )
    op.create_index(
        "idx_research_saved_views_user_updated_at",
        "research_saved_views",
        ["user_id", "updated_at"],
        unique=False,
    )

    op.create_table(
        "research_tracking_topics",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("keyword", sa.String(length=120), nullable=False),
        sa.Column("research_focus", sa.String(length=280), server_default=sa.text("''"), nullable=False),
        sa.Column("perspective", sa.String(length=30), server_default=sa.text("'all'"), nullable=False),
        sa.Column("region_filter", sa.String(length=40), server_default=sa.text("''"), nullable=False),
        sa.Column("industry_filter", sa.String(length=40), server_default=sa.text("''"), nullable=False),
        sa.Column("notes", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("last_refreshed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_refresh_status", sa.String(length=20), server_default=sa.text("'idle'"), nullable=False),
        sa.Column("last_refresh_error", sa.Text(), nullable=True),
        sa.Column("last_refresh_note", sa.Text(), nullable=True),
        sa.Column("last_refresh_new_targets", sa.JSON(), nullable=False),
        sa.Column("last_refresh_new_competitors", sa.JSON(), nullable=False),
        sa.Column("last_refresh_new_budget_signals", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_research_tracking_topics_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_research_tracking_topics"),
    )
    op.create_index(
        "idx_research_tracking_topics_user_updated_at",
        "research_tracking_topics",
        ["user_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "idx_research_tracking_topics_last_refreshed_at",
        "research_tracking_topics",
        ["last_refreshed_at"],
        unique=False,
    )

    op.create_table(
        "research_report_versions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("knowledge_entry_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("report_title", sa.Text(), nullable=False),
        sa.Column("report_payload", sa.JSON(), nullable=False),
        sa.Column("action_cards_payload", sa.JSON(), nullable=False),
        sa.Column("source_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("evidence_density", sa.String(length=20), server_default=sa.text("'low'"), nullable=False),
        sa.Column("source_quality", sa.String(length=20), server_default=sa.text("'low'"), nullable=False),
        sa.Column("refresh_note", sa.Text(), nullable=True),
        sa.Column("new_targets", sa.JSON(), nullable=False),
        sa.Column("new_competitors", sa.JSON(), nullable=False),
        sa.Column("new_budget_signals", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["knowledge_entry_id"],
            ["knowledge_entries.id"],
            name="fk_research_report_versions_knowledge_entry_id_knowledge_entries",
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["topic_id"],
            ["research_tracking_topics.id"],
            name="fk_research_report_versions_topic_id_research_tracking_topics",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_research_report_versions"),
    )
    op.create_index(
        "idx_research_report_versions_topic_created_at",
        "research_report_versions",
        ["topic_id", "created_at"],
        unique=False,
    )

    op.add_column(
        "research_tracking_topics",
        sa.Column("last_report_version_id", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_research_tracking_topics_last_report_version_id_research_report_versions",
        "research_tracking_topics",
        "research_report_versions",
        ["last_report_version_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "research_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("keyword", sa.String(length=120), nullable=False),
        sa.Column("research_focus", sa.String(length=280), nullable=True),
        sa.Column("output_language", sa.String(length=10), server_default=sa.text("'zh-CN'"), nullable=False),
        sa.Column("include_wechat", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("research_mode", sa.String(length=20), server_default=sa.text("'deep'"), nullable=False),
        sa.Column("max_sources", sa.Integer(), server_default=sa.text("14"), nullable=False),
        sa.Column("deep_research", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("progress_percent", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("stage_key", sa.String(length=40), server_default=sa.text("'queued'"), nullable=False),
        sa.Column("stage_label", sa.String(length=120), server_default=sa.text("''"), nullable=False),
        sa.Column("message", sa.Text(), server_default=sa.text("''"), nullable=False),
        sa.Column("estimated_seconds", sa.Integer(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("report_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["topic_id"], ["research_tracking_topics.id"], name="fk_research_jobs_topic_id_research_tracking_topics", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_research_jobs_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_research_jobs"),
    )
    op.create_index("idx_research_jobs_user_created_at", "research_jobs", ["user_id", "created_at"], unique=False)
    op.create_index("idx_research_jobs_status", "research_jobs", ["status"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_research_jobs_status", table_name="research_jobs")
    op.drop_index("idx_research_jobs_user_created_at", table_name="research_jobs")
    op.drop_table("research_jobs")

    op.drop_constraint(
        "fk_research_tracking_topics_last_report_version_id_research_report_versions",
        "research_tracking_topics",
        type_="foreignkey",
    )
    op.drop_column("research_tracking_topics", "last_report_version_id")

    op.drop_index("idx_research_report_versions_topic_created_at", table_name="research_report_versions")
    op.drop_table("research_report_versions")

    op.drop_index("idx_research_tracking_topics_last_refreshed_at", table_name="research_tracking_topics")
    op.drop_index("idx_research_tracking_topics_user_updated_at", table_name="research_tracking_topics")
    op.drop_table("research_tracking_topics")

    op.drop_index("idx_research_saved_views_user_updated_at", table_name="research_saved_views")
    op.drop_table("research_saved_views")
