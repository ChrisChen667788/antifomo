"""add decision studio

Revision ID: 20260716_0026
Revises: 20260613_0025
Create Date: 2026-07-16 12:00:00.000000
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260716_0026"
down_revision = "20260613_0025"
branch_labels = None
depends_on = None


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def _updated_at() -> sa.Column:
    return sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False)


def upgrade() -> None:
    op.create_table(
        "decision_policy_packs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pack_key", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("authority", sa.String(length=160), server_default="", nullable=False),
        sa.Column("source_uri", sa.Text(), server_default="", nullable=False),
        sa.Column("document_kind", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="active", nullable=False),
        sa.Column("schema_payload", sa.JSON(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        _created_at(),
        _updated_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_policy_packs")),
        sa.UniqueConstraint("pack_key", "version", name="uq_decision_policy_pack_key_version"),
    )
    op.create_index(
        "idx_decision_policy_packs_kind_status",
        "decision_policy_packs",
        ["document_kind", "status"],
        unique=False,
    )
    op.create_table(
        "decision_knowledge_spaces",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("owner_user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("visibility", sa.String(length=20), server_default="private", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(
            ["owner_user_id"],
            ["users.id"],
            name=op.f("fk_decision_knowledge_spaces_owner_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_knowledge_spaces")),
    )
    op.create_index(
        "idx_decision_spaces_owner_updated",
        "decision_knowledge_spaces",
        ["owner_user_id", "updated_at"],
        unique=False,
    )
    op.create_table(
        "governed_skills",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("skill_key", sa.String(length=140), nullable=False),
        sa.Column("version", sa.String(length=40), nullable=False),
        sa.Column("publisher", sa.String(length=160), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="quarantine", nullable=False),
        sa.Column("manifest_payload", sa.JSON(), nullable=False),
        sa.Column("package_hash", sa.String(length=64), nullable=False),
        sa.Column("signature", sa.String(length=128), server_default="", nullable=False),
        sa.Column("signature_algorithm", sa.String(length=30), server_default="hmac-sha256", nullable=False),
        sa.Column("license_id", sa.String(length=80), server_default="", nullable=False),
        sa.Column("permissions_payload", sa.JSON(), nullable=False),
        sa.Column("benchmark_payload", sa.JSON(), nullable=False),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_governed_skills_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_governed_skills")),
        sa.UniqueConstraint("user_id", "skill_key", "version", name="uq_governed_skill_user_key_version"),
    )
    op.create_index("idx_governed_skills_user_status", "governed_skills", ["user_id", "status"], unique=False)
    op.create_table(
        "decision_connectors",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("space_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("connector_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("endpoint", sa.Text(), server_default="", nullable=False),
        sa.Column("permissions_payload", sa.JSON(), nullable=False),
        sa.Column("config_fingerprint", sa.String(length=64), server_default="", nullable=False),
        sa.Column("last_dry_run_payload", sa.JSON(), nullable=False),
        sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["decision_knowledge_spaces.id"],
            name=op.f("fk_decision_connectors_space_id_decision_knowledge_spaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_connectors")),
    )
    op.create_index(
        "idx_decision_connectors_space_status", "decision_connectors", ["space_id", "status"], unique=False
    )
    op.create_table(
        "decision_notebooks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("space_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(length=160), nullable=False),
        sa.Column("description", sa.Text(), server_default="", nullable=False),
        sa.Column("status", sa.String(length=20), server_default="active", nullable=False),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["decision_knowledge_spaces.id"],
            name=op.f("fk_decision_notebooks_space_id_decision_knowledge_spaces"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_decision_notebooks_user_id_users"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_notebooks")),
    )
    op.create_index(
        "idx_decision_notebooks_space_updated", "decision_notebooks", ["space_id", "updated_at"], unique=False
    )
    op.create_index(
        "idx_decision_notebooks_user_updated", "decision_notebooks", ["user_id", "updated_at"], unique=False
    )
    op.create_table(
        "decision_review_threads",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("space_id", sa.Uuid(), nullable=False),
        sa.Column("target_type", sa.String(length=40), nullable=False),
        sa.Column("target_id", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="open", nullable=False),
        sa.Column("comments_payload", sa.JSON(), nullable=False),
        sa.Column("decision", sa.String(length=30), server_default="pending", nullable=False),
        sa.Column("reviewer_id", sa.String(length=80), server_default="", nullable=False),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["decision_knowledge_spaces.id"],
            name=op.f("fk_decision_review_threads_space_id_decision_knowledge_spaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_review_threads")),
    )
    op.create_index(
        "idx_decision_reviews_space_status", "decision_review_threads", ["space_id", "status"], unique=False
    )
    op.create_table(
        "decision_space_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("space_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.String(length=80), nullable=False),
        sa.Column("role", sa.String(length=20), server_default="viewer", nullable=False),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(
            ["space_id"],
            ["decision_knowledge_spaces.id"],
            name=op.f("fk_decision_space_memberships_space_id_decision_knowledge_spaces"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_space_memberships")),
        sa.UniqueConstraint("space_id", "member_id", name="uq_decision_space_member"),
    )
    op.create_index(
        "idx_decision_space_members_member",
        "decision_space_memberships",
        ["member_id", "space_id"],
        unique=False,
    )
    op.create_table(
        "decision_artifacts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notebook_id", sa.Uuid(), nullable=False),
        sa.Column("artifact_type", sa.String(length=60), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("content_payload", sa.JSON(), nullable=False),
        sa.Column("source_revision_ids", sa.JSON(), nullable=False),
        sa.Column("claim_ids", sa.JSON(), nullable=False),
        sa.Column("dependency_hash", sa.String(length=64), nullable=False),
        sa.Column("consistency_hash", sa.String(length=64), nullable=False),
        sa.Column("stale", sa.Boolean(), server_default="0", nullable=False),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(
            ["notebook_id"],
            ["decision_notebooks.id"],
            name=op.f("fk_decision_artifacts_notebook_id_decision_notebooks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_artifacts")),
    )
    op.create_index(
        "idx_decision_artifacts_notebook_updated", "decision_artifacts", ["notebook_id", "updated_at"], unique=False
    )
    op.create_index(
        "idx_decision_artifacts_status_stale", "decision_artifacts", ["status", "stale"], unique=False
    )
    op.create_table(
        "decision_claims",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notebook_id", sa.Uuid(), nullable=False),
        sa.Column("claim_key", sa.String(length=120), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("criticality", sa.String(length=20), server_default="normal", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("passage_ids", sa.JSON(), nullable=False),
        sa.Column("depends_on_claim_ids", sa.JSON(), nullable=False),
        sa.Column("facts_payload", sa.JSON(), nullable=False),
        sa.Column("owner_label", sa.String(length=160), server_default="", nullable=False),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(
            ["notebook_id"],
            ["decision_notebooks.id"],
            name=op.f("fk_decision_claims_notebook_id_decision_notebooks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_claims")),
        sa.UniqueConstraint("notebook_id", "claim_key", name="uq_decision_claim_notebook_key"),
    )
    op.create_index(
        "idx_decision_claims_notebook_status", "decision_claims", ["notebook_id", "status"], unique=False
    )
    op.create_table(
        "decision_document_contracts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notebook_id", sa.Uuid(), nullable=False),
        sa.Column("policy_pack_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("document_kind", sa.String(length=60), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="draft", nullable=False),
        sa.Column("revision", sa.Integer(), server_default="1", nullable=False),
        sa.Column("fields_payload", sa.JSON(), nullable=False),
        sa.Column("assumptions_payload", sa.JSON(), nullable=False),
        sa.Column("calculations_payload", sa.JSON(), nullable=False),
        sa.Column("gaps_payload", sa.JSON(), nullable=False),
        sa.Column("policy_snapshot", sa.JSON(), nullable=False),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(
            ["notebook_id"],
            ["decision_notebooks.id"],
            name=op.f("fk_decision_document_contracts_notebook_id_decision_notebooks"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["policy_pack_id"],
            ["decision_policy_packs.id"],
            name=op.f("fk_decision_document_contracts_policy_pack_id_decision_policy_packs"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_document_contracts")),
    )
    op.create_index(
        "idx_decision_contracts_notebook_updated",
        "decision_document_contracts",
        ["notebook_id", "updated_at"],
        unique=False,
    )
    op.create_table(
        "decision_sources",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notebook_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("source_kind", sa.String(length=40), server_default="text", nullable=False),
        sa.Column("source_uri", sa.Text(), server_default="", nullable=False),
        sa.Column("mime_type", sa.String(length=120), server_default="text/plain", nullable=False),
        sa.Column("labels", sa.JSON(), nullable=False),
        sa.Column("admission_status", sa.String(length=30), server_default="accepted", nullable=False),
        sa.Column("current_revision_id", sa.Uuid(), nullable=True),
        sa.Column("owner_label", sa.String(length=160), server_default="", nullable=False),
        sa.Column("trust_status", sa.String(length=30), server_default="unverified", nullable=False),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(
            ["notebook_id"],
            ["decision_notebooks.id"],
            name=op.f("fk_decision_sources_notebook_id_decision_notebooks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_sources")),
    )
    op.create_index(
        "idx_decision_sources_admission", "decision_sources", ["notebook_id", "admission_status"], unique=False
    )
    op.create_index(
        "idx_decision_sources_notebook_updated", "decision_sources", ["notebook_id", "updated_at"], unique=False
    )
    op.create_table(
        "governed_skill_runs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("skill_id", sa.Uuid(), nullable=False),
        sa.Column("notebook_id", sa.Uuid(), nullable=True),
        sa.Column("actor_id", sa.String(length=80), nullable=False),
        sa.Column("mode", sa.String(length=20), server_default="dry_run", nullable=False),
        sa.Column("status", sa.String(length=30), server_default="planned", nullable=False),
        sa.Column("plan_payload", sa.JSON(), nullable=False),
        sa.Column("requested_permissions", sa.JSON(), nullable=False),
        sa.Column("granted_permissions", sa.JSON(), nullable=False),
        sa.Column("result_payload", sa.JSON(), nullable=False),
        sa.Column("violations_payload", sa.JSON(), nullable=False),
        _created_at(),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(
            ["notebook_id"],
            ["decision_notebooks.id"],
            name=op.f("fk_governed_skill_runs_notebook_id_decision_notebooks"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["skill_id"],
            ["governed_skills.id"],
            name=op.f("fk_governed_skill_runs_skill_id_governed_skills"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_governed_skill_runs")),
    )
    op.create_index(
        "idx_governed_skill_runs_skill_created", "governed_skill_runs", ["skill_id", "created_at"], unique=False
    )
    op.create_table(
        "decision_sections",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notebook_id", sa.Uuid(), nullable=False),
        sa.Column("contract_id", sa.Uuid(), nullable=True),
        sa.Column("section_key", sa.String(length=120), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("status", sa.String(length=30), server_default="waiting", nullable=False),
        sa.Column("claim_ids", sa.JSON(), nullable=False),
        sa.Column("content", sa.Text(), server_default="", nullable=False),
        sa.Column("dependency_hash", sa.String(length=64), server_default="", nullable=False),
        sa.Column("build_version", sa.Integer(), server_default="0", nullable=False),
        sa.Column("findings_payload", sa.JSON(), nullable=False),
        sa.Column("last_built_at", sa.DateTime(timezone=True), nullable=True),
        _created_at(),
        _updated_at(),
        sa.ForeignKeyConstraint(
            ["contract_id"],
            ["decision_document_contracts.id"],
            name=op.f("fk_decision_sections_contract_id_decision_document_contracts"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["notebook_id"],
            ["decision_notebooks.id"],
            name=op.f("fk_decision_sections_notebook_id_decision_notebooks"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_sections")),
        sa.UniqueConstraint("notebook_id", "section_key", name="uq_decision_section_notebook_key"),
    )
    op.create_index(
        "idx_decision_sections_notebook_status", "decision_sections", ["notebook_id", "status"], unique=False
    )
    op.create_table(
        "decision_source_revisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("source_id", sa.Uuid(), nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("parser_name", sa.String(length=80), nullable=False),
        sa.Column("parser_version", sa.String(length=40), server_default="1", nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("metadata_payload", sa.JSON(), nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["decision_sources.id"],
            name=op.f("fk_decision_source_revisions_source_id_decision_sources"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_source_revisions")),
        sa.UniqueConstraint("source_id", "revision_number", name="uq_decision_source_revision_number"),
    )
    op.create_index(
        "idx_decision_source_revisions_source_created",
        "decision_source_revisions",
        ["source_id", "created_at"],
        unique=False,
    )
    op.create_table(
        "decision_passages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("revision_id", sa.Uuid(), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("paragraph_number", sa.Integer(), nullable=True),
        sa.Column("start_seconds", sa.Integer(), nullable=True),
        sa.Column("end_seconds", sa.Integer(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("locator_payload", sa.JSON(), nullable=False),
        sa.Column("embedding", sa.JSON(), nullable=False),
        sa.Column("embedding_model", sa.String(length=160), server_default="", nullable=False),
        _created_at(),
        sa.ForeignKeyConstraint(
            ["revision_id"],
            ["decision_source_revisions.id"],
            name=op.f("fk_decision_passages_revision_id_decision_source_revisions"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_decision_passages")),
        sa.UniqueConstraint("revision_id", "sequence", name="uq_decision_passage_revision_sequence"),
    )
    op.create_index(
        "idx_decision_passages_revision_sequence", "decision_passages", ["revision_id", "sequence"], unique=False
    )


def downgrade() -> None:
    for table_name in (
        "decision_passages",
        "decision_source_revisions",
        "decision_sections",
        "governed_skill_runs",
        "decision_sources",
        "decision_document_contracts",
        "decision_claims",
        "decision_artifacts",
        "decision_space_memberships",
        "decision_review_threads",
        "decision_notebooks",
        "decision_connectors",
        "governed_skills",
        "decision_knowledge_spaces",
        "decision_policy_packs",
    ):
        op.drop_table(table_name)
