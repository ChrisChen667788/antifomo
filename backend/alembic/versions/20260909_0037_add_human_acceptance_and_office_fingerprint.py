"""Add append-only 2.10.7 human acceptance events and Office request fingerprints.

Revision ID: 20260909_0037
Revises: 20260909_0036
"""

from alembic import op
import sqlalchemy as sa

revision = "20260909_0037"
down_revision = "20260909_0036"
branch_labels = None
depends_on = None


def _table_names(bind):
    return set(sa.inspect(bind).get_table_names())


def upgrade() -> None:
    bind = op.get_bind()
    office = "product_strategy_office_evidence_receipts"
    if office in _table_names(bind):
        columns = {item["name"] for item in sa.inspect(bind).get_columns(office)}
        if "input_digest" not in columns:
            with op.batch_alter_table(office) as batch:
                batch.add_column(sa.Column("input_digest", sa.String(length=64), nullable=True))
        constraints = {item["name"] for item in sa.inspect(bind).get_unique_constraints(office)}
        if "uq_product_strategy_office_receipt_input_digest" not in constraints:
            with op.batch_alter_table(office) as batch:
                batch.create_unique_constraint("uq_product_strategy_office_receipt_input_digest", ["input_digest"])

    name = "product_strategy_human_acceptance_events"
    if name not in _table_names(bind):
        op.create_table(
            name,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("event_key", sa.String(length=100), nullable=False),
            sa.Column("idempotency_key", sa.String(length=160), nullable=False),
            sa.Column("request_digest", sa.String(length=64), nullable=False),
            sa.Column("artifact_key", sa.String(length=180), nullable=False),
            sa.Column("office_receipt_id", sa.Uuid(), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("previous_event_digest", sa.String(length=64), nullable=True),
            sa.Column("event_digest", sa.String(length=64), nullable=False),
            sa.Column("snapshot_payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.ForeignKeyConstraint(["office_receipt_id"], [f"{office}.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("event_key", name="uq_ps_acceptance_event_key"),
            sa.UniqueConstraint("idempotency_key", name="uq_ps_acceptance_idempotency"),
            sa.UniqueConstraint("artifact_key", "sequence", name="uq_ps_acceptance_sequence"),
        )
    indexes = {item["name"] for item in sa.inspect(bind).get_indexes(name)}
    if "idx_ps_acceptance_artifact_created" not in indexes:
        op.create_index("idx_ps_acceptance_artifact_created", name, ["artifact_key", "created_at"])

    if bind.dialect.name == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(sa.text(
                f"CREATE TRIGGER IF NOT EXISTS af_acceptance_no_{action.lower()} "
                f"BEFORE {action} ON {name} BEGIN SELECT RAISE(ABORT, 'Human acceptance events are append-only'); END"
            ))
    elif bind.dialect.name == "postgresql":
        op.execute(sa.text(
            "CREATE OR REPLACE FUNCTION af_reject_acceptance_mutation() RETURNS trigger "
            "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Human acceptance events are append-only'; END; $$"
        ))
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS af_acceptance_immutable ON {name}"))
        op.execute(sa.text(
            f"CREATE TRIGGER af_acceptance_immutable BEFORE UPDATE OR DELETE ON {name} "
            "FOR EACH ROW EXECUTE FUNCTION af_reject_acceptance_mutation()"
        ))


def downgrade() -> None:
    bind = op.get_bind()
    name = "product_strategy_human_acceptance_events"
    if name in _table_names(bind):
        op.drop_index("idx_ps_acceptance_artifact_created", table_name=name)
        op.drop_table(name)
    if bind.dialect.name == "postgresql":
        op.execute(sa.text("DROP FUNCTION IF EXISTS af_reject_acceptance_mutation()"))
