"""add focus session pause state

Revision ID: 20260404_0020
Revises: 20260403_0019
Create Date: 2026-04-04 09:50:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260404_0020"
down_revision = "20260403_0019"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "focus_sessions",
        sa.Column("current_window_started_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "focus_sessions",
        sa.Column("paused_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "focus_sessions",
        sa.Column("elapsed_seconds", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("focus_sessions", "elapsed_seconds")
    op.drop_column("focus_sessions", "paused_at")
    op.drop_column("focus_sessions", "current_window_started_at")
