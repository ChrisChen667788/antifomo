"""add product competitive intelligence catalog

Revision ID: 20260828_0031
Revises: 20260807_0030
Create Date: 2026-08-28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260828_0031"
down_revision = "20260807_0030"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "product_strategy_sources" not in tables:
        op.create_table(
            "product_strategy_sources",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("catalog_key", sa.String(length=120), nullable=False),
            sa.Column("product_key", sa.String(length=80), nullable=False),
            sa.Column("vendor", sa.String(length=160), nullable=False),
            sa.Column("product_name", sa.String(length=160), nullable=False),
            sa.Column("source_title", sa.String(length=240), nullable=False),
            sa.Column("source_url", sa.Text(), nullable=False),
            sa.Column("source_kind", sa.String(length=60), server_default="official_product_page", nullable=False),
            sa.Column("source_digest", sa.String(length=64), nullable=False),
            sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("evidence_tier", sa.String(length=40), server_default="vendor_claim", nullable=False),
            sa.Column("evidence_status", sa.String(length=60), server_default="vendor_claim_unverified", nullable=False),
            sa.Column("vendor_claim", sa.Text(), nullable=False),
            sa.Column("claimed_capabilities_payload", sa.JSON(), nullable=False),
            sa.Column("local_implementation_status", sa.String(length=60), server_default="not_assessed", nullable=False),
            sa.Column("local_implementation_notes", sa.Text(), server_default="", nullable=False),
            sa.Column("local_release_status", sa.String(length=60), server_default="not_evaluated", nullable=False),
            sa.Column("local_release_notes", sa.Text(), server_default="", nullable=False),
            sa.Column("seed_managed", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("catalog_key", name="uq_product_strategy_source_catalog_key"),
        )

    inspector = sa.inspect(bind)
    source_indexes = {index["name"] for index in inspector.get_indexes("product_strategy_sources")}
    if "idx_product_strategy_sources_product_observed" not in source_indexes:
        op.create_index(
            "idx_product_strategy_sources_product_observed",
            "product_strategy_sources",
            ["product_key", "observed_at"],
            unique=False,
        )
    if "idx_product_strategy_sources_evidence" not in source_indexes:
        op.create_index(
            "idx_product_strategy_sources_evidence",
            "product_strategy_sources",
            ["evidence_tier", "evidence_status"],
            unique=False,
        )

    if "product_strategy_roadmap_cards" not in tables:
        op.create_table(
            "product_strategy_roadmap_cards",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("card_key", sa.String(length=120), nullable=False),
            sa.Column("product_key", sa.String(length=80), nullable=False),
            sa.Column("title", sa.String(length=240), nullable=False),
            sa.Column("decision", sa.String(length=40), nullable=False),
            sa.Column("status", sa.String(length=40), server_default="proposed", nullable=False),
            sa.Column("rationale", sa.Text(), nullable=False),
            sa.Column("source_catalog_keys_payload", sa.JSON(), nullable=False),
            sa.Column("source_digest", sa.String(length=64), nullable=False),
            sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("evidence_tier", sa.String(length=40), server_default="vendor_claim", nullable=False),
            sa.Column("evidence_status", sa.String(length=60), server_default="vendor_claim_unverified", nullable=False),
            sa.Column("acceptance_criteria_payload", sa.JSON(), nullable=False),
            sa.Column("module_targets_payload", sa.JSON(), nullable=False),
            sa.Column("approval_status", sa.String(length=60), server_default="human_review_required", nullable=False),
            sa.Column("release_impact", sa.String(length=60), server_default="none", nullable=False),
            sa.Column("seed_managed", sa.Boolean(), server_default=sa.true(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("card_key", name="uq_product_strategy_roadmap_card_key"),
        )

    inspector = sa.inspect(bind)
    roadmap_indexes = {index["name"] for index in inspector.get_indexes("product_strategy_roadmap_cards")}
    if "idx_product_strategy_roadmap_cards_product_status" not in roadmap_indexes:
        op.create_index(
            "idx_product_strategy_roadmap_cards_product_status",
            "product_strategy_roadmap_cards",
            ["product_key", "status"],
            unique=False,
        )
    if "idx_product_strategy_roadmap_cards_decision" not in roadmap_indexes:
        op.create_index(
            "idx_product_strategy_roadmap_cards_decision",
            "product_strategy_roadmap_cards",
            ["decision", "approval_status"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index("idx_product_strategy_roadmap_cards_decision", table_name="product_strategy_roadmap_cards")
    op.drop_index("idx_product_strategy_roadmap_cards_product_status", table_name="product_strategy_roadmap_cards")
    op.drop_table("product_strategy_roadmap_cards")
    op.drop_index("idx_product_strategy_sources_evidence", table_name="product_strategy_sources")
    op.drop_index("idx_product_strategy_sources_product_observed", table_name="product_strategy_sources")
    op.drop_table("product_strategy_sources")
