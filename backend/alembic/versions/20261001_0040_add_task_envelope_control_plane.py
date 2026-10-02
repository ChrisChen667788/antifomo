"""Add the governed Task Envelope control plane.

Revision ID: 20261001_0040
Revises: 20260922_0039

This is an expand-only migration.  Approval and receipt evidence is retained if
the feature flag is turned off, so downgrade intentionally does not drop data.
"""

from alembic import op
import sqlalchemy as sa


revision = "20261001_0040"
down_revision = "20260922_0039"
branch_labels = None
depends_on = None


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    bind = op.get_bind()
    existing = {item["name"] for item in sa.inspect(bind).get_indexes(table_name)}
    if index_name not in existing:
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())

    if "model_profiles" not in tables:
        op.create_table(
            "model_profiles",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("profile_key", sa.String(120), nullable=False),
            sa.Column("revision", sa.Integer(), nullable=False),
            sa.Column("provider", sa.String(80), nullable=False),
            sa.Column("model", sa.String(160), nullable=False),
            sa.Column("model_revision", sa.String(160), nullable=False),
            sa.Column("temperature", sa.Numeric(5, 3), nullable=False),
            sa.Column("max_tokens", sa.Integer(), nullable=False),
            sa.Column("timeout_seconds", sa.Integer(), nullable=False),
            sa.Column("cost_ceiling_minor_units", sa.Integer(), nullable=True),
            sa.Column("fallback_order_payload", sa.JSON(), nullable=False),
            sa.Column("status", sa.String(20), server_default="active", nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("profile_digest", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("revision > 0", name="ck_model_profiles_revision_positive"),
            sa.CheckConstraint("temperature >= 0", name="ck_model_profiles_temperature_non_negative"),
            sa.CheckConstraint("max_tokens > 0", name="ck_model_profiles_max_tokens_positive"),
            sa.CheckConstraint("timeout_seconds > 0", name="ck_model_profiles_timeout_positive"),
            sa.CheckConstraint(
                "cost_ceiling_minor_units IS NULL OR cost_ceiling_minor_units >= 0",
                name="ck_model_profiles_cost_non_negative",
            ),
            sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_model_profiles_status_valid"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("profile_key", "revision", name="uq_model_profiles_key_revision"),
            sa.UniqueConstraint("profile_digest", name="uq_model_profiles_digest"),
        )
    _create_index_if_missing(
        "model_profiles", "idx_model_profiles_key_status", ["profile_key", "status"]
    )

    tables = set(sa.inspect(bind).get_table_names())
    if "task_envelopes" not in tables:
        op.create_table(
            "task_envelopes",
            sa.Column("task_id", sa.Uuid(), nullable=False),
            sa.Column("request_id", sa.String(160), nullable=False),
            sa.Column("user_id", sa.Uuid(), nullable=False),
            sa.Column("mode", sa.String(20), nullable=False),
            sa.Column("capability_key", sa.String(160), nullable=False),
            sa.Column("state", sa.String(30), server_default="proposed", nullable=False),
            sa.Column("context_digest", sa.String(64), nullable=False),
            sa.Column("plan_digest", sa.String(64), nullable=True),
            sa.Column("content_digest", sa.String(64), nullable=True),
            sa.Column("effects_digest", sa.String(64), nullable=True),
            sa.Column("model_profile_id", sa.Uuid(), nullable=True),
            sa.Column("budget_payload", sa.JSON(), nullable=False),
            sa.Column("budget_digest", sa.String(64), nullable=False),
            sa.Column("required_scope_payload", sa.JSON(), nullable=False),
            sa.Column("scope_digest", sa.String(64), nullable=False),
            sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
            sa.Column("idempotency_key", sa.String(160), nullable=False),
            sa.Column("request_digest", sa.String(64), nullable=False),
            sa.Column("request_payload", sa.JSON(), nullable=False),
            sa.Column("approval_ref", sa.String(160), nullable=True),
            sa.Column("rollback_ref", sa.String(240), nullable=True),
            sa.Column("legacy_work_task_id", sa.Uuid(), nullable=True),
            sa.Column("revocation_epoch", sa.Integer(), server_default="0", nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("mode IN ('ask', 'plan', 'agent')", name="ck_task_envelopes_mode_valid"),
            sa.CheckConstraint(
                "state IN ('proposed', 'planned', 'approved', 'running', 'succeeded', 'failed', "
                "'unknown', 'hold', 'cancelled', 'reconcile_required')",
                name="ck_task_envelopes_state_valid",
            ),
            sa.CheckConstraint(
                "revocation_epoch >= 0", name="ck_task_envelopes_revocation_epoch_non_negative"
            ),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["model_profile_id"], ["model_profiles.id"], ondelete="RESTRICT"),
            sa.ForeignKeyConstraint(["legacy_work_task_id"], ["work_tasks.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("task_id"),
            sa.UniqueConstraint("idempotency_key", name="uq_task_envelopes_idempotency"),
            sa.UniqueConstraint("legacy_work_task_id", name="uq_task_envelopes_legacy_work_task"),
        )
    _create_index_if_missing(
        "task_envelopes", "idx_task_envelopes_user_created", ["user_id", "created_at"]
    )
    _create_index_if_missing("task_envelopes", "idx_task_envelopes_request_id", ["request_id"])
    _create_index_if_missing("task_envelopes", "idx_task_envelopes_state", ["state"])

    tables = set(sa.inspect(bind).get_table_names())
    if "task_approvals" not in tables:
        op.create_table(
            "task_approvals",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("approval_ref", sa.String(160), nullable=False),
            sa.Column("envelope_id", sa.Uuid(), nullable=False),
            sa.Column("plan_digest", sa.String(64), nullable=False),
            sa.Column("content_digest", sa.String(64), nullable=False),
            sa.Column("effects_digest", sa.String(64), nullable=False),
            sa.Column("scope_payload", sa.JSON(), nullable=False),
            sa.Column("scope_digest", sa.String(64), nullable=False),
            sa.Column("budget_payload", sa.JSON(), nullable=False),
            sa.Column("budget_digest", sa.String(64), nullable=False),
            sa.Column("approver", sa.String(160), nullable=False),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("revocation_epoch", sa.Integer(), nullable=False),
            sa.Column("approval_digest", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint(
                "revocation_epoch >= 0", name="ck_task_approvals_revocation_epoch_non_negative"
            ),
            sa.ForeignKeyConstraint(["envelope_id"], ["task_envelopes.task_id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("approval_ref", name="uq_task_approvals_ref"),
            sa.UniqueConstraint("approval_digest", name="uq_task_approvals_digest"),
        )
    _create_index_if_missing(
        "task_approvals", "idx_task_approvals_envelope_created", ["envelope_id", "created_at"]
    )

    tables = set(sa.inspect(bind).get_table_names())
    if "task_receipts" not in tables:
        op.create_table(
            "task_receipts",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("receipt_key", sa.String(100), nullable=False),
            sa.Column("envelope_id", sa.Uuid(), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("event_type", sa.String(60), nullable=False),
            sa.Column("from_state", sa.String(30), nullable=True),
            sa.Column("to_state", sa.String(30), nullable=False),
            sa.Column("actor", sa.String(160), nullable=False),
            sa.Column("payload", sa.JSON(), nullable=False),
            sa.Column("previous_receipt_digest", sa.String(64), nullable=True),
            sa.Column("receipt_digest", sa.String(64), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.CheckConstraint("sequence > 0", name="ck_task_receipts_sequence_positive"),
            sa.ForeignKeyConstraint(["envelope_id"], ["task_envelopes.task_id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("receipt_key", name="uq_task_receipts_key"),
            sa.UniqueConstraint("receipt_digest", name="uq_task_receipts_digest"),
            sa.UniqueConstraint(
                "envelope_id", "sequence", name="uq_task_receipts_envelope_sequence"
            ),
        )
    _create_index_if_missing(
        "task_receipts", "idx_task_receipts_envelope_created", ["envelope_id", "created_at"]
    )

    immutable_tables = (
        ("model_profiles", "af_model_profiles", "Model profiles are append-only"),
        ("task_approvals", "af_task_approvals", "Task approvals are append-only"),
        ("task_receipts", "af_task_receipts", "Task receipts are append-only"),
    )
    if bind.dialect.name == "sqlite":
        frozen_fields = (
            "request_id", "user_id", "mode", "capability_key", "context_digest",
            "plan_digest", "content_digest", "effects_digest", "model_profile_id",
            "budget_payload", "budget_digest", "required_scope_payload", "scope_digest",
            "deadline", "idempotency_key", "request_digest", "request_payload", "rollback_ref",
        )
        frozen_predicate = " OR ".join(
            f"NEW.{field} IS NOT OLD.{field}" for field in frozen_fields
        )
        op.execute(
            sa.text(
                "CREATE TRIGGER IF NOT EXISTS af_task_envelopes_frozen_fields "
                "BEFORE UPDATE ON task_envelopes FOR EACH ROW "
                f"WHEN {frozen_predicate} BEGIN "
                "SELECT RAISE(ABORT, 'Task envelope frozen fields cannot change'); END"
            )
        )
        for table_name, prefix, message in immutable_tables:
            for action in ("UPDATE", "DELETE"):
                op.execute(
                    sa.text(
                        f"CREATE TRIGGER IF NOT EXISTS {prefix}_no_{action.lower()} "
                        f"BEFORE {action} ON {table_name} BEGIN "
                        f"SELECT RAISE(ABORT, '{message}'); END"
                    )
                )
    elif bind.dialect.name == "postgresql":
        op.execute(
            sa.text(
                "CREATE OR REPLACE FUNCTION af_reject_task_envelope_frozen_mutation() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN "
                "IF ROW(NEW.request_id, NEW.user_id, NEW.mode, NEW.capability_key, NEW.context_digest, "
                "NEW.plan_digest, NEW.content_digest, NEW.effects_digest, NEW.model_profile_id, "
                "NEW.budget_payload, NEW.budget_digest, NEW.required_scope_payload, NEW.scope_digest, "
                "NEW.deadline, NEW.idempotency_key, NEW.request_digest, NEW.request_payload, NEW.rollback_ref) "
                "IS DISTINCT FROM ROW(OLD.request_id, OLD.user_id, OLD.mode, OLD.capability_key, OLD.context_digest, "
                "OLD.plan_digest, OLD.content_digest, OLD.effects_digest, OLD.model_profile_id, "
                "OLD.budget_payload, OLD.budget_digest, OLD.required_scope_payload, OLD.scope_digest, "
                "OLD.deadline, OLD.idempotency_key, OLD.request_digest, OLD.request_payload, OLD.rollback_ref) "
                "THEN RAISE EXCEPTION 'Task envelope frozen fields cannot change'; END IF; RETURN NEW; END; $$"
            )
        )
        op.execute(sa.text("DROP TRIGGER IF EXISTS af_task_envelopes_frozen_fields ON task_envelopes"))
        op.execute(
            sa.text(
                "CREATE TRIGGER af_task_envelopes_frozen_fields BEFORE UPDATE ON task_envelopes "
                "FOR EACH ROW EXECUTE FUNCTION af_reject_task_envelope_frozen_mutation()"
            )
        )
        op.execute(
            sa.text(
                "CREATE OR REPLACE FUNCTION af_reject_task_control_mutation() RETURNS trigger "
                "LANGUAGE plpgsql AS $$ BEGIN RAISE EXCEPTION 'Task control evidence is append-only'; END; $$"
            )
        )
        for table_name, prefix, _message in immutable_tables:
            trigger_name = f"{prefix}_immutable"
            op.execute(sa.text(f"DROP TRIGGER IF EXISTS {trigger_name} ON {table_name}"))
            op.execute(
                sa.text(
                    f"CREATE TRIGGER {trigger_name} BEFORE UPDATE OR DELETE ON {table_name} "
                    "FOR EACH ROW EXECUTE FUNCTION af_reject_task_control_mutation()"
                )
            )


def downgrade() -> None:
    # Feature-flag rollback must retain task, approval and receipt evidence.
    pass
