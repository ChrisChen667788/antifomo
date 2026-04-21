"""add knowledge metadata payload

Revision ID: 20260320_0010
Revises: 20260319_0008
Create Date: 2026-03-20 20:55:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260320_0010"
down_revision = "20260319_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_entries", sa.Column("metadata_payload", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("knowledge_entries", "metadata_payload")
