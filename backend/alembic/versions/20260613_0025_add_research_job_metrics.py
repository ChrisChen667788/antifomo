"""add research job metrics

Revision ID: 20260613_0025
Revises: 20260520_0024
Create Date: 2026-06-13 10:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260613_0025"
down_revision = "20260520_0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "research_jobs",
        sa.Column("metrics_payload", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("research_jobs", "metrics_payload")
