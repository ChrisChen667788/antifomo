"""init anti-fomo schema

Revision ID: 20260316_0001
Revises:
Create Date: 2026-03-16 08:00:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260316_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_users"),
    )

    op.create_table(
        "items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_domain", sa.String(length=255), nullable=True),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("raw_content", sa.Text(), nullable=True),
        sa.Column("clean_content", sa.Text(), nullable=True),
        sa.Column("short_summary", sa.Text(), nullable=True),
        sa.Column("long_summary", sa.Text(), nullable=True),
        sa.Column("score_value", sa.Numeric(precision=3, scale=2), nullable=True),
        sa.Column("action_suggestion", sa.String(length=20), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_items_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_items"),
    )
    op.create_index("idx_items_user_id", "items", ["user_id"], unique=False)
    op.create_index("idx_items_status", "items", ["status"], unique=False)
    op.execute("CREATE INDEX idx_items_created_at ON items (created_at DESC)")
    op.create_index("idx_items_source_domain", "items", ["source_domain"], unique=False)

    op.create_table(
        "item_tags",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_name", sa.String(length=100), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], name="fk_item_tags_item_id_items", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_item_tags"),
    )
    op.create_index("idx_item_tags_item_id", "item_tags", ["item_id"], unique=False)
    op.create_index("idx_item_tags_tag_name", "item_tags", ["tag_name"], unique=False)

    op.create_table(
        "feedbacks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("feedback_type", sa.String(length=30), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], name="fk_feedbacks_item_id_items", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_feedbacks_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_feedbacks"),
    )
    op.create_index("idx_feedbacks_user_id", "feedbacks", ["user_id"], unique=False)
    op.create_index("idx_feedbacks_item_id", "feedbacks", ["item_id"], unique=False)
    op.create_index("idx_feedbacks_type", "feedbacks", ["feedback_type"], unique=False)
    op.execute("CREATE INDEX idx_feedbacks_created_at ON feedbacks (created_at DESC)")

    op.create_table(
        "focus_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("goal_text", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'running'"), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_focus_sessions_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_focus_sessions"),
    )
    op.create_index("idx_focus_sessions_user_id", "focus_sessions", ["user_id"], unique=False)
    op.create_index("idx_focus_sessions_status", "focus_sessions", ["status"], unique=False)
    op.execute("CREATE INDEX idx_focus_sessions_start_time ON focus_sessions (start_time DESC)")

    op.create_table(
        "session_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
            name="fk_session_items_item_id_items",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["focus_sessions.id"],
            name="fk_session_items_session_id_focus_sessions",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_session_items"),
    )
    op.create_index("idx_session_items_session_id", "session_items", ["session_id"], unique=False)
    op.create_index("idx_session_items_item_id", "session_items", ["item_id"], unique=False)

    op.create_table(
        "work_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("task_type", sa.String(length=50), nullable=False),
        sa.Column("input_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("output_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("status", sa.String(length=20), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["session_id"], ["focus_sessions.id"], name="fk_work_tasks_session_id_focus_sessions", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_work_tasks_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_work_tasks"),
    )
    op.create_index("idx_work_tasks_user_id", "work_tasks", ["user_id"], unique=False)
    op.create_index("idx_work_tasks_session_id", "work_tasks", ["session_id"], unique=False)
    op.create_index("idx_work_tasks_status", "work_tasks", ["status"], unique=False)
    op.execute("CREATE INDEX idx_work_tasks_created_at ON work_tasks (created_at DESC)")

    op.create_table(
        "topic_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tag_name", sa.String(length=100), nullable=False),
        sa.Column("preference_score", sa.Numeric(precision=6, scale=3), server_default=sa.text("0"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_topic_preferences_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_topic_preferences"),
        sa.UniqueConstraint("user_id", "tag_name", name="uq_topic_preferences_user_tag"),
    )

    op.create_table(
        "source_preferences",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_domain", sa.String(length=255), nullable=False),
        sa.Column("preference_score", sa.Numeric(precision=6, scale=3), server_default=sa.text("0"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_source_preferences_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_source_preferences"),
        sa.UniqueConstraint("user_id", "source_domain", name="uq_source_preferences_user_domain"),
    )


def downgrade() -> None:
    op.drop_table("source_preferences")
    op.drop_table("topic_preferences")
    op.drop_table("work_tasks")
    op.drop_table("session_items")
    op.drop_table("focus_sessions")
    op.drop_table("feedbacks")
    op.drop_table("item_tags")
    op.drop_table("items")
    op.drop_table("users")

