"""add reviewable product-strategy decision context packets

Revision ID: 20260828_0032
Revises: 20260828_0031
Create Date: 2026-08-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260828_0032"
down_revision = "20260828_0031"
branch_labels = None
depends_on = None


def _index_names(bind: sa.engine.Connection, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def upgrade() -> None:
    """Create missing tables/indexes without failing after ``Base.create_all``.

    Local demo startup can create ORM tables before Alembic is run.  This
    migration therefore checks each table and index independently, matching the
    compatibility rule introduced by revision 0031.
    """

    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "product_strategy_decision_context_packets" not in tables:
        op.create_table(
            "product_strategy_decision_context_packets",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("packet_key", sa.String(length=160), nullable=False),
            sa.Column("project_scope", sa.String(length=120), nullable=False),
            sa.Column("roadmap_card_key", sa.String(length=120), nullable=False),
            sa.Column("product_key", sa.String(length=80), nullable=False),
            sa.Column("decision", sa.String(length=40), nullable=False),
            sa.Column("title", sa.String(length=240), nullable=False),
            sa.Column("problem_statement", sa.Text(), nullable=False),
            sa.Column("rationale", sa.Text(), nullable=False),
            sa.Column("source_catalog_keys_payload", sa.JSON(), nullable=False),
            sa.Column("source_digests_payload", sa.JSON(), nullable=False),
            sa.Column("source_references_payload", sa.JSON(), nullable=False),
            sa.Column("assumptions_payload", sa.JSON(), nullable=False),
            sa.Column("constraints_payload", sa.JSON(), nullable=False),
            sa.Column("module_targets_payload", sa.JSON(), nullable=False),
            sa.Column("owner_evidence_payload", sa.JSON(), nullable=False),
            sa.Column("retention_until", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
            sa.Column("revision_digest", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=60), server_default="approved_for_context", nullable=False),
            sa.Column("can_auto_execute", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("can_auto_approve_release", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("requires_human_change_approval", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("production_status", sa.String(length=60), server_default="not_authorized", nullable=False),
            sa.Column("seed_managed", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("packet_key", name="uq_product_strategy_context_packet_key"),
        )

    packet_indexes = _index_names(bind, "product_strategy_decision_context_packets")
    if "idx_product_strategy_context_packets_project_status" not in packet_indexes:
        op.create_index(
            "idx_product_strategy_context_packets_project_status",
            "product_strategy_decision_context_packets",
            ["project_scope", "status"],
            unique=False,
        )
    if "idx_product_strategy_context_packets_card" not in packet_indexes:
        op.create_index(
            "idx_product_strategy_context_packets_card",
            "product_strategy_decision_context_packets",
            ["roadmap_card_key", "decision"],
            unique=False,
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "product_strategy_decision_context_packet_revisions" not in tables:
        op.create_table(
            "product_strategy_decision_context_packet_revisions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("packet_id", sa.Uuid(), nullable=False),
            sa.Column("packet_key", sa.String(length=160), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("previous_revision_digest", sa.String(length=64), nullable=True),
            sa.Column("revision_digest", sa.String(length=64), nullable=False),
            sa.Column("event_type", sa.String(length=80), nullable=False),
            sa.Column("snapshot_payload", sa.JSON(), nullable=False),
            sa.Column("approval_evidence_payload", sa.JSON(), nullable=False),
            sa.Column("is_immutable", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("seed_managed", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(
                ["packet_id"], ["product_strategy_decision_context_packets.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("packet_id", "revision", name="uq_product_strategy_context_packet_revision"),
        )

    revision_indexes = _index_names(bind, "product_strategy_decision_context_packet_revisions")
    if "idx_product_strategy_context_revisions_packet_created" not in revision_indexes:
        op.create_index(
            "idx_product_strategy_context_revisions_packet_created",
            "product_strategy_decision_context_packet_revisions",
            ["packet_id", "created_at"],
            unique=False,
        )
    if "idx_product_strategy_context_revisions_event" not in revision_indexes:
        op.create_index(
            "idx_product_strategy_context_revisions_event",
            "product_strategy_decision_context_packet_revisions",
            ["event_type", "created_at"],
            unique=False,
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "product_strategy_decision_context_initialization_audits" not in tables:
        op.create_table(
            "product_strategy_decision_context_initialization_audits",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("event_key", sa.String(length=160), nullable=False),
            sa.Column("project_scope", sa.String(length=120), nullable=False),
            sa.Column("event_type", sa.String(length=80), nullable=False),
            sa.Column("approval_evidence_payload", sa.JSON(), nullable=False),
            sa.Column("allowed_decisions_payload", sa.JSON(), nullable=False),
            sa.Column("excluded_card_keys_payload", sa.JSON(), nullable=False),
            sa.Column("source_catalog_version", sa.String(length=40), nullable=False),
            sa.Column("packet_catalog_digest", sa.String(length=64), nullable=False),
            sa.Column("event_digest", sa.String(length=64), nullable=False),
            sa.Column("can_auto_execute", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("can_auto_approve_release", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("release_gate_mutated", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("event_key", name="uq_product_strategy_context_initialization_event_key"),
        )

    audit_indexes = _index_names(bind, "product_strategy_decision_context_initialization_audits")
    if "idx_product_strategy_context_initialization_created" not in audit_indexes:
        op.create_index(
            "idx_product_strategy_context_initialization_created",
            "product_strategy_decision_context_initialization_audits",
            ["project_scope", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "product_strategy_decision_context_initialization_audits" in tables:
        audit_indexes = _index_names(bind, "product_strategy_decision_context_initialization_audits")
        if "idx_product_strategy_context_initialization_created" in audit_indexes:
            op.drop_index(
                "idx_product_strategy_context_initialization_created",
                table_name="product_strategy_decision_context_initialization_audits",
            )
        op.drop_table("product_strategy_decision_context_initialization_audits")

    tables = set(sa.inspect(bind).get_table_names())
    if "product_strategy_decision_context_packet_revisions" in tables:
        revision_indexes = _index_names(bind, "product_strategy_decision_context_packet_revisions")
        if "idx_product_strategy_context_revisions_event" in revision_indexes:
            op.drop_index(
                "idx_product_strategy_context_revisions_event",
                table_name="product_strategy_decision_context_packet_revisions",
            )
        if "idx_product_strategy_context_revisions_packet_created" in revision_indexes:
            op.drop_index(
                "idx_product_strategy_context_revisions_packet_created",
                table_name="product_strategy_decision_context_packet_revisions",
            )
        op.drop_table("product_strategy_decision_context_packet_revisions")

    tables = set(sa.inspect(bind).get_table_names())
    if "product_strategy_decision_context_packets" in tables:
        packet_indexes = _index_names(bind, "product_strategy_decision_context_packets")
        if "idx_product_strategy_context_packets_card" in packet_indexes:
            op.drop_index(
                "idx_product_strategy_context_packets_card",
                table_name="product_strategy_decision_context_packets",
            )
        if "idx_product_strategy_context_packets_project_status" in packet_indexes:
            op.drop_index(
                "idx_product_strategy_context_packets_project_status",
                table_name="product_strategy_decision_context_packets",
            )
        op.drop_table("product_strategy_decision_context_packets")
