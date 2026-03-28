"""add collector sources table

Revision ID: 20260317_0003
Revises: 20260317_0002
Create Date: 2026-03-17 20:40:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260317_0003"
down_revision = "20260317_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "collector_sources",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("source_url", sa.Text(), nullable=False),
        sa.Column("source_domain", sa.String(length=255), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_collected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_collector_sources_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_collector_sources"),
        sa.UniqueConstraint("user_id", "source_url", name="uq_collector_sources_user_url"),
    )
    op.create_index("idx_collector_sources_user_id", "collector_sources", ["user_id"], unique=False)
    op.create_index("idx_collector_sources_enabled", "collector_sources", ["enabled"], unique=False)
    op.execute("CREATE INDEX idx_collector_sources_updated_at ON collector_sources (updated_at DESC)")


def downgrade() -> None:
    op.drop_index("idx_collector_sources_updated_at", table_name="collector_sources")
    op.drop_index("idx_collector_sources_enabled", table_name="collector_sources")
    op.drop_index("idx_collector_sources_user_id", table_name="collector_sources")
    op.drop_table("collector_sources")
