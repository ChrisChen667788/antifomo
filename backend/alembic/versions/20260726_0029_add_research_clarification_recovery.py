"""add research clarification recovery and experience tracking

Revision ID: 20260726_0029
Revises: 20260718_0028
Create Date: 2026-07-26 18:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260726_0029"
down_revision = "20260718_0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("research_jobs") as batch:
        batch.add_column(
            sa.Column(
                "interaction_state",
                sa.String(length=30),
                server_default="recovering",
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "clarification_payload",
                sa.JSON(),
                server_default=sa.text("'{}'"),
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "recovery_payload",
                sa.JSON(),
                server_default=sa.text("'{}'"),
                nullable=False,
            )
        )
        batch.add_column(
            sa.Column(
                "experience_payload",
                sa.JSON(),
                server_default=sa.text("'{}'"),
                nullable=False,
            )
        )
        batch.add_column(sa.Column("parent_job_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("root_job_id", sa.Uuid(), nullable=True))
        batch.add_column(sa.Column("resumed_child_job_id", sa.Uuid(), nullable=True))
        batch.add_column(
            sa.Column("recovery_attempt", sa.Integer(), server_default="0", nullable=False)
        )
        batch.add_column(
            sa.Column(
                "accepted_snapshot_digest",
                sa.String(length=64),
                server_default="",
                nullable=False,
            )
        )
        batch.add_column(sa.Column("idempotency_key", sa.String(length=120), nullable=True))
        batch.create_unique_constraint(
            "uq_research_jobs_user_idempotency",
            ["user_id", "idempotency_key"],
        )
        batch.create_index(
            "idx_research_jobs_parent_job_id",
            ["parent_job_id"],
            unique=False,
        )
        batch.create_index(
            "idx_research_jobs_interaction_state",
            ["interaction_state"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("research_jobs") as batch:
        batch.drop_index("idx_research_jobs_interaction_state")
        batch.drop_index("idx_research_jobs_parent_job_id")
        batch.drop_constraint("uq_research_jobs_user_idempotency", type_="unique")
        batch.drop_column("idempotency_key")
        batch.drop_column("accepted_snapshot_digest")
        batch.drop_column("recovery_attempt")
        batch.drop_column("resumed_child_job_id")
        batch.drop_column("root_job_id")
        batch.drop_column("parent_job_id")
        batch.drop_column("experience_payload")
        batch.drop_column("recovery_payload")
        batch.drop_column("clarification_payload")
        batch.drop_column("interaction_state")
