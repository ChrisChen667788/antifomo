"""add collector diagnostics and session artifacts

Revision ID: 20260328_0012
Revises: 20260328_0011
Create Date: 2026-03-28 13:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "20260328_0012"
down_revision = "20260328_0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("items", sa.Column("ingest_route", sa.String(length=40), nullable=True))
    op.add_column(
        "items",
        sa.Column("content_acquisition_status", sa.String(length=30), server_default=sa.text("'pending'"), nullable=False),
    )
    op.add_column("items", sa.Column("content_acquisition_note", sa.Text(), nullable=True))
    op.add_column("items", sa.Column("resolved_from_url", sa.Text(), nullable=True))
    op.add_column(
        "items",
        sa.Column("fallback_used", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

    op.create_table(
        "collector_ingest_attempts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("route_type", sa.String(length=40), nullable=False),
        sa.Column("resolver", sa.String(length=60), nullable=True),
        sa.Column("attempt_status", sa.String(length=30), nullable=False),
        sa.Column("error_code", sa.String(length=60), nullable=True),
        sa.Column("error_detail", sa.Text(), nullable=True),
        sa.Column("body_source", sa.String(length=60), nullable=True),
        sa.Column("body_length", sa.Integer(), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], name="fk_collector_ingest_attempts_item_id_items", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_collector_ingest_attempts_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_collector_ingest_attempts"),
    )
    op.create_index(
        "idx_collector_ingest_attempts_item_created_at",
        "collector_ingest_attempts",
        ["item_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_collector_ingest_attempts_user_created_at",
        "collector_ingest_attempts",
        ["user_id", "created_at"],
        unique=False,
    )

    op.create_table(
        "session_export_artifacts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("work_task_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("session_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("artifact_type", sa.String(length=40), nullable=False),
        sa.Column("markdown", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["session_id"], ["focus_sessions.id"], name="fk_session_export_artifacts_session_id_focus_sessions", ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["work_task_id"], ["work_tasks.id"], name="fk_session_export_artifacts_work_task_id_work_tasks", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_session_export_artifacts"),
    )
    op.create_index(
        "idx_session_export_artifacts_session_created_at",
        "session_export_artifacts",
        ["session_id", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_session_export_artifacts_work_task_id",
        "session_export_artifacts",
        ["work_task_id"],
        unique=False,
    )

    op.create_table(
        "session_export_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("artifact_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("position", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("included_reason", sa.Text(), nullable=True),
        sa.Column("title_snapshot", sa.Text(), nullable=False),
        sa.Column("source_url_snapshot", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["artifact_id"], ["session_export_artifacts.id"], name="fk_session_export_items_artifact_id_session_export_artifacts", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["items.id"], name="fk_session_export_items_item_id_items", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_session_export_items"),
    )
    op.create_index(
        "idx_session_export_items_artifact_position",
        "session_export_items",
        ["artifact_id", "position"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_session_export_items_artifact_position", table_name="session_export_items")
    op.drop_table("session_export_items")

    op.drop_index("idx_session_export_artifacts_work_task_id", table_name="session_export_artifacts")
    op.drop_index("idx_session_export_artifacts_session_created_at", table_name="session_export_artifacts")
    op.drop_table("session_export_artifacts")

    op.drop_index("idx_collector_ingest_attempts_user_created_at", table_name="collector_ingest_attempts")
    op.drop_index("idx_collector_ingest_attempts_item_created_at", table_name="collector_ingest_attempts")
    op.drop_table("collector_ingest_attempts")

    op.drop_column("items", "fallback_used")
    op.drop_column("items", "resolved_from_url")
    op.drop_column("items", "content_acquisition_note")
    op.drop_column("items", "content_acquisition_status")
    op.drop_column("items", "ingest_route")
