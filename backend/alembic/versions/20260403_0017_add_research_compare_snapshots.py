"""add research compare snapshots

Revision ID: 20260403_0017
Revises: 20260328_0016
Create Date: 2026-04-03 04:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260403_0017"
down_revision = "20260328_0016"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_compare_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tracking_topic_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("query", sa.String(length=120), server_default="", nullable=False),
        sa.Column("region_filter", sa.String(length=40), server_default="", nullable=False),
        sa.Column("industry_filter", sa.String(length=40), server_default="", nullable=False),
        sa.Column("role_filter", sa.String(length=20), server_default="all", nullable=False),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("rows_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tracking_topic_id"], ["research_tracking_topics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_research_compare_snapshots_user_updated_at",
        "research_compare_snapshots",
        ["user_id", "updated_at"],
    )
    op.create_index(
        "idx_research_compare_snapshots_topic_id",
        "research_compare_snapshots",
        ["tracking_topic_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_research_compare_snapshots_topic_id", table_name="research_compare_snapshots")
    op.drop_index("idx_research_compare_snapshots_user_updated_at", table_name="research_compare_snapshots")
    op.drop_table("research_compare_snapshots")
