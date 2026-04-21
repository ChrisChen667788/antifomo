"""add research conversations and daily briefs

Revision ID: 20260328_0016
Revises: 20260328_0015
Create Date: 2026-03-28 23:55:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260328_0016"
down_revision = "20260328_0015"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_jobs",
        sa.Column("timeline_payload", sa.JSON(), nullable=False, server_default="[]"),
    )

    op.create_table(
        "research_conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=True),
        sa.Column("job_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=160), server_default="", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("context_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["research_jobs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["topic_id"], ["research_tracking_topics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_research_conversations_user_updated_at",
        "research_conversations",
        ["user_id", "updated_at"],
    )
    op.create_index("idx_research_conversations_topic_id", "research_conversations", ["topic_id"])
    op.create_index("idx_research_conversations_job_id", "research_conversations", ["job_id"])

    op.create_table(
        "research_messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("message_type", sa.String(length=30), server_default="text", nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["conversation_id"], ["research_conversations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_research_messages_conversation_created_at",
        "research_messages",
        ["conversation_id", "created_at"],
    )

    op.create_table(
        "output_templates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("template_key", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=160), server_default="", nullable=False),
        sa.Column("config_payload", sa.JSON(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_output_templates_user_template", "output_templates", ["user_id", "template_key"])

    op.create_table(
        "daily_brief_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("brief_date", sa.String(length=10), nullable=False),
        sa.Column("items_payload", sa.JSON(), nullable=False),
        sa.Column("audio_status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("audio_url", sa.Text(), nullable=True),
        sa.Column("audio_script", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_daily_brief_snapshots_user_date",
        "daily_brief_snapshots",
        ["user_id", "brief_date"],
    )


def downgrade() -> None:
    op.drop_index("idx_daily_brief_snapshots_user_date", table_name="daily_brief_snapshots")
    op.drop_table("daily_brief_snapshots")
    op.drop_index("idx_output_templates_user_template", table_name="output_templates")
    op.drop_table("output_templates")
    op.drop_index("idx_research_messages_conversation_created_at", table_name="research_messages")
    op.drop_table("research_messages")
    op.drop_index("idx_research_conversations_job_id", table_name="research_conversations")
    op.drop_index("idx_research_conversations_topic_id", table_name="research_conversations")
    op.drop_index("idx_research_conversations_user_updated_at", table_name="research_conversations")
    op.drop_table("research_conversations")
    op.drop_column("research_jobs", "timeline_payload")
