"""add multiformat collector inputs

Revision ID: 20260328_0015
Revises: 20260328_0014
Create Date: 2026-03-28 23:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260328_0015"
down_revision = "20260328_0014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collector_feed_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("feed_type", sa.String(length=20), server_default="rss", nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=160), server_default="", nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="idle", nullable=False),
        sa.Column("last_synced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_collector_feed_sources_user_updated_at",
        "collector_feed_sources",
        ["user_id", "updated_at"],
    )
    op.create_index("idx_collector_feed_sources_feed_type", "collector_feed_sources", ["feed_type"])

    op.create_table(
        "collector_feed_entries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("feed_id", sa.Uuid(), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=True),
        sa.Column("title", sa.String(length=300), server_default="", nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dedup_key", sa.String(length=255), nullable=False),
        sa.Column("raw_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["feed_id"], ["collector_feed_sources.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_collector_feed_entries_feed_created",
        "collector_feed_entries",
        ["feed_id", "created_at"],
    )
    op.create_index("idx_collector_feed_entries_dedup_key", "collector_feed_entries", ["dedup_key"])

    op.create_table(
        "uploaded_documents",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=80), server_default="application/octet-stream", nullable=False),
        sa.Column("file_size", sa.Integer(), server_default="0", nullable=False),
        sa.Column("storage_path", sa.Text(), nullable=False),
        sa.Column("parse_status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("parse_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_uploaded_documents_user_created_at",
        "uploaded_documents",
        ["user_id", "created_at"],
    )
    op.create_index("idx_uploaded_documents_parse_status", "uploaded_documents", ["parse_status"])


def downgrade() -> None:
    op.drop_index("idx_uploaded_documents_parse_status", table_name="uploaded_documents")
    op.drop_index("idx_uploaded_documents_user_created_at", table_name="uploaded_documents")
    op.drop_table("uploaded_documents")
    op.drop_index("idx_collector_feed_entries_dedup_key", table_name="collector_feed_entries")
    op.drop_index("idx_collector_feed_entries_feed_created", table_name="collector_feed_entries")
    op.drop_table("collector_feed_entries")
    op.drop_index("idx_collector_feed_sources_feed_type", table_name="collector_feed_sources")
    op.drop_index("idx_collector_feed_sources_user_updated_at", table_name="collector_feed_sources")
    op.drop_table("collector_feed_sources")
