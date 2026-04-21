"""add knowledge focus reference fields

Revision ID: 20260319_0007
Revises: 20260318_0006
Create Date: 2026-03-19 10:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260319_0007"
down_revision = "20260318_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "knowledge_entries",
        sa.Column("is_focus_reference", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )
    op.create_index(
        "idx_knowledge_entries_focus_reference",
        "knowledge_entries",
        ["user_id", "is_focus_reference"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_knowledge_entries_focus_reference", table_name="knowledge_entries")
    op.drop_column("knowledge_entries", "is_focus_reference")
