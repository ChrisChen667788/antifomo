"""link compare snapshots to report versions

Revision ID: 20260403_0018
Revises: 20260403_0017
Create Date: 2026-04-03 16:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260403_0018"
down_revision = "20260403_0017"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("research_compare_snapshots") as batch_op:
        batch_op.add_column(sa.Column("report_version_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_research_compare_snapshots_report_version_id",
            "research_report_versions",
            ["report_version_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "idx_research_compare_snapshots_report_version_id",
            ["report_version_id"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("research_compare_snapshots") as batch_op:
        batch_op.drop_index("idx_research_compare_snapshots_report_version_id")
        batch_op.drop_constraint("fk_research_compare_snapshots_report_version_id", type_="foreignkey")
        batch_op.drop_column("report_version_id")
