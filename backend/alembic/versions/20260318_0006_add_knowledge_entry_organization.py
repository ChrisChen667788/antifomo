"""add knowledge entry organization fields

Revision ID: 20260318_0006
Revises: 20260318_0005
Create Date: 2026-03-18 21:25:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260318_0006"
down_revision = "20260318_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_entries", sa.Column("collection_name", sa.String(length=80), nullable=True))
    op.add_column(
        "knowledge_entries",
        sa.Column("is_pinned", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index(
        "idx_knowledge_entries_pinned",
        "knowledge_entries",
        ["user_id", "is_pinned"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_knowledge_entries_pinned", table_name="knowledge_entries")
    op.drop_column("knowledge_entries", "is_pinned")
    op.drop_column("knowledge_entries", "collection_name")
