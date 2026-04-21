"""add watchlists and entity catalog

Revision ID: 20260328_0014
Revises: 20260328_0013
Create Date: 2026-03-28 22:10:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260328_0014"
down_revision = "20260328_0013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "research_watchlists",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("tracking_topic_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("watch_type", sa.String(length=30), server_default="topic", nullable=False),
        sa.Column("query", sa.String(length=120), server_default="", nullable=False),
        sa.Column("region_filter", sa.String(length=40), server_default="", nullable=False),
        sa.Column("industry_filter", sa.String(length=40), server_default="", nullable=False),
        sa.Column("alert_level", sa.String(length=20), server_default="medium", nullable=False),
        sa.Column("schedule", sa.String(length=30), server_default="manual", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        sa.Column("last_checked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["tracking_topic_id"], ["research_tracking_topics.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_research_watchlists_user_updated_at", "research_watchlists", ["user_id", "updated_at"])
    op.create_index("idx_research_watchlists_tracking_topic_id", "research_watchlists", ["tracking_topic_id"])

    op.create_table(
        "research_watchlist_change_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("watchlist_id", sa.Uuid(), nullable=False),
        sa.Column("change_type", sa.String(length=20), server_default="rewritten", nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("severity", sa.String(length=20), server_default="medium", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["watchlist_id"], ["research_watchlists.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_research_watchlist_change_events_watchlist_created",
        "research_watchlist_change_events",
        ["watchlist_id", "created_at"],
    )

    op.create_table(
        "research_canonical_entities",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("canonical_name", sa.String(length=160), nullable=False),
        sa.Column("entity_type", sa.String(length=20), server_default="generic", nullable=False),
        sa.Column("region_hint", sa.String(length=80), server_default="", nullable=False),
        sa.Column("industry_hint", sa.String(length=80), server_default="", nullable=False),
        sa.Column("profile_payload", sa.JSON(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "canonical_name", "entity_type", name="uq_research_entity_user_name_type"),
    )
    op.create_index("idx_research_entities_user_updated_at", "research_canonical_entities", ["user_id", "updated_at"])

    op.create_table(
        "research_entity_aliases",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("alias_name", sa.String(length=160), nullable=False),
        sa.Column("confidence", sa.Integer(), server_default="80", nullable=False),
        sa.Column("source_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["entity_id"], ["research_canonical_entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("entity_id", "alias_name", name="uq_research_entity_alias"),
    )
    op.create_index("idx_research_entity_aliases_alias_name", "research_entity_aliases", ["alias_name"])

    op.create_table(
        "research_entity_relations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("from_entity_id", sa.Uuid(), nullable=False),
        sa.Column("to_entity_id", sa.Uuid(), nullable=False),
        sa.Column("relation_type", sa.String(length=30), nullable=False),
        sa.Column("evidence_payload", sa.JSON(), nullable=False),
        sa.Column("weight", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["from_entity_id"], ["research_canonical_entities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["to_entity_id"], ["research_canonical_entities.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "from_entity_id",
            "to_entity_id",
            "relation_type",
            name="uq_research_entity_relation_pair_type",
        ),
    )


def downgrade() -> None:
    op.drop_table("research_entity_relations")
    op.drop_index("idx_research_entity_aliases_alias_name", table_name="research_entity_aliases")
    op.drop_table("research_entity_aliases")
    op.drop_index("idx_research_entities_user_updated_at", table_name="research_canonical_entities")
    op.drop_table("research_canonical_entities")
    op.drop_index(
        "idx_research_watchlist_change_events_watchlist_created",
        table_name="research_watchlist_change_events",
    )
    op.drop_table("research_watchlist_change_events")
    op.drop_index("idx_research_watchlists_tracking_topic_id", table_name="research_watchlists")
    op.drop_index("idx_research_watchlists_user_updated_at", table_name="research_watchlists")
    op.drop_table("research_watchlists")
