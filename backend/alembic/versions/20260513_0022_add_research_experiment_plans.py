"""add research experiment plans

Revision ID: 20260513_0022
Revises: 20260508_0021
Create Date: 2026-05-13 14:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260513_0022"
down_revision = "20260508_0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_experiment_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("lane_key", sa.String(length=60), nullable=False),
        sa.Column("strategy_family", sa.String(length=40), nullable=False),
        sa.Column("candidate_label", sa.String(length=180), server_default="", nullable=False),
        sa.Column("notes", sa.Text(), server_default="", nullable=False),
        sa.Column("strategy_payload", sa.JSON(), nullable=False),
        sa.Column("gate_config_payload", sa.JSON(), nullable=False),
        sa.Column("cohort_payload", sa.JSON(), nullable=False),
        sa.Column("baseline_payload", sa.JSON(), nullable=False),
        sa.Column("latest_gate_payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="draft", nullable=False),
        sa.Column("cohort_frozen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("baseline_locked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_gate_evaluated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_research_experiment_plans_user_updated_at",
        "research_experiment_plans",
        ["user_id", "updated_at"],
    )
    op.create_index(
        "idx_research_experiment_plans_lane_status",
        "research_experiment_plans",
        ["lane_key", "status"],
    )


def downgrade() -> None:
    op.drop_index("idx_research_experiment_plans_lane_status", table_name="research_experiment_plans")
    op.drop_index("idx_research_experiment_plans_user_updated_at", table_name="research_experiment_plans")
    op.drop_table("research_experiment_plans")
