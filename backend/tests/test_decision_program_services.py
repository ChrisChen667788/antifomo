from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app import models  # noqa: F401
from app.db.base import Base
from app.models.decision_program_entities import DecisionReleaseCandidate
from app.models.decision_studio_entities import DecisionPassage
from app.models.entities import User
from app.services.decision_program.agent_operations import (
    create_agent_run,
    decide_agent_approval,
    list_agent_approvals,
    transition_agent_run,
)
from app.services.decision_program.commercial import create_customer_pilot, update_customer_pilot
from app.services.decision_program.control_room import create_research_run, revise_research_run_plan, transition_research_run
from app.services.decision_program.document_editor import (
    create_document_draft,
    confirm_document_export,
    export_document_draft,
    regenerate_document_blocks,
    update_document_block,
)
from app.services.decision_program.enterprise import create_identity_profile, record_connector_sync
from app.services.decision_program.quality import evaluate_quality_benchmark, record_quality_benchmark
from app.services.decision_program.release_candidates import (
    freeze_release_candidate,
    preview_release_candidate,
    release_build_digest,
)
from app.services.decision_program.verticals import record_vertical_pack_benchmark, seed_vertical_packs
from app.services.decision_studio.claim_graph import create_claim
from app.services.decision_studio.notebooks import create_notebook, create_source_revision, update_source_trust
from app.services.decision_studio.skills import (
    approve_skill,
    ensure_first_party_skills,
    record_skill_benchmark,
    sign_skill,
)
from app.services.decision_studio.spaces import create_connector, create_space
from app.services.decision_studio.validation import record_validation_run


@contextmanager
def _session() -> Generator[Session, None, None]:
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        future=True,
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, future=True, autoflush=False, autocommit=False)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


def _user(db: Session) -> User:
    user = User(id=uuid4(), name="Decision Program Test", email=f"program-{uuid4()}@example.test")
    db.add(user)
    db.commit()
    return user


def _notebook_claim(db: Session, user: User):
    notebook = create_notebook(db, user_id=user.id, name="文旅决策工作台")
    source, revision, _parsed, _stale = create_source_revision(
        db,
        notebook_id=notebook.id,
        title="文旅项目官方资料",
        data="项目客流和投资假设需要逐项核验。".encode("utf-8"),
        file_name="tourism.txt",
        mime_type="text/plain",
    )
    update_source_trust(
        db,
        source=source,
        trust_status="verified",
        owner_label="official-source-owner",
        expires_at=None,
    )
    passage = db.scalar(select(DecisionPassage).where(DecisionPassage.revision_id == revision.id))
    assert passage is not None
    claim = create_claim(
        db,
        notebook_id=notebook.id,
        claim_key="verified-demand",
        text="项目需求成立，但投资收益仍需情景验证。",
        criticality="critical",
        status="accepted",
        passage_ids=[passage.id],
        depends_on_claim_ids=[],
        facts={"evidence_state": "verified"},
        owner_label="analyst",
    )
    return notebook, source, claim


def test_release_candidate_is_immutable_and_stays_blocked_without_real_evidence() -> None:
    with _session() as db:
        user = _user(db)
        manifest = {"git_commit": "abc123", "artifact_manifest": "artifact://build/manifest.json"}
        digest = release_build_digest(version="2.0.7", manifest=manifest)
        validation = record_validation_run(
            db,
            user_id=user.id,
            suite_key="real_data_activation",
            metrics={
                "candidate_count": 1,
                "created_source_count": 1,
                "updated_source_count": 0,
                "unchanged_source_count": 0,
                "failed_source_count": 0,
                "provenance_source_count": 1,
            },
            evidence={"release_candidate_digest": digest},
        )
        preview = preview_release_candidate(
            db,
            user_id=user.id,
            version="2.0.7",
            manifest=manifest,
            validation_run_ids=[validation.id],
            external_attestations={},
        )
        assert preview["build_digest"] == digest
        assert preview["persisted"] is False
        assert db.scalar(select(DecisionReleaseCandidate)) is None
        candidate = freeze_release_candidate(
            db,
            user_id=user.id,
            version="2.0.7",
            manifest=manifest,
            validation_run_ids=[validation.id],
            external_attestations={},
        )
        assert candidate.status == "frozen"
        assert candidate.evidence_snapshot_payload["acceptance_status"] == "blocked"
        assert any("专家校准" in blocker for blocker in candidate.blockers_payload)
        assert any("缺少冻结验证记录" in blocker for blocker in candidate.blockers_payload)

        same = freeze_release_candidate(
            db,
            user_id=user.id,
            version="2.0.7",
            manifest=manifest,
            validation_run_ids=[],
            external_attestations={"expert_calibration": {"reviewer_id": "late-change"}},
        )
        assert same.id == candidate.id
        assert same.external_attestations_payload == {}


def test_research_control_room_requires_approval_snapshot_and_budget() -> None:
    with _session() as db:
        user = _user(db)
        notebook, _source, _claim = _notebook_claim(db, user)
        run = create_research_run(
            db,
            user_id=user.id,
            actor_id=str(user.id),
            notebook_id=notebook.id,
            run_key="tourism-run-001",
            title="文旅投资决策研究",
            brief={"decision": "是否进入样机阶段"},
            question_tree=[{"key": "market", "question": "需求是否真实"}],
            source_decisions=[{"source_class": "official", "policy": "required"}],
            budget_fen=100,
        )
        original_hash = run.plan_hash
        revise_research_run_plan(
            db,
            run=run,
            actor_id=str(user.id),
            expected_plan_hash=original_hash,
            title="文旅投资决策研究（修订）",
            brief={"decision": "是否进入样机阶段", "audience": "项目决策委员会"},
            question_tree=[{"key": "market", "question": "需求与支付意愿是否真实"}],
            source_decisions=[{"source_class": "official", "decision": "locked", "reason": "关键政策来源"}],
            budget_fen=100,
        )
        assert run.plan_hash != original_hash
        with pytest.raises(ValueError, match="not allowed"):
            transition_research_run(db, run=run, actor_id=str(user.id), action="start")
        transition_research_run(
            db,
            run=run,
            actor_id=str(user.id),
            action="approve",
            expected_plan_hash=run.plan_hash,
        )
        assert run.source_snapshot_payload[0]["revision_id"]
        transition_research_run(db, run=run, actor_id=str(user.id), action="start")
        transition_research_run(
            db,
            run=run,
            actor_id=str(user.id),
            action="checkpoint",
            spend_fen=30,
            checkpoint={"stage": "retrieval"},
        )
        with pytest.raises(ValueError, match="budget"):
            transition_research_run(
                db,
                run=run,
                actor_id=str(user.id),
                action="complete",
                spend_fen=80,
                result={"decision": "hold"},
            )
        transition_research_run(
            db,
            run=run,
            actor_id=str(user.id),
            action="complete",
            spend_fen=60,
            result={"decision": "hold", "confidence": 0.7},
        )
        assert run.status == "completed"
        assert run.spent_fen == 90


def test_quality_benchmarks_apply_2_1_1_hard_thresholds() -> None:
    metrics = {
        "ndcg_at_10": 0.83,
        "recall_at_20": 0.93,
        "critical_cross_industry_false_positive_rate": 0.005,
        "clickback_rate": 0.995,
    }
    status, findings = evaluate_quality_benchmark(
        benchmark_kind="retrieval",
        case_count=599,
        metrics=metrics,
        source_artifact_uri="artifact://qrels.json",
    )
    assert status == "blocked"
    assert next(row for row in findings if row["key"] == "case_count")["status"] == "blocked"

    with _session() as db:
        user = _user(db)
        row = record_quality_benchmark(
            db,
            user_id=user.id,
            benchmark_key="retrieval-cn-three-sector",
            version="1.0.0",
            benchmark_kind="retrieval",
            incumbent="semantic-only",
            challenger="hybrid-rrf",
            case_count=600,
            corpus_digest="a" * 64,
            configuration={"human_qrels": True},
            metrics=metrics,
            source_artifact_uri="artifact://qrels.json",
        )
        assert row.status == "pass"


def test_document_editor_preserves_human_blocks_and_exports_real_openxml() -> None:
    with _session() as db:
        user = _user(db)
        notebook, _source, claim = _notebook_claim(db, user)
        draft = create_document_draft(
            db,
            notebook_id=notebook.id,
            contract_id=None,
            title="文旅项目决策建议书",
            document_kind="project_proposal",
        )
        block_key = draft.blocks_payload[0]["block_key"]
        update_document_block(
            db,
            draft=draft,
            expected_revision=1,
            block_key=block_key,
            title="人工结论",
            content="保留这段人工判断。",
            source_refs=[str(value) for value in claim.passage_ids],
            actor_id=str(user.id),
        )
        claim.text = "上游 Claim 已更新。"
        db.commit()
        regenerate_document_blocks(
            db,
            draft=draft,
            expected_revision=2,
            changed_claim_ids=[claim.id],
            actor_id=str(user.id),
        )
        assert draft.blocks_payload[0]["content"] == "保留这段人工判断。"
        assert draft.blocks_payload[0]["owner"] == "human"
        assert draft.blocks_payload[0]["stale"] is True
        with pytest.raises(ValueError, match="stale human blocks"):
            export_document_draft(db, draft=draft, export_format="docx", brand_template={})

        update_document_block(
            db,
            draft=draft,
            expected_revision=3,
            block_key=block_key,
            title="人工结论",
            content="保留这段人工判断，并已复核上游变化。",
            source_refs=[str(value) for value in claim.passage_ids],
            actor_id=str(user.id),
        )
        filename, mime, artifact, metadata = export_document_draft(
            db,
            draft=draft,
            export_format="docx",
            brand_template={},
        )
        assert filename.endswith(".docx")
        assert "wordprocessingml" in mime
        assert artifact.startswith(b"PK")
        assert metadata["status"] == "pass"
        assert metadata["manual_visual_confirmation_required"] is True
        with pytest.raises(ValueError, match="independent reviewer"):
            confirm_document_export(
                db,
                draft=draft,
                owner_user_id=user.id,
                actor_id=str(user.id),
                artifact_digest=metadata["artifact_digest"],
                reviewer_id=str(user.id),
                artifact_uri="artifact://office/review.pdf",
                reviewed_at=datetime.now(UTC),
                note="I reviewed the document in Microsoft Word and confirmed the visual baseline.",
            )
        confirm_document_export(
            db,
            draft=draft,
            owner_user_id=user.id,
            actor_id="independent-office-reviewer",
            artifact_digest=metadata["artifact_digest"],
            reviewer_id="independent-office-reviewer",
            artifact_uri="artifact://office/review.pdf",
            reviewed_at=datetime.now(UTC),
            note="I reviewed the document in Microsoft Word and confirmed the visual baseline.",
        )
        assert draft.last_export_payload["manual_visual_confirmation"]["status"] == "pass"


def test_enterprise_identity_and_connector_sync_reject_secrets() -> None:
    with _session() as db:
        user = _user(db)
        space = create_space(db, owner_user_id=user.id, name="Enterprise", description="", visibility="private")
        profile = create_identity_profile(
            db,
            space_id=space.id,
            provider_type="microsoft_entra",
            name="Corporate Entra",
            issuer_uri="https://login.microsoftonline.com/example/v2.0",
            client_id="public-client-id",
            tenant_key="example",
            role_mapping={"researchers": "editor"},
            allowed_domains=["example.com"],
            retention_days=90,
        )
        assert profile.client_id_fingerprint != "public-client-id"
        assert profile.validation_payload["credentials_persisted"] is False
        connector = create_connector(
            db,
            space_id=space.id,
            name="SharePoint",
            connector_type="sharepoint",
            endpoint="https://example.com/sites/research",
            permissions=["read:documents"],
        )
        connector.status = "ready"
        db.commit()
        with pytest.raises(ValueError, match="credentials"):
            record_connector_sync(
                db,
                connector=connector,
                actor_id=str(user.id),
                idempotency_key="sync-secret-001",
                mode="dry_run",
                cursor_before="",
                resources=[{"id": "doc-1", "token": "forbidden"}],
                acl_snapshot=[{"resource_id": "doc-1", "roles": ["reader"]}],
            )
        sync = record_connector_sync(
            db,
            connector=connector,
            actor_id=str(user.id),
            idempotency_key="sync-apply-001",
            mode="apply",
            cursor_before="cursor-0",
            resources=[{"id": "doc-1", "title": "Policy"}],
            acl_snapshot=[{"resource_id": "doc-1", "roles": ["reader"]}],
        )
        assert sync.status == "applied"
        assert sync.applied_count == 1


def test_governed_agent_requires_high_risk_approval_and_checkpoints() -> None:
    with _session() as db:
        user = _user(db)
        notebook, _source, _claim = _notebook_claim(db, user)
        skill = next(row for row in ensure_first_party_skills(db, user_id=user.id) if row.skill_key == "evidence-and-entity-auditor")
        sign_skill(db, skill=skill, signing_key="test-signing-key")
        record_skill_benchmark(db, skill=skill, score=0.95, case_count=100, evidence_ref="artifact://skill-benchmark.json")
        approve_skill(db, skill=skill, signing_key="test-signing-key")
        permissions = list(skill.permissions_payload)
        run = create_agent_run(
            db,
            skill=skill,
            notebook_id=notebook.id,
            actor_id=str(user.id),
            idempotency_key="agent-run-001",
            plan={
                "steps": [
                    {"step_key": "audit", "action_class": "read", "estimated_cost_fen": 10},
                    {"step_key": "publish", "action_class": "network", "estimated_cost_fen": 10},
                ]
            },
            requested_permissions=permissions,
            granted_permissions=permissions,
            budget_fen=30,
            scheduled_for=None,
        )
        approval = list_agent_approvals(db, run_id=run.id)[0]
        transition_agent_run(
            db,
            run=run,
            skill=skill,
            actor_id=str(user.id),
            action="start",
            spend_fen=0,
            step_result={},
        )
        transition_agent_run(
            db,
            run=run,
            skill=skill,
            actor_id=str(user.id),
            action="advance",
            spend_fen=10,
            step_result={"audited": True},
        )
        with pytest.raises(ValueError, match="requires an approved decision"):
            transition_agent_run(
                db,
                run=run,
                skill=skill,
                actor_id=str(user.id),
                action="advance",
                spend_fen=10,
                step_result={"published": False},
            )
        decide_agent_approval(
            db,
            approval=approval,
            reviewer_id="independent-security-reviewer",
            decision="approved",
            note="Approved after checking destination and payload digest.",
        )
        transition_agent_run(
            db,
            run=run,
            skill=skill,
            actor_id=str(user.id),
            action="advance",
            spend_fen=10,
            step_result={"published": False, "reason": "checkpoint only"},
        )
        assert run.status == "completed"
        assert len(run.checkpoints_payload) == 2
        assert run.result_payload["external_effects_executed"] is False
        transition_agent_run(
            db,
            run=run,
            skill=skill,
            actor_id=str(user.id),
            action="rollback",
            spend_fen=0,
            step_result={},
        )
        assert run.status == "rolled_back"


def test_vertical_pack_gate_and_customer_pilot_inherit_release_blocker() -> None:
    with _session() as db:
        user = _user(db)
        packs = seed_vertical_packs(db)
        assert {row.status for row in packs} == {"validation_pending"}
        pack = packs[2]
        record_vertical_pack_benchmark(
            db,
            pack=pack,
            task_count=100,
            expert_review_count=30,
            pass_rate=0.91,
            critical_error_count=0,
            artifact_uri="artifact://tourism/expert-review.json",
        )
        assert pack.status == "active"

        space = create_space(db, owner_user_id=user.id, name="Pilot", description="", visibility="private")
        pilot = create_customer_pilot(
            db,
            space_id=space.id,
            vertical_pack_id=pack.id,
            name="文旅客户试点",
            customer_label="客户 A",
            sector="tourism",
            owner_label="delivery-owner",
            deployment_profile={"mode": "private"},
            sla={"availability": "99.5%"},
        )
        update_customer_pilot(
            db,
            pilot=pilot,
            user_id=user.id,
            action="start",
            workflow_evidence={},
            acceptance={},
            customer_signer="",
        )
        evidence = {
            key: {"status": "pass", "artifact_uri": f"artifact://pilot/{key}.json"}
            for key in ("source_ingest", "research_run", "decision_document", "office_roundtrip", "audit_export", "recovery_drill")
        }
        update_customer_pilot(
            db,
            pilot=pilot,
            user_id=user.id,
            action="record_evidence",
            workflow_evidence=evidence,
            acceptance={},
            customer_signer="",
        )
        update_customer_pilot(
            db,
            pilot=pilot,
            user_id=user.id,
            action="request_acceptance",
            workflow_evidence={},
            acceptance={"requested_by": "delivery-owner"},
            customer_signer="",
        )
        with pytest.raises(ValueError, match="2.0.7 release candidate"):
            update_customer_pilot(
                db,
                pilot=pilot,
                user_id=user.id,
                action="signoff",
                workflow_evidence={},
                acceptance={"decision": "accepted", "artifact_uri": "artifact://pilot/signoff.pdf"},
                customer_signer="customer-signer",
            )
        assert pilot.status == "acceptance_pending"
