"""add research experiment rollout audit

Revision ID: 20260513_0023
Revises: 20260513_0022
Create Date: 2026-05-13 17:20:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260513_0023"
down_revision = "20260513_0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_experiment_plans",
        sa.Column("gate_history_payload", sa.JSON(), server_default="[]", nullable=False),
    )
    op.add_column(
        "research_experiment_plans",
        sa.Column("rollout_payload", sa.JSON(), server_default="{}", nullable=False),
    )
    op.add_column(
        "research_experiment_plans",
        sa.Column("promoted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "research_experiment_plans",
        sa.Column("rollout_revoked_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("research_experiment_plans", "rollout_revoked_at")
    op.drop_column("research_experiment_plans", "promoted_at")
    op.drop_column("research_experiment_plans", "rollout_payload")
    op.drop_column("research_experiment_plans", "gate_history_payload")
