"""add knowledge entries table

Revision ID: 20260317_0004
Revises: 20260317_0003
Create Date: 2026-03-17 22:15:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260317_0004"
down_revision = "20260317_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("item_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("source_domain", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_knowledge_entries_user_id_users",
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["item_id"],
            ["items.id"],
            name="fk_knowledge_entries_item_id_items",
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_entries"),
    )
    op.create_index("idx_knowledge_entries_user_id", "knowledge_entries", ["user_id"], unique=False)
    op.create_index("idx_knowledge_entries_item_id", "knowledge_entries", ["item_id"], unique=False)
    op.execute("CREATE INDEX idx_knowledge_entries_created_at ON knowledge_entries (created_at DESC)")


def downgrade() -> None:
    op.drop_index("idx_knowledge_entries_created_at", table_name="knowledge_entries")
    op.drop_index("idx_knowledge_entries_item_id", table_name="knowledge_entries")
    op.drop_index("idx_knowledge_entries_user_id", table_name="knowledge_entries")
    op.drop_table("knowledge_entries")
