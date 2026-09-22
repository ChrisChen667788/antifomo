"""Add append-only 2.10.6 visual evidence revisions.

Revision ID: 20260909_0036
Revises: 20260906_0035
"""

from alembic import op
import sqlalchemy as sa

revision = "20260909_0036"
down_revision = "20260906_0035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    name = "product_strategy_visual_evidence_revisions"
    if name not in sa.inspect(bind).get_table_names():
        op.create_table(
            name,
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("revision_key", sa.String(100), nullable=False),
            sa.Column("office_receipt_id", sa.Uuid(), nullable=False),
            sa.Column("surface_key", sa.String(120), nullable=False),
            sa.Column("capture_kind", sa.String(40), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("previous_revision_digest", sa.String(64), nullable=True),
            sa.Column("revision_digest", sa.String(64), nullable=False),
            sa.Column("content_digest", sa.String(64), nullable=False),
            sa.Column("snapshot_payload", sa.JSON(), nullable=False),
            sa.Column("field_level_diff_payload", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.ForeignKeyConstraint(["office_receipt_id"], ["product_strategy_office_evidence_receipts.id"], ondelete="RESTRICT"),
            sa.UniqueConstraint("revision_key", name="uq_product_strategy_visual_revision_key"),
            sa.UniqueConstraint("office_receipt_id", "surface_key", "capture_kind", "revision", name="uq_product_strategy_visual_revision_number"),
        )
    indexes = {entry["name"] for entry in sa.inspect(bind).get_indexes(name)}
    if "idx_product_strategy_visual_receipt_created" not in indexes:
        op.create_index("idx_product_strategy_visual_receipt_created", name, ["office_receipt_id", "created_at"])
    if bind.dialect.name == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(sa.text(f"CREATE TRIGGER IF NOT EXISTS af_visual_no_{action.lower()} BEFORE {action} ON {name} BEGIN SELECT RAISE(ABORT, 'Visual evidence revisions are append-only'); END"))
    elif bind.dialect.name == "postgresql":
        op.execute(sa.text("CREATE OR REPLACE FUNCTION af_reject_visual_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Visual evidence revisions are append-only'; END; $$"))
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS af_visual_immutable ON {name}"))
        op.execute(sa.text(f"CREATE TRIGGER af_visual_immutable BEFORE UPDATE OR DELETE ON {name} FOR EACH ROW EXECUTE FUNCTION af_reject_visual_mutation()"))
    receipt_name = "product_strategy_office_evidence_receipts"
    constraints = {entry["name"] for entry in sa.inspect(bind).get_unique_constraints(receipt_name)}
    if "uq_product_strategy_office_receipt_artifact_file" in constraints:
        with op.batch_alter_table(receipt_name) as batch:
            batch.drop_constraint("uq_product_strategy_office_receipt_artifact_file", type_="unique")
            batch.create_unique_constraint("uq_product_strategy_office_receipt_revision_file", ["artifact_key", "artifact_revision_digest", "file_sha256"])


def downgrade() -> None:
    name = "product_strategy_visual_evidence_revisions"
    if name in sa.inspect(op.get_bind()).get_table_names():
        op.drop_table(name)
    if op.get_bind().dialect.name == "postgresql":
        op.execute(sa.text("DROP FUNCTION IF EXISTS af_reject_visual_mutation()"))
    # The expanded Office key is intentionally retained: reverting it would
    # discard valid receipts for a repeated file across artifact revisions.
