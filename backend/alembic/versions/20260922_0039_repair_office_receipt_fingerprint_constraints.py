"""Align migrated Office receipts with request fingerprints and append-only guards.

Revision ID: 20260922_0039
Revises: 20260909_0038
"""

from alembic import op
import sqlalchemy as sa


revision = "20260922_0039"
down_revision = "20260909_0038"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    name = "product_strategy_office_evidence_receipts"
    constraints = {item["name"] for item in sa.inspect(bind).get_unique_constraints(name)}
    obsolete = constraints & {
        "uq_product_strategy_office_receipt_artifact_file",
        "uq_product_strategy_office_receipt_revision_file",
    }
    fingerprint_constraint = "uq_product_strategy_office_receipt_input_digest"
    if obsolete or fingerprint_constraint not in constraints:
        # The input digest includes the artifact revision, rendering inputs and
        # validation requirements. Older file-only keys reject valid re-reviews.
        # Preserve every historical row/key/digest, including NULL legacy inputs.
        with op.batch_alter_table(name) as batch:
            for constraint in sorted(obsolete):
                batch.drop_constraint(constraint, type_="unique")
            if fingerprint_constraint not in constraints:
                batch.create_unique_constraint(fingerprint_constraint, ["input_digest"])

    # Model after_create listeners do not run when Alembic alters an existing
    # table. Install the same DB-level guard after any SQLite table recreation.
    if bind.dialect.name == "sqlite":
        for action in ("UPDATE", "DELETE"):
            op.execute(sa.text(
                f"CREATE TRIGGER IF NOT EXISTS af_office_no_{action.lower()} BEFORE {action} ON {name} "
                "BEGIN SELECT RAISE(ABORT, 'Office evidence receipts are append-only'); END"
            ))
    elif bind.dialect.name == "postgresql":
        op.execute(sa.text(
            "CREATE OR REPLACE FUNCTION af_reject_office_mutation() RETURNS trigger LANGUAGE plpgsql AS $$ "
            "BEGIN RAISE EXCEPTION 'Office evidence receipts are append-only'; END; $$"
        ))
        op.execute(sa.text(f"DROP TRIGGER IF EXISTS af_office_immutable ON {name}"))
        op.execute(sa.text(
            f"CREATE TRIGGER af_office_immutable BEFORE UPDATE OR DELETE ON {name} "
            "FOR EACH ROW EXECUTE FUNCTION af_reject_office_mutation()"
        ))


def downgrade() -> None:
    # Restoring a file-only key could discard valid receipts. Retain both the
    # expanded identity and append-only protection on downgrade, as in 0036.
    pass
