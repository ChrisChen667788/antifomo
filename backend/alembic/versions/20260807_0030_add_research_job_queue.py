"""add durable research job queue fields

Revision ID: 20260807_0030
Revises: 20260726_0029
Create Date: 2026-08-07
"""

from alembic import op
import sqlalchemy as sa


revision = "20260807_0030"
down_revision = "20260726_0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {column["name"] for column in inspector.get_columns("research_jobs")}
    additions = (
        ("request_payload", sa.Column("request_payload", sa.JSON(), nullable=False, server_default="{}")),
        ("worker_id", sa.Column("worker_id", sa.String(length=80), nullable=False, server_default="")),
        ("lease_expires_at", sa.Column("lease_expires_at", sa.DateTime(timezone=True), nullable=True)),
        ("execution_attempts", sa.Column("execution_attempts", sa.Integer(), nullable=False, server_default="0")),
    )
    for name, column in additions:
        if name not in columns:
            op.add_column("research_jobs", column)

    indexes = {index["name"] for index in inspector.get_indexes("research_jobs")}
    if "idx_research_jobs_worker_lease" not in indexes:
        op.create_index(
            "idx_research_jobs_worker_lease",
            "research_jobs",
            ["worker_id", "lease_expires_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    indexes = {index["name"] for index in inspector.get_indexes("research_jobs")}
    if "idx_research_jobs_worker_lease" in indexes:
        op.drop_index("idx_research_jobs_worker_lease", table_name="research_jobs")
    columns = {column["name"] for column in inspector.get_columns("research_jobs")}
    for name in ("execution_attempts", "lease_expires_at", "worker_id", "request_payload"):
        if name in columns:
            op.drop_column("research_jobs", name)
