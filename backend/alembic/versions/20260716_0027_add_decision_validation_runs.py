"""add decision validation runs

Revision ID: 20260716_0027
Revises: 20260716_0026
Create Date: 2026-07-16 16:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260716_0027"
down_revision = "20260716_0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_validation_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("milestone_version", sa.String(length=20), nullable=False),
        sa.Column("suite_key", sa.String(length=80), nullable=False),
        sa.Column("evidence_class", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("metrics_payload", sa.JSON(), nullable=False),
        sa.Column("evidence_payload", sa.JSON(), nullable=False),
        sa.Column("findings_payload", sa.JSON(), nullable=False),
        sa.Column("input_digest", sa.String(length=64), nullable=False),
        sa.Column("reviewer_id", sa.String(length=160), server_default="", nullable=False),
        sa.Column("reviewer_role", sa.String(length=80), server_default="", nullable=False),
        sa.Column("attestation", sa.Text(), server_default="", nullable=False),
        sa.Column("source_artifact_uri", sa.Text(), server_default="", nullable=False),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_decision_validation_runs_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_validation_runs")),
    )
    op.create_index(
        "idx_decision_validation_user_suite_created",
        "decision_validation_runs",
        ["user_id", "suite_key", "created_at"],
        unique=False,
    )
    op.create_index(
        "idx_decision_validation_milestone_status",
        "decision_validation_runs",
        ["milestone_version", "status"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_decision_validation_milestone_status", table_name="decision_validation_runs")
    op.drop_index("idx_decision_validation_user_suite_created", table_name="decision_validation_runs")
    op.drop_table("decision_validation_runs")
