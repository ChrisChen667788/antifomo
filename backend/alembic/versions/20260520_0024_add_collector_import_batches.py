"""add collector import batches

Revision ID: 20260520_0024
Revises: 20260513_0023
Create Date: 2026-05-20 11:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260520_0024"
down_revision = "20260513_0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collector_import_batches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("import_type", sa.String(length=40), server_default="wechat_favorites", nullable=False),
        sa.Column("source_label", sa.String(length=120), server_default="微信收藏", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="queued", nullable=False),
        sa.Column("output_language", sa.String(length=10), server_default="zh-CN", nullable=False),
        sa.Column("processing_deferred", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("total_candidates", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("deduplicated_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("invalid_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("skipped_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("item_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("created_item_ids", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("result_payload", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("source_payload", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_collector_import_batches_user_created",
        "collector_import_batches",
        ["user_id", "created_at"],
    )
    op.create_index(
        "idx_collector_import_batches_type_status",
        "collector_import_batches",
        ["import_type", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_collector_import_batches_type_status", table_name="collector_import_batches")
    op.drop_index("idx_collector_import_batches_user_created", table_name="collector_import_batches")
    op.drop_table("collector_import_batches")
