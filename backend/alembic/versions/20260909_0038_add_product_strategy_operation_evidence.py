"""Append-only local operation evidence; never an execution authorization.

Revision ID: 20260909_0038
Revises: 20260909_0037
"""
from alembic import op
import sqlalchemy as sa

revision = "20260909_0038"
down_revision = "20260909_0037"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    name = "product_strategy_operation_evidence"
    if name not in sa.inspect(bind).get_table_names():
        op.create_table(
            name,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("evidence_key", sa.String(100), nullable=False),
            sa.Column("kind", sa.String(40), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("digest", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("evidence_key", name="uq_product_strategy_operation_evidence_key"),
        )
    if "ix_product_strategy_operation_evidence_kind" not in {item["name"] for item in sa.inspect(bind).get_indexes(name)}:
        op.create_index("ix_product_strategy_operation_evidence_kind", name, ["kind"])
    if bind.dialect.name == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(sa.text(f"CREATE TRIGGER IF NOT EXISTS af_operations_no_{action.lower()} BEFORE {action} ON {name} BEGIN SELECT RAISE(ABORT, 'Operation evidence is append-only'); END"))
    elif bind.dialect.name == "postgresql":
        op.execute(sa.text("CREATE OR REPLACE FUNCTION af_reject_operation_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Operation evidence is append-only'; END; $$"))
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS af_operations_immutable ON {name}"))
        op.execute(sa.text(f"CREATE TRIGGER af_operations_immutable BEFORE UPDATE OR DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION af_reject_operation_mutation()"))


def downgrade() -> None:
    if "product_strategy_operation_evidence" in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table("product_strategy_operation_evidence")
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text("DROP FUNCTION IF EXISTS af_reject_operation_mutation()"))
