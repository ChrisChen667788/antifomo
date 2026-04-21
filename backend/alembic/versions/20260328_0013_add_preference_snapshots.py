"""add preference snapshots

Revision ID: 20260328_0013
Revises: 20260328_0012
Create Date: 2026-03-28 20:30:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260328_0013"
down_revision = "20260328_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "preference_snapshots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("top_tags", sa.JSON(), nullable=False),
        sa.Column("top_domains", sa.JSON(), nullable=False),
        sa.Column("snapshot_payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_preference_snapshots_user_id", "preference_snapshots", ["user_id"])
    op.create_index("idx_preference_snapshots_created_at", "preference_snapshots", ["created_at"])


def downgrade() -> None:
    op.drop_index("idx_preference_snapshots_created_at", table_name="preference_snapshots")
    op.drop_index("idx_preference_snapshots_user_id", table_name="preference_snapshots")
    op.drop_table("preference_snapshots")
