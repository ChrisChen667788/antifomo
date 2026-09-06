"""add immutable 2.10.5 Office evidence receipts

Revision ID: 20260906_0035
Revises: 20260831_0034
Create Date: 2026-09-06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260906_0035"
down_revision = "20260831_0034"
branch_labels = None
depends_on = None


def _index_names(bind: sa.engine.Connection, table_name: str) -> set[str]:
    return {index["name"] for index in sa.inspect(bind).get_indexes(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    table_name = "product_strategy_office_evidence_receipts"
    if table_name not in tables:
        op.create_table(
            table_name,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("receipt_key", sa.String(length=240), nullable=False),
            sa.Column("artifact_acceptance_draft_id", sa.Uuid(), nullable=False),
            sa.Column("artifact_key", sa.String(length=180), nullable=False),
            sa.Column("artifact_revision", sa.Integer(), nullable=False),
            sa.Column("artifact_revision_digest", sa.String(length=64), nullable=False),
            sa.Column("file_name", sa.String(length=240), nullable=False),
            sa.Column("media_type", sa.String(length=160), nullable=False),
            sa.Column("file_size_bytes", sa.Integer(), nullable=False),
            sa.Column("file_sha256", sa.String(length=64), nullable=False),
            sa.Column("storage_ref", sa.String(length=360), nullable=False),
            sa.Column("source_version", sa.String(length=120), nullable=False),
            sa.Column("validator_version", sa.String(length=80), nullable=False),
            sa.Column("structure_status", sa.String(length=40), nullable=False),
            sa.Column("office_roundtrip_status", sa.String(length=60), nullable=False),
            sa.Column("visual_evidence_status", sa.String(length=60), nullable=False),
            sa.Column("page_count", sa.Integer(), server_default="0", nullable=False),
            sa.Column("rendered_pdf_sha256", sa.String(length=64), nullable=True),
            sa.Column("rendered_pages_payload", sa.JSON(), nullable=False),
            sa.Column("validation_payload", sa.JSON(), nullable=False),
            sa.Column("receipt_digest", sa.String(length=64), nullable=False),
            sa.Column("evidence_level", sa.String(length=60), server_default="local_runtime_evidence", nullable=False),
            sa.Column("human_review_status", sa.String(length=40), server_default="missing", nullable=False),
            sa.Column("acceptance_status", sa.String(length=40), server_default="hold", nullable=False),
            sa.Column("blocking_status", sa.String(length=40), server_default="blocked", nullable=False),
            sa.Column("can_auto_accept", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("can_auto_approve_release", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("production_status", sa.String(length=60), server_default="not_authorized", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(
                ["artifact_acceptance_draft_id"],
                ["product_strategy_artifact_acceptance_drafts.id"],
                ondelete="RESTRICT",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("artifact_key", "file_sha256", name="uq_product_strategy_office_receipt_artifact_file"),
            sa.UniqueConstraint("receipt_key", name="uq_product_strategy_office_receipt_key"),
        )
    indexes = _index_names(bind, table_name)
    if "idx_product_strategy_office_receipt_artifact_created" not in indexes:
        op.create_index(
            "idx_product_strategy_office_receipt_artifact_created",
            table_name,
            ["artifact_key", "created_at"],
            unique=False,
        )
    if "idx_product_strategy_office_receipt_status" not in indexes:
        op.create_index(
            "idx_product_strategy_office_receipt_status",
            table_name,
            ["office_roundtrip_status", "visual_evidence_status"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    table_name = "product_strategy_office_evidence_receipts"
    if table_name not in set(sa.inspect(bind).get_table_names()):
        return
    indexes = _index_names(bind, table_name)
    for name in (
        "idx_product_strategy_office_receipt_status",
        "idx_product_strategy_office_receipt_artifact_created",
    ):
        if name in indexes:
            op.drop_index(name, table_name=table_name)
    op.drop_table(table_name)
