"""add output language for items and sessions

Revision ID: 20260317_0002
Revises: 20260316_0001
Create Date: 2026-03-17 09:10:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "20260317_0002"
down_revision = "20260316_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "items",
        sa.Column("output_language", sa.String(length=10), nullable=False, server_default=sa.text("'zh-CN'")),
    )
    op.add_column(
        "focus_sessions",
        sa.Column("output_language", sa.String(length=10), nullable=False, server_default=sa.text("'zh-CN'")),
    )
    op.alter_column("items", "output_language", server_default=None)
    op.alter_column("focus_sessions", "output_language", server_default=None)


def downgrade() -> None:
    op.drop_column("focus_sessions", "output_language")
    op.drop_column("items", "output_language")
