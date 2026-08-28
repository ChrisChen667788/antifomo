from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from uuid import UUID, uuid4

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.decision_studio_entities import DecisionSource, DecisionValidationRun
from app.models.entities import KnowledgeEntry, User
from app.models.research_entities import ResearchJob
from app.services.decision_studio.activation import preview_data_activation, run_data_activation
from app.services.decision_studio.validation import (
    SUITE_SPECS,
    build_release_program_snapshot,
    build_validation_audit_export,
    preview_validation_run,
    record_validation_run,
)


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
    user = User(id=uuid4(), name="Release Program", email="release@example.test")
    db.add(user)
    db.commit()
    return user


def _external(user_id: UUID) -> dict:
    return {
        "user_id": user_id,
        "reviewer_id": "independent-reviewer-001",
        "reviewer_role": "industry-expert",
        "attestation": "I independently reviewed the raw cases and confirm this result.",
        "source_artifact_uri": "artifact://decision-studio/review/run-001.json",
        "reviewed_at": datetime.now(UTC),
    }


def _passing_payloads() -> dict[str, dict]:
    retrieval_cases = []
    for domain in ("medical", "finance", "tourism"):
        for index in range(100):
            passage = f"{domain}-p-{index}"
            source = f"{domain}-s-{index}"
            retrieval_cases.append(
                {
                    "domain": domain,
                    "relevant_passage_ids": [passage],
                    "ranked_passage_ids": [passage, "noise"],
                    "baseline_ranked_passage_ids": ["noise", passage],
                    "included_source_ids": [source],
                    "returned_source_ids": [source],
                    "source_scope_required": True,
                    "clickback_ok": True,
                }
            )
    parser_cases = [
        {
            "order_preserved": True,
            "tables_preserved": True,
            "locator_clickback_ok": True,
            "extracted_text": f"document-{index}",
        }
        for index in range(100)
    ]
    documents = [
        {
            "document_kind": kind,
            "outline_complete": True,
            "unsourced_number_count": 0,
            "formula_count": 2,
            "formula_lineage_count": 2,
        }
        for kind in ("government_fsr", "enterprise_fsr", "project_proposal")
        for _index in range(20)
    ]
    reports = [
        {
            "independently_reviewed": True,
            "low_quality": index < 10,
            "actual_undeliverable": index < 10,
            "predicted_undeliverable": index < 10,
        }
        for index in range(100)
    ]
    entities = [
        {
            "predicted_real": index < 452,
            "actual_real": index < 450,
        }
        for index in range(500)
    ]
    permission_cases = [
        {
            "surface": surface,
            "expected_allowed": index % 2 == 0,
            "observed_allowed": index % 2 == 0,
            "resource_leaked": False,
            "credential_exposed": False,
        }
        for surface in ("search", "chat", "cache", "export", "deep_link")
        for index in range(5)
    ]
    skills = [
        {
            "signature_valid": True,
            "license_id": "Apache-2.0",
            "approved": True,
            "benchmark_score": 0.95,
            "injection_undeclared_action_count": 0,
            "least_privilege_violation_count": 0,
        }
        for _index in range(5)
    ]
    office_cases = [
        {"format": format_name, "theme": theme, "roundtrip_ok": True, "visual_approved": True}
        for format_name in ("docx", "xlsx", "pptx")
        for theme in ("light", "dark")
    ]
    return {
        "real_data_activation": {
            "candidate_count": 2,
            "created_source_count": 2,
            "updated_source_count": 0,
            "unchanged_source_count": 0,
            "failed_source_count": 0,
            "provenance_source_count": 2,
        },
        "retrieval_benchmark": {"cases": retrieval_cases},
        "parser_benchmark": {"cases": parser_cases},
        "document_contract_calibration": {"documents": documents},
        "claim_compiler_quality": {
            "critical_claim_count": 100,
            "critical_cited_count": 100,
            "critical_conflict_count": 0,
            "unaffected_section_count": 100,
            "unaffected_section_reused_count": 90,
        },
        "report_quality_independent_review": {"reports": reports},
        "entity_authenticity_benchmark": {"entities": entities},
        "permission_leakage_matrix": {"cases": permission_cases},
        "skill_security_benchmark": {"skills": skills},
        "cross_artifact_consistency": {
            "artifact_types": [
                "executive_brief",
                "mind_map",
                "data_table",
                "slide_outline",
                "infographic_spec",
                "audio_script",
            ],
            "critical_fact_count": 100,
            "critical_consistent_count": 100,
            "ordinary_fact_count": 100,
            "ordinary_consistent_count": 98,
            "stale_artifact_count": 0,
        },
        "office_visual_acceptance": {"cases": office_cases},
        "performance_cost_benchmark": {
            "environment": "production",
            "concurrent_users": 20,
            "request_count": 500,
            "p95_ms": 1500,
            "error_rate": 0.005,
            "model_cold_start_seconds": 80,
            "long_report_cost_cny": 12,
        },
        "recovery_audit_reliability": {
            "environment": "production",
            "scenarios": [
                {"scenario": name, "passed": True, "data_loss_count": 0, "recovery_seconds": 120}
                for name in ("queue_restart", "backup_restore", "audit_export", "external_model_volume_fail_closed")
            ]
        },
    }


def test_all_2_0_1_through_2_0_6_threshold_calculators_pass_only_with_required_evidence() -> None:
    user_id = uuid4()
    payloads = _passing_payloads()
    assert set(payloads) == set(SUITE_SPECS)
    for suite_key, metrics in payloads.items():
        spec = SUITE_SPECS[suite_key]
        kwargs = _external(user_id) if spec.evidence_class != "engineering" else {"user_id": user_id}
        if spec.evidence_class == "engineering" and spec.requires_artifact:
            kwargs["source_artifact_uri"] = "artifact://decision-studio/engineering/run.json"
        result = preview_validation_run(suite_key=suite_key, metrics=metrics, **kwargs)
        assert result["status"] == "pass", (suite_key, result["findings"])

    without_reviewer = preview_validation_run(
        suite_key="retrieval_benchmark",
        metrics=payloads["retrieval_benchmark"],
        user_id=user_id,
    )
    assert without_reviewer["status"] == "blocked"
    assert {row["key"] for row in without_reviewer["findings"] if row["status"] == "blocked"} >= {
        "reviewer_id",
        "source_artifact_uri",
    }


def test_release_reliability_suites_reject_local_smoke_as_production_evidence() -> None:
    user_id = uuid4()
    payloads = _passing_payloads()
    for suite_key in ("performance_cost_benchmark", "recovery_audit_reliability"):
        metrics = dict(payloads[suite_key])
        metrics["environment"] = "local"
        result = preview_validation_run(
            suite_key=suite_key,
            metrics=metrics,
            source_artifact_uri=f"artifact://decision-studio/{suite_key}/local.json",
            user_id=user_id,
        )
        assert result["status"] == "blocked"
        environment = next(row for row in result["findings"] if row["key"] == "environment")
        assert environment["status"] == "blocked"


def test_release_program_uses_latest_immutable_runs_and_exports_hash_chain() -> None:
    with _session() as db:
        user = _user(db)
        for suite_key, metrics in _passing_payloads().items():
            spec = SUITE_SPECS[suite_key]
            kwargs = _external(user.id) if spec.evidence_class != "engineering" else {}
            kwargs.pop("user_id", None)
            if spec.evidence_class == "engineering" and spec.requires_artifact:
                kwargs["source_artifact_uri"] = "artifact://decision-studio/engineering/run.json"
            record_validation_run(db, user_id=user.id, suite_key=suite_key, metrics=metrics, **kwargs)

        snapshot = build_release_program_snapshot(db, user_id=user.id)
        assert snapshot["release_version"] == "2.0.7-development"
        assert snapshot["implementation_status"] == "implemented"
        assert snapshot["overall_status"] == "pass"
        assert all(row["acceptance_status"] == "pass" for row in snapshot["milestones"])

        failed_latest = record_validation_run(
            db,
            user_id=user.id,
            suite_key="performance_cost_benchmark",
            metrics={},
            source_artifact_uri="artifact://decision-studio/engineering/failed.json",
        )
        assert failed_latest.status == "blocked"
        snapshot = build_release_program_snapshot(db, user_id=user.id)
        version_206 = next(row for row in snapshot["milestones"] if row["version"] == "2.0.6")
        assert version_206["acceptance_status"] == "blocked"

        audit = build_validation_audit_export(db, user_id=user.id)
        assert audit["chain_valid"] is True
        assert audit["record_count"] == len(SUITE_SPECS) + 1
        assert len(audit["chain_head"]) == 64
        assert db.scalar(select(DecisionValidationRun).where(DecisionValidationRun.id == failed_latest.id)) is not None


def test_real_knowledge_and_report_activation_is_provenance_bound_and_idempotent() -> None:
    with _session() as db:
        user = _user(db)
        entry = KnowledgeEntry(
            user_id=user.id,
            title="文旅知识条目",
            content="景区客流增长。\n产品供给需要升级。",
            source_domain="example.gov.cn",
            collection_name="文旅",
        )
        job = ResearchJob(
            user_id=user.id,
            keyword="文旅项目",
            research_focus="真实数据激活",
            status="succeeded",
            report_payload={"markdown": "# 文旅研报\n\n预算与实施计划。"},
            finished_at=datetime.now(UTC),
        )
        db.add_all([entry, job])
        db.commit()

        preview = preview_data_activation(db, user_id=user.id)
        assert preview["status"] == "ready"
        assert preview["candidate_count"] == 2
        assert preview["state_counts"] == {"new": 2}

        activated = run_data_activation(db, user_id=user.id, notebook_name="真实资料 Notebook")
        assert activated["status"] == "pass"
        assert activated["metrics"]["created_source_count"] == 2
        notebook_id = UUID(activated["notebook"]["id"])
        sources = list(db.scalars(select(DecisionSource).where(DecisionSource.notebook_id == notebook_id)).all())
        assert len(sources) == 2
        assert all(source.source_uri.startswith("anti-fomo://") for source in sources)

        rerun = run_data_activation(
            db,
            user_id=user.id,
            notebook_name="ignored",
            notebook_id=notebook_id,
        )
        assert rerun["status"] == "pass"
        assert rerun["metrics"]["created_source_count"] == 0
        assert rerun["metrics"]["unchanged_source_count"] == 2
        assert db.scalar(select(DecisionValidationRun).where(DecisionValidationRun.suite_key == "real_data_activation")) is not None
