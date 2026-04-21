"""add knowledge rules table

Revision ID: 20260318_0005
Revises: 20260317_0004
Create Date: 2026-03-18 12:20:00
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision = "20260318_0005"
down_revision = "20260317_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "knowledge_rules",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("min_score_value", sa.Numeric(3, 2), server_default="4.00", nullable=False),
        sa.Column("archive_on_like", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("archive_on_save", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name="fk_knowledge_rules_user_id_users",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_knowledge_rules"),
        sa.UniqueConstraint("user_id", name="uq_knowledge_rules_user_id"),
    )
    op.create_index("idx_knowledge_rules_user_id", "knowledge_rules", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index("idx_knowledge_rules_user_id", table_name="knowledge_rules")
    op.drop_table("knowledge_rules")
