"""add watchlist run history

Revision ID: 20260508_0021
Revises: 20260404_0020
Create Date: 2026-05-08 10:40:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260508_0021"
down_revision = "20260404_0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_watchlist_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("watchlist_id", sa.Uuid(), nullable=True),
        sa.Column("run_id", sa.String(length=80), nullable=False),
        sa.Column("watchlist_name", sa.String(length=120), server_default="", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="refreshed", nullable=False),
        sa.Column("change_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("attempt_count", sa.Integer(), server_default="1", nullable=False),
        sa.Column("retry_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("summary", sa.Text(), server_default="", nullable=False),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("notification_level", sa.String(length=20), server_default="low", nullable=False),
        sa.Column("notification_payload", sa.JSON(), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["watchlist_id"], ["research_watchlists.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_research_watchlist_runs_user_created", "research_watchlist_runs", ["user_id", "created_at"])
    op.create_index(
        "idx_research_watchlist_runs_watchlist_created",
        "research_watchlist_runs",
        ["watchlist_id", "created_at"],
    )
    op.create_index("idx_research_watchlist_runs_run_id", "research_watchlist_runs", ["run_id"])


def downgrade() -> None:
    op.drop_index("idx_research_watchlist_runs_run_id", table_name="research_watchlist_runs")
    op.drop_index("idx_research_watchlist_runs_watchlist_created", table_name="research_watchlist_runs")
    op.drop_index("idx_research_watchlist_runs_user_created", table_name="research_watchlist_runs")
    op.drop_table("research_watchlist_runs")
