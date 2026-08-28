"""add decision program operations

Revision ID: 20260718_0028
Revises: 20260716_0027
Create Date: 2026-07-18 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260718_0028"
down_revision = "20260716_0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "decision_release_candidates",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=20), server_default="2.0.7", nullable=False),
        sa.Column("build_digest", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="frozen", nullable=False),
        sa.Column("manifest_payload", sa.JSON(), nullable=False),
        sa.Column("validation_run_ids", sa.JSON(), nullable=False),
        sa.Column("external_attestations_payload", sa.JSON(), nullable=False),
        sa.Column("evidence_snapshot_payload", sa.JSON(), nullable=False),
        sa.Column("blockers_payload", sa.JSON(), nullable=False),
        sa.Column("frozen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "version", "build_digest", name="uq_decision_release_candidate_digest"),
    )
    op.create_index(
        "idx_decision_release_candidates_user_status",
        "decision_release_candidates",
        ["user_id", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "decision_research_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("notebook_id", sa.Uuid(), nullable=False),
        sa.Column("run_key", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("brief_payload", sa.JSON(), nullable=False),
        sa.Column("question_tree_payload", sa.JSON(), nullable=False),
        sa.Column("source_decisions_payload", sa.JSON(), nullable=False),
        sa.Column("source_snapshot_payload", sa.JSON(), nullable=False),
        sa.Column("checkpoint_payload", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("audit_payload", sa.JSON(), nullable=False),
        sa.Column("plan_hash", sa.String(length=64), server_default="", nullable=False),
        sa.Column("budget_fen", sa.Integer(), server_default="0", nullable=False),
        sa.Column("spent_fen", sa.Integer(), server_default="0", nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["notebook_id"], ["decision_notebooks.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "run_key", name="uq_decision_research_run_key"),
    )
    op.create_index(
        "idx_decision_research_runs_notebook_status",
        "decision_research_runs",
        ["notebook_id", "status", "updated_at"],
        unique=False,
    )

    op.create_table(
        "decision_quality_benchmarks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("benchmark_key", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("benchmark_kind", sa.String(length=30), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("incumbent", sa.String(length=160), server_default="", nullable=False),
        sa.Column("challenger", sa.String(length=160), server_default="", nullable=False),
        sa.Column("case_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("corpus_digest", sa.String(length=64), nullable=False),
        sa.Column("configuration_payload", sa.JSON(), nullable=False),
        sa.Column("metrics_payload", sa.JSON(), nullable=False),
        sa.Column("findings_payload", sa.JSON(), nullable=False),
        sa.Column("source_artifact_uri", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "benchmark_key", "version", name="uq_decision_quality_benchmark_version"),
    )
    op.create_index(
        "idx_decision_quality_benchmarks_kind_status",
        "decision_quality_benchmarks",
        ["benchmark_kind", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "decision_document_drafts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notebook_id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=True),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("document_kind", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("blocks_payload", sa.JSON(), nullable=False),
        sa.Column("revision_history_payload", sa.JSON(), nullable=False),
        sa.Column("dependency_hash", sa.String(length=64), nullable=False),
        sa.Column("export_profile_payload", sa.JSON(), nullable=False),
        sa.Column("last_export_payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["contract_id"], ["decision_document_contracts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["notebook_id"], ["decision_notebooks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_decision_document_drafts_notebook_status",
        "decision_document_drafts",
        ["notebook_id", "status", "updated_at"],
        unique=False,
    )

    op.create_table(
        "decision_identity_profiles",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("space_id", sa.Uuid(), nullable=False),
        sa.Column("provider_type", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("issuer_uri", sa.Text(), nullable=False),
        sa.Column("client_id_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("tenant_key", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("role_mapping_payload", sa.JSON(), nullable=False),
        sa.Column("allowed_domains_payload", sa.JSON(), nullable=False),
        sa.Column("retention_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column("validation_payload", sa.JSON(), nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["space_id"], ["decision_knowledge_spaces.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("space_id", "provider_type", "tenant_key", name="uq_decision_identity_provider_tenant"),
    )
    op.create_index(
        "idx_decision_identity_profiles_space_status",
        "decision_identity_profiles",
        ["space_id", "status"],
        unique=False,
    )

    op.create_table(
        "decision_connector_sync_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("connector_id", sa.Uuid(), nullable=False),
        sa.Column("actor_id", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("mode", sa.String(length=20), server_default="dry_run", nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("cursor_before", sa.String(length=400), server_default="", nullable=False),
        sa.Column("cursor_after", sa.String(length=400), server_default="", nullable=False),
        sa.Column("resource_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("applied_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("deleted_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("acl_snapshot_payload", sa.JSON(), nullable=False),
        sa.Column("findings_payload", sa.JSON(), nullable=False),
        sa.Column("snapshot_digest", sa.String(length=64), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["connector_id"], ["decision_connectors.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("connector_id", "idempotency_key", name="uq_decision_connector_sync_idempotency"),
    )
    op.create_index(
        "idx_decision_connector_sync_connector_status",
        "decision_connector_sync_runs",
        ["connector_id", "status", "created_at"],
        unique=False,
    )

    op.create_table(
        "decision_agent_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("notebook_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=120), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="planned", nullable=False),
        sa.Column("plan_payload", sa.JSON(), nullable=False),
        sa.Column("checkpoints_payload", sa.JSON(), nullable=False),
        sa.Column("current_step", sa.Integer(), server_default="0", nullable=False),
        sa.Column("budget_fen", sa.Integer(), server_default="0", nullable=False),
        sa.Column("spent_fen", sa.Integer(), server_default="0", nullable=False),
        sa.Column("requested_permissions", sa.JSON(), nullable=False),
        sa.Column("granted_permissions", sa.JSON(), nullable=False),
        sa.Column("effect_preview_payload", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("audit_payload", sa.JSON(), nullable=False),
        sa.Column("scheduled_for", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["notebook_id"], ["decision_notebooks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["skill_id"], ["governed_skills.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("actor_id", "idempotency_key", name="uq_decision_agent_run_idempotency"),
    )
    op.create_index(
        "idx_decision_agent_runs_status_schedule",
        "decision_agent_runs",
        ["status", "scheduled_for"],
        unique=False,
    )

    op.create_table(
        "decision_agent_approvals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("run_id", sa.Uuid(), nullable=False),
        sa.Column("step_key", sa.String(length=120), nullable=False),
        sa.Column("action_class", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("requested_by", sa.String(length=80), nullable=False),
        sa.Column("reviewer_id", sa.String(length=80), server_default="", nullable=False),
        sa.Column("input_digest", sa.String(length=64), nullable=False),
        sa.Column("decision_note", sa.Text(), server_default="", nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["run_id"], ["decision_agent_runs.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("run_id", "step_key", name="uq_decision_agent_approval_step"),
    )
    op.create_index(
        "idx_decision_agent_approvals_status",
        "decision_agent_approvals",
        ["status", "requested_at"],
        unique=False,
    )

    op.create_table(
        "decision_vertical_packs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pack_key", sa.String(length=120), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("sector", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("source_registry_payload", sa.JSON(), nullable=False),
        sa.Column("ontology_payload", sa.JSON(), nullable=False),
        sa.Column("contract_payload", sa.JSON(), nullable=False),
        sa.Column("hard_negatives_payload", sa.JSON(), nullable=False),
        sa.Column("review_rubric_payload", sa.JSON(), nullable=False),
        sa.Column("licensing_payload", sa.JSON(), nullable=False),
        sa.Column("benchmark_payload", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pack_key", "version", name="uq_decision_vertical_pack_version"),
    )
    op.create_index(
        "idx_decision_vertical_packs_sector_status",
        "decision_vertical_packs",
        ["sector", "status"],
        unique=False,
    )

    op.create_table(
        "decision_customer_pilots",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("space_id", sa.Uuid(), nullable=False),
        sa.Column("vertical_pack_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("customer_label", sa.String(length=200), nullable=False),
        sa.Column("sector", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="planned", nullable=False),
        sa.Column("owner_label", sa.String(length=160), nullable=False),
        sa.Column("deployment_profile_payload", sa.JSON(), nullable=False),
        sa.Column("sla_payload", sa.JSON(), nullable=False),
        sa.Column("workflow_evidence_payload", sa.JSON(), nullable=False),
        sa.Column("acceptance_payload", sa.JSON(), nullable=False),
        sa.Column("customer_signer", sa.String(length=160), server_default="", nullable=False),
        sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["space_id"], ["decision_knowledge_spaces.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["vertical_pack_id"], ["decision_vertical_packs.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_decision_customer_pilots_space_status",
        "decision_customer_pilots",
        ["space_id", "status", "updated_at"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("idx_decision_customer_pilots_space_status", table_name="decision_customer_pilots")
    op.drop_table("decision_customer_pilots")
    op.drop_index("idx_decision_vertical_packs_sector_status", table_name="decision_vertical_packs")
    op.drop_table("decision_vertical_packs")
    op.drop_index("idx_decision_agent_approvals_status", table_name="decision_agent_approvals")
    op.drop_table("decision_agent_approvals")
    op.drop_index("idx_decision_agent_runs_status_schedule", table_name="decision_agent_runs")
    op.drop_table("decision_agent_runs")
    op.drop_index("idx_decision_connector_sync_connector_status", table_name="decision_connector_sync_runs")
    op.drop_table("decision_connector_sync_runs")
    op.drop_index("idx_decision_identity_profiles_space_status", table_name="decision_identity_profiles")
    op.drop_table("decision_identity_profiles")
    op.drop_index("idx_decision_document_drafts_notebook_status", table_name="decision_document_drafts")
    op.drop_table("decision_document_drafts")
    op.drop_index("idx_decision_quality_benchmarks_kind_status", table_name="decision_quality_benchmarks")
    op.drop_table("decision_quality_benchmarks")
    op.drop_index("idx_decision_research_runs_notebook_status", table_name="decision_research_runs")
    op.drop_table("decision_research_runs")
    op.drop_index("idx_decision_release_candidates_user_status", table_name="decision_release_candidates")
    op.drop_table("decision_release_candidates")
