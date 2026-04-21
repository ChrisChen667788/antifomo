"""add research markdown archives

Revision ID: 20260403_0019
Revises: 20260403_0018
Create Date: 2026-04-03 18:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260403_0019"
down_revision = "20260403_0018"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_markdown_archives",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tracking_topic_id", sa.Uuid(), nullable=True),
        sa.Column("compare_snapshot_id", sa.Uuid(), nullable=True),
        sa.Column("report_version_id", sa.Uuid(), nullable=True),
        sa.Column("archive_kind", sa.String(length=40), nullable=False, server_default="compare_markdown"),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("filename", sa.String(length=180), nullable=False),
        sa.Column("query", sa.String(length=120), nullable=False, server_default=""),
        sa.Column("region_filter", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("industry_filter", sa.String(length=40), nullable=False, server_default=""),
        sa.Column("summary", sa.Text(), nullable=False, server_default=""),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("metadata_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["compare_snapshot_id"], ["research_compare_snapshots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["report_version_id"], ["research_report_versions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tracking_topic_id"], ["research_tracking_topics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_research_markdown_archives_user_updated_at",
        "research_markdown_archives",
        ["user_id", "updated_at"],
        unique=False,
    )
    op.create_index(
        "idx_research_markdown_archives_topic_id",
        "research_markdown_archives",
        ["tracking_topic_id"],
        unique=False,
    )
    op.create_index(
        "idx_research_markdown_archives_snapshot_id",
        "research_markdown_archives",
        ["compare_snapshot_id"],
        unique=False,
    )
    op.create_index(
        "idx_research_markdown_archives_report_version_id",
        "research_markdown_archives",
        ["report_version_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_research_markdown_archives_report_version_id", table_name="research_markdown_archives")
    op.drop_index("idx_research_markdown_archives_snapshot_id", table_name="research_markdown_archives")
    op.drop_index("idx_research_markdown_archives_topic_id", table_name="research_markdown_archives")
    op.drop_index("idx_research_markdown_archives_user_updated_at", table_name="research_markdown_archives")
    op.drop_table("research_markdown_archives")
