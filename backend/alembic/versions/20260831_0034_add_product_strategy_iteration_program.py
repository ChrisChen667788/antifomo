"""add governed 2.10.3-2.11.7 iteration-program records

Revision ID: 20260831_0034
Revises: 20260828_0033
Create Date: 2026-08-31
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260831_0034"
down_revision = "20260828_0033"
branch_labels = None
depends_on = None


def _index_names(bind: sa.engine.Connection, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def upgrade() -> None:
    """Create control-plane tables without materializing any execution authority.

    The application can call ``Base.create_all`` before Alembic in a local demo,
    so each table and index is guarded.  These tables only hold plan/revision
    records; they do not process Office files, render visuals, invoke agents,
    or change release readiness.
    """

    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "product_strategy_iterations" not in tables:
        op.create_table(
            "product_strategy_iterations",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("iteration_key", sa.String(length=180), nullable=False),
            sa.Column("project_scope", sa.String(length=120), nullable=False),
            sa.Column("version", sa.String(length=40), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=240), nullable=False),
            sa.Column("workstream", sa.String(length=120), nullable=False),
            sa.Column("decision", sa.String(length=40), nullable=False),
            sa.Column("purpose", sa.Text(), nullable=False),
            sa.Column("scope_boundary", sa.Text(), nullable=False),
            sa.Column("implementation_status", sa.String(length=80), nullable=False),
            sa.Column("external_evidence_status", sa.String(length=80), nullable=False),
            sa.Column("acceptance_status", sa.String(length=80), nullable=False),
            sa.Column("dependencies_payload", sa.JSON(), nullable=False),
            sa.Column("source_basis_payload", sa.JSON(), nullable=False),
            sa.Column("delivery_artifacts_payload", sa.JSON(), nullable=False),
            sa.Column("acceptance_criteria_payload", sa.JSON(), nullable=False),
            sa.Column("external_evidence_requirements_payload", sa.JSON(), nullable=False),
            sa.Column("can_auto_accept", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("can_auto_execute", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("can_auto_approve_release", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("requires_human_evidence_review", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("production_status", sa.String(length=60), server_default="not_authorized", nullable=False),
            sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
            sa.Column("revision_digest", sa.String(length=64), nullable=False),
            sa.Column("seed_managed", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("iteration_key", name="uq_product_strategy_iteration_key"),
        )

    iteration_indexes = _index_names(bind, "product_strategy_iterations")
    if "idx_product_strategy_iteration_scope_sequence" not in iteration_indexes:
        op.create_index(
            "idx_product_strategy_iteration_scope_sequence",
            "product_strategy_iterations",
            ["project_scope", "sequence"],
            unique=False,
        )
    if "idx_product_strategy_iteration_status" not in iteration_indexes:
        op.create_index(
            "idx_product_strategy_iteration_status",
            "product_strategy_iterations",
            ["implementation_status", "external_evidence_status"],
            unique=False,
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "product_strategy_iteration_revisions" not in tables:
        op.create_table(
            "product_strategy_iteration_revisions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("iteration_id", sa.Uuid(), nullable=False),
            sa.Column("iteration_key", sa.String(length=180), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("previous_revision_digest", sa.String(length=64), nullable=True),
            sa.Column("revision_digest", sa.String(length=64), nullable=False),
            sa.Column("event_type", sa.String(length=120), nullable=False),
            sa.Column("snapshot_payload", sa.JSON(), nullable=False),
            sa.Column("field_level_diff_payload", sa.JSON(), nullable=False),
            sa.Column("is_immutable", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("seed_managed", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["iteration_id"], ["product_strategy_iterations.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("iteration_id", "revision", name="uq_product_strategy_iteration_revision"),
        )

    revision_indexes = _index_names(bind, "product_strategy_iteration_revisions")
    if "idx_product_strategy_iteration_revision_created" not in revision_indexes:
        op.create_index(
            "idx_product_strategy_iteration_revision_created",
            "product_strategy_iteration_revisions",
            ["iteration_id", "created_at"],
            unique=False,
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "product_strategy_iteration_initialization_audits" not in tables:
        op.create_table(
            "product_strategy_iteration_initialization_audits",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("event_key", sa.String(length=180), nullable=False),
            sa.Column("project_scope", sa.String(length=120), nullable=False),
            sa.Column("event_type", sa.String(length=120), nullable=False),
            sa.Column("instruction_evidence_payload", sa.JSON(), nullable=False),
            sa.Column("iteration_program_digest", sa.String(length=64), nullable=False),
            sa.Column("iteration_keys_payload", sa.JSON(), nullable=False),
            sa.Column("event_digest", sa.String(length=64), nullable=False),
            sa.Column("can_auto_accept", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("can_auto_execute", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("can_auto_approve_release", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("release_gate_mutated", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("event_key", name="uq_product_strategy_iteration_initialization_event_key"),
        )

    audit_indexes = _index_names(bind, "product_strategy_iteration_initialization_audits")
    if "idx_product_strategy_iteration_initialization_created" not in audit_indexes:
        op.create_index(
            "idx_product_strategy_iteration_initialization_created",
            "product_strategy_iteration_initialization_audits",
            ["project_scope", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "product_strategy_iteration_initialization_audits" in tables:
        indexes = _index_names(bind, "product_strategy_iteration_initialization_audits")
        if "idx_product_strategy_iteration_initialization_created" in indexes:
            op.drop_index(
                "idx_product_strategy_iteration_initialization_created",
                table_name="product_strategy_iteration_initialization_audits",
            )
        op.drop_table("product_strategy_iteration_initialization_audits")

    tables = set(sa.inspect(bind).get_table_names())
    if "product_strategy_iteration_revisions" in tables:
        indexes = _index_names(bind, "product_strategy_iteration_revisions")
        if "idx_product_strategy_iteration_revision_created" in indexes:
            op.drop_index("idx_product_strategy_iteration_revision_created", table_name="product_strategy_iteration_revisions")
        op.drop_table("product_strategy_iteration_revisions")

    tables = set(sa.inspect(bind).get_table_names())
    if "product_strategy_iterations" in tables:
        indexes = _index_names(bind, "product_strategy_iterations")
        if "idx_product_strategy_iteration_status" in indexes:
            op.drop_index("idx_product_strategy_iteration_status", table_name="product_strategy_iterations")
        if "idx_product_strategy_iteration_scope_sequence" in indexes:
            op.drop_index("idx_product_strategy_iteration_scope_sequence", table_name="product_strategy_iterations")
        op.drop_table("product_strategy_iterations")
