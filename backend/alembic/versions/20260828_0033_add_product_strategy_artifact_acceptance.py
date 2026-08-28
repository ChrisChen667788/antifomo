"""add HOLD-only product-strategy artifact acceptance records

Revision ID: 20260828_0033
Revises: 20260828_0032
Create Date: 2026-08-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260828_0033"
down_revision = "20260828_0032"
branch_labels = None
depends_on = None


def _index_names(bind: sa.engine.Connection, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def upgrade() -> None:
    """Create the review-only tables without overriding ORM-created tables.

    The local demo can call ``Base.create_all`` before Alembic.  As in 0031
    and 0032, each table and index is therefore created only when absent.
    Nothing in this revision represents Office/visual evidence or an accepted
    artifact; the rows persist HOLD-only review templates and their digests.
    """

    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "product_strategy_artifact_acceptance_drafts" not in tables:
        op.create_table(
            "product_strategy_artifact_acceptance_drafts",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("artifact_key", sa.String(length=180), nullable=False),
            sa.Column("project_scope", sa.String(length=120), nullable=False),
            sa.Column("decision_context_packet_id", sa.Uuid(), nullable=False),
            sa.Column("decision_context_packet_key", sa.String(length=160), nullable=False),
            sa.Column("roadmap_card_key", sa.String(length=120), nullable=False),
            sa.Column("decision", sa.String(length=40), nullable=False),
            sa.Column("artifact_type", sa.String(length=100), nullable=False),
            sa.Column("title", sa.String(length=240), nullable=False),
            sa.Column("artifact_summary", sa.Text(), nullable=False),
            sa.Column("acceptance_status", sa.String(length=40), server_default="hold", nullable=False),
            sa.Column("blocking_status", sa.String(length=40), server_default="blocked", nullable=False),
            sa.Column("office_evidence_status", sa.String(length=40), server_default="missing", nullable=False),
            sa.Column("visual_evidence_status", sa.String(length=40), server_default="missing", nullable=False),
            sa.Column("acceptance_checklist_payload", sa.JSON(), nullable=False),
            sa.Column("evidence_source_bundle_payload", sa.JSON(), nullable=False),
            sa.Column("evidence_source_bundle_digest", sa.String(length=64), nullable=False),
            sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
            sa.Column("revision_digest", sa.String(length=64), nullable=False),
            sa.Column("can_auto_accept", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("can_auto_execute", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("can_auto_approve_release", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("requires_human_evidence_review", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("production_status", sa.String(length=60), server_default="not_authorized", nullable=False),
            sa.Column("seed_managed", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(
                ["decision_context_packet_id"],
                ["product_strategy_decision_context_packets.id"],
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("artifact_key", name="uq_product_strategy_artifact_acceptance_draft_key"),
        )

    draft_indexes = _index_names(bind, "product_strategy_artifact_acceptance_drafts")
    if "idx_product_strategy_artifact_acceptance_project_status" not in draft_indexes:
        op.create_index(
            "idx_product_strategy_artifact_acceptance_project_status",
            "product_strategy_artifact_acceptance_drafts",
            ["project_scope", "acceptance_status"],
            unique=False,
        )
    if "idx_product_strategy_artifact_acceptance_context_packet" not in draft_indexes:
        op.create_index(
            "idx_product_strategy_artifact_acceptance_context_packet",
            "product_strategy_artifact_acceptance_drafts",
            ["decision_context_packet_id", "revision"],
            unique=False,
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "product_strategy_artifact_acceptance_revisions" not in tables:
        op.create_table(
            "product_strategy_artifact_acceptance_revisions",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("draft_id", sa.Uuid(), nullable=False),
            sa.Column("artifact_key", sa.String(length=180), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("previous_revision_digest", sa.String(length=64), nullable=True),
            sa.Column("revision_digest", sa.String(length=64), nullable=False),
            sa.Column("event_type", sa.String(length=100), nullable=False),
            sa.Column("snapshot_payload", sa.JSON(), nullable=False),
            sa.Column("evidence_source_bundle_payload", sa.JSON(), nullable=False),
            sa.Column("evidence_source_bundle_digest", sa.String(length=64), nullable=False),
            sa.Column("field_level_diff_payload", sa.JSON(), nullable=False),
            sa.Column("is_immutable", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("seed_managed", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(
                ["draft_id"], ["product_strategy_artifact_acceptance_drafts.id"], ondelete="CASCADE"
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("draft_id", "revision", name="uq_product_strategy_artifact_acceptance_revision"),
        )

    revision_indexes = _index_names(bind, "product_strategy_artifact_acceptance_revisions")
    if "idx_product_strategy_artifact_acceptance_revisions_draft_created" not in revision_indexes:
        op.create_index(
            "idx_product_strategy_artifact_acceptance_revisions_draft_created",
            "product_strategy_artifact_acceptance_revisions",
            ["draft_id", "created_at"],
            unique=False,
        )
    if "idx_product_strategy_artifact_acceptance_revisions_event" not in revision_indexes:
        op.create_index(
            "idx_product_strategy_artifact_acceptance_revisions_event",
            "product_strategy_artifact_acceptance_revisions",
            ["event_type", "created_at"],
            unique=False,
        )

    tables = set(sa.inspect(bind).get_table_names())
    if "product_strategy_artifact_acceptance_initialization_audits" not in tables:
        op.create_table(
            "product_strategy_artifact_acceptance_initialization_audits",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("event_key", sa.String(length=180), nullable=False),
            sa.Column("project_scope", sa.String(length=120), nullable=False),
            sa.Column("event_type", sa.String(length=100), nullable=False),
            sa.Column("instruction_evidence_payload", sa.JSON(), nullable=False),
            sa.Column("required_context_packet_keys_payload", sa.JSON(), nullable=False),
            sa.Column("artifact_catalog_digest", sa.String(length=64), nullable=False),
            sa.Column("context_packet_catalog_digest", sa.String(length=64), nullable=False),
            sa.Column("event_digest", sa.String(length=64), nullable=False),
            sa.Column("can_auto_accept", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("can_auto_execute", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("can_auto_approve_release", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("release_gate_mutated", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("event_key", name="uq_product_strategy_artifact_acceptance_initialization_event_key"),
        )

    audit_indexes = _index_names(bind, "product_strategy_artifact_acceptance_initialization_audits")
    if "idx_product_strategy_artifact_acceptance_initialization_created" not in audit_indexes:
        op.create_index(
            "idx_product_strategy_artifact_acceptance_initialization_created",
            "product_strategy_artifact_acceptance_initialization_audits",
            ["project_scope", "created_at"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "product_strategy_artifact_acceptance_initialization_audits" in tables:
        audit_indexes = _index_names(bind, "product_strategy_artifact_acceptance_initialization_audits")
        if "idx_product_strategy_artifact_acceptance_initialization_created" in audit_indexes:
            op.drop_index(
                "idx_product_strategy_artifact_acceptance_initialization_created",
                table_name="product_strategy_artifact_acceptance_initialization_audits",
            )
        op.drop_table("product_strategy_artifact_acceptance_initialization_audits")

    tables = set(sa.inspect(bind).get_table_names())
    if "product_strategy_artifact_acceptance_revisions" in tables:
        revision_indexes = _index_names(bind, "product_strategy_artifact_acceptance_revisions")
        if "idx_product_strategy_artifact_acceptance_revisions_event" in revision_indexes:
            op.drop_index(
                "idx_product_strategy_artifact_acceptance_revisions_event",
                table_name="product_strategy_artifact_acceptance_revisions",
            )
        if "idx_product_strategy_artifact_acceptance_revisions_draft_created" in revision_indexes:
            op.drop_index(
                "idx_product_strategy_artifact_acceptance_revisions_draft_created",
                table_name="product_strategy_artifact_acceptance_revisions",
            )
        op.drop_table("product_strategy_artifact_acceptance_revisions")

    tables = set(sa.inspect(bind).get_table_names())
    if "product_strategy_artifact_acceptance_drafts" in tables:
        draft_indexes = _index_names(bind, "product_strategy_artifact_acceptance_drafts")
        if "idx_product_strategy_artifact_acceptance_context_packet" in draft_indexes:
            op.drop_index(
                "idx_product_strategy_artifact_acceptance_context_packet",
                table_name="product_strategy_artifact_acceptance_drafts",
            )
        if "idx_product_strategy_artifact_acceptance_project_status" in draft_indexes:
            op.drop_index(
                "idx_product_strategy_artifact_acceptance_project_status",
                table_name="product_strategy_artifact_acceptance_drafts",
            )
        op.drop_table("product_strategy_artifact_acceptance_drafts")
