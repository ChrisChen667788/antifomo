from __future__ import annotations

from collections.abc import Generator, Sequence
from contextlib import contextmanager
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.db.base import Base
from app.models.decision_studio_entities import DecisionArtifact, DecisionPassage
from app.models.entities import User
from app.services.decision_studio import readiness as readiness_service
from app.services.decision_studio.artifacts import (
    audit_artifact_consistency,
    generate_artifact,
)
from app.services.decision_studio.claim_graph import (
    compile_notebook_sections,
    create_claim,
    upsert_section,
)
from app.services.decision_studio.contracts import (
    GOVERNMENT_FSR_FIELDS,
    add_contract_assumption,
    add_contract_calculation,
    create_document_contract,
    ensure_builtin_policy_packs,
    serialize_contract,
    update_contract_field,
)
from app.services.decision_studio.embedding import (
    SemanticBackendUnavailable,
    _prepare_cache_dir,
    index_notebook_passages,
    search_notebook_passages,
)
from app.services.decision_studio.notebooks import (
    create_notebook,
    create_source_revision,
    get_passage_payload,
    update_source_trust,
)
from app.services.decision_studio.parsing import parse_document
from app.services.decision_studio.skills import (
    approve_skill,
    dry_run_skill,
    ensure_first_party_skills,
    record_skill_benchmark,
    sign_skill,
)
from app.services.decision_studio.spaces import (
    AccessDeniedError,
    create_connector,
    create_space,
    dry_run_connector,
    invoke_controlled_mcp,
    require_space_access,
    upsert_membership,
)
from app.services.work_tasks.pdf import _build_simple_pdf


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
    user = User(id=uuid4(), name="Decision Studio Test", email="studio@example.test")
    db.add(user)
    db.commit()
    return user


class _SemanticBackend:
    model_name = "test/semantic-v1"

    def encode(self, texts: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        for text in texts:
            tourism = sum(token in text for token in ("文旅", "旅游", "游客", "景区", "destination"))
            finance = sum(token in text for token in ("预算", "融资", "成本", "finance"))
            if tourism == finance == 0:
                vectors.append([0.1, 0.1])
            else:
                vectors.append([float(tourism), float(finance)])
        return vectors


def test_embedding_cache_preflight_creates_local_directory(tmp_path: Path) -> None:
    cache_dir = tmp_path / "huggingface" / "hub"

    assert _prepare_cache_dir(str(cache_dir), label="test") == str(cache_dir)
    assert cache_dir.is_dir()


def test_embedding_cache_preflight_rejects_unmounted_external_volume(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(Path, "is_mount", lambda _path: False)

    with pytest.raises(SemanticBackendUnavailable, match="External cache volume is not mounted"):
        _prepare_cache_dir("/Volumes/Missing SSD/huggingface/hub", label="test")


def _source(db: Session, notebook_id: UUID, title: str, content: str):
    source, revision, _parsed, _stale = create_source_revision(
        db,
        notebook_id=notebook_id,
        title=title,
        data=content.encode("utf-8"),
        file_name=f"{title}.txt",
        mime_type="text/plain",
    )
    passages = list(
        db.scalars(
            select(DecisionPassage)
            .where(DecisionPassage.revision_id == revision.id)
            .order_by(DecisionPassage.sequence)
        ).all()
    )
    update_source_trust(
        db,
        source=source,
        trust_status="verified",
        owner_label="test-owner",
        expires_at=None,
    )
    return source, revision, passages


def test_document_parsing_semantic_index_and_source_filtering() -> None:
    parsed = parse_document(
        b"<html><script>ignore()</script><body><h1>Destination</h1><p>Tourism evidence</p></body></html>",
        file_name="source.html",
        mime_type="text/html",
    )
    assert parsed.parser_name == "native_html"
    assert "ignore" not in parsed.text
    assert len(parsed.passages) == 2
    parsed_pdf = parse_document(
        _build_simple_pdf(["Structured PDF evidence"]),
        file_name="source.pdf",
        mime_type="application/pdf",
    )
    assert parsed_pdf.parser_name == "pypdf"
    assert parsed_pdf.text == "Structured PDF evidence"

    with _session() as db:
        user = _user(db)
        notebook = create_notebook(db, user_id=user.id, name="文旅决策")
        tourism, _revision, tourism_passages = _source(db, notebook.id, "文旅资料", "景区游客增长明显。\n目的地旅游产品需要升级。")
        finance, _revision2, _finance_passages = _source(db, notebook.id, "财务资料", "预算成本需要控制。\n融资方案待评估。")

        indexed = index_notebook_passages(db, notebook_id=notebook.id, backend=_SemanticBackend())
        assert indexed["status"] == "ready"
        assert indexed["model"] == "test/semantic-v1"
        assert indexed["indexed_passage_count"] == 4

        result = search_notebook_passages(
            db,
            notebook_id=notebook.id,
            query="文旅目的地",
            included_source_ids=[tourism.id],
            require_semantic=True,
            backend=_SemanticBackend(),
        )
        assert result["mode"] == "semantic"
        assert result["hits"]
        assert {hit["source_id"] for hit in result["hits"]} == {str(tourism.id)}
        assert str(finance.id) not in {hit["source_id"] for hit in result["hits"]}

        hybrid = search_notebook_passages(
            db,
            notebook_id=notebook.id,
            query="文旅目的地",
            included_source_ids=[tourism.id, finance.id],
            require_semantic=True,
            retrieval_mode="hybrid",
            backend=_SemanticBackend(),
        )
        assert hybrid["mode"] == "hybrid_rrf"
        assert hybrid["hits"][0]["ranking"]["semantic_rank"] >= 1
        assert hybrid["hits"][0]["ranking"]["lexical_rank"] >= 1

        lexical = search_notebook_passages(
            db,
            notebook_id=notebook.id,
            query="预算成本",
            included_source_ids=[finance.id],
            retrieval_mode="lexical",
        )
        assert lexical["mode"] == "lexical"
        assert {hit["source_id"] for hit in lexical["hits"]} == {str(finance.id)}

        clickback = get_passage_payload(db, tourism_passages[0].id)
        assert clickback is not None
        assert clickback["revision_number"] == 1
        assert clickback["locator"]["paragraph"] == 1


def test_source_revision_invalidates_artifact_and_stale_claim() -> None:
    with _session() as db:
        user = _user(db)
        notebook = create_notebook(db, user_id=user.id, name="Revision lineage")
        source, _revision, passages = _source(db, notebook.id, "来源", "首版事实。")
        claim = create_claim(
            db,
            notebook_id=notebook.id,
            claim_key="market_fact",
            text="首版事实成立。",
            criticality="critical",
            status="accepted",
            passage_ids=[passages[0].id],
            depends_on_claim_ids=[],
            facts={"metric": 1},
            owner_label="owner",
        )
        artifact, reused = generate_artifact(
            db,
            notebook_id=notebook.id,
            artifact_type="executive_brief",
            title="决策摘要",
        )
        assert reused is False
        assert str(claim.id) in artifact.claim_ids
        assert artifact.stale is False

        create_source_revision(
            db,
            notebook_id=notebook.id,
            source_id=source.id,
            title=source.title,
            data="第二版事实。".encode("utf-8"),
            file_name="source.txt",
            mime_type="text/plain",
        )
        db.refresh(artifact)
        assert artifact.status == "stale"
        assert artifact.stale is True
        with pytest.raises(ValueError, match="stale"):
            generate_artifact(
                db,
                notebook_id=notebook.id,
                artifact_type="data_table",
                title="证据表",
            )


def test_critical_claim_rejects_unverified_source() -> None:
    with _session() as db:
        user = _user(db)
        notebook = create_notebook(db, user_id=user.id, name="Trust gate")
        source, revision, _parsed, _stale = create_source_revision(
            db,
            notebook_id=notebook.id,
            title="未验证来源",
            data="关键事实。".encode("utf-8"),
            file_name="unverified.txt",
            mime_type="text/plain",
        )
        passage = db.scalar(select(DecisionPassage).where(DecisionPassage.revision_id == revision.id))
        assert source.trust_status == "unverified"
        assert passage is not None
        with pytest.raises(ValueError, match="verified source"):
            create_claim(
                db,
                notebook_id=notebook.id,
                claim_key="critical_unverified",
                text="关键事实成立。",
                criticality="critical",
                status="accepted",
                passage_ids=[passage.id],
                depends_on_claim_ids=[],
                facts={},
                owner_label="owner",
            )


def test_chinese_document_contract_tracks_gaps_assumptions_and_formula_lineage() -> None:
    assert len(GOVERNMENT_FSR_FIELDS) >= 35
    with _session() as db:
        user = _user(db)
        notebook = create_notebook(db, user_id=user.id, name="政府可研")
        packs = ensure_builtin_policy_packs(db)
        government_pack = next(pack for pack in packs if pack.pack_key == "government_fsr_2023")
        contract = create_document_contract(
            db,
            notebook_id=notebook.id,
            policy_pack_id=government_pack.id,
            title="文旅项目可行性研究报告",
        )
        assert serialize_contract(contract)["gap_count"] == len(GOVERNMENT_FSR_FIELDS)

        with pytest.raises(ValueError, match="require evidence"):
            update_contract_field(
                db,
                contract=contract,
                field_key="project_overview",
                state="evidence",
                value="示范项目",
                owner="项目组",
                evidence_refs=[],
                note="",
            )
        update_contract_field(
            db,
            contract=contract,
            field_key="project_overview",
            state="evidence",
            value="示范项目",
            owner="项目组",
            evidence_refs=["passage:001"],
            note="",
        )
        add_contract_assumption(
            db,
            contract=contract,
            assumption_key="visitor_growth",
            statement="游客量每年增长 8%",
            owner="咨询组",
            validation_action="取得统计年鉴后复核",
        )
        with pytest.raises(ValueError, match="requires source_refs"):
            add_contract_calculation(
                db,
                contract=contract,
                calculation_key="total_investment",
                label="总投资",
                operation="sum",
                inputs=[{"key": "construction", "value": 100, "source_refs": [], "assumption_ref": ""}],
                unit="万元",
            )
        add_contract_calculation(
            db,
            contract=contract,
            calculation_key="total_investment",
            label="总投资",
            operation="sum",
            inputs=[
                {"key": "construction", "value": 100, "source_refs": ["passage:002"], "assumption_ref": ""},
                {"key": "reserve", "value": 20, "source_refs": [], "assumption_ref": "visitor_growth"},
            ],
            unit="万元",
        )
        payload = serialize_contract(contract)
        assert payload["calculations"][0]["result"] == "120"
        assert payload["calculations"][0]["inputs"][1]["assumption_ref"] == "visitor_growth"


def test_claim_graph_incremental_compilation_and_multiformat_consistency() -> None:
    with _session() as db:
        user = _user(db)
        notebook = create_notebook(db, user_id=user.id, name="Claim graph")
        _source_row, _revision, passages = _source(db, notebook.id, "证据", "预算为 100 万元。\n建设期为 12 个月。\n另一材料称预算为 120 万元。")
        budget = create_claim(
            db,
            notebook_id=notebook.id,
            claim_key="budget",
            text="项目预算为 100 万元。",
            criticality="critical",
            status="accepted",
            passage_ids=[passages[0].id],
            depends_on_claim_ids=[],
            facts={"budget": 100},
            owner_label="finance",
        )
        schedule = create_claim(
            db,
            notebook_id=notebook.id,
            claim_key="schedule",
            text="建设期为 12 个月。",
            criticality="normal",
            status="accepted",
            passage_ids=[passages[1].id],
            depends_on_claim_ids=[budget.id],
            facts={"duration_months": 12},
            owner_label="delivery",
        )
        upsert_section(
            db,
            notebook_id=notebook.id,
            section_key="investment",
            title="投资与计划",
            claim_ids=[budget.id, schedule.id],
        )
        first = compile_notebook_sections(db, notebook_id=notebook.id)
        second = compile_notebook_sections(db, notebook_id=notebook.id)
        assert first["status"] == "pass"
        assert first["built_section_keys"] == ["investment"]
        assert second["skipped_section_keys"] == ["investment"]

        brief, _ = generate_artifact(db, notebook_id=notebook.id, artifact_type="executive_brief", title="摘要")
        table, _ = generate_artifact(db, notebook_id=notebook.id, artifact_type="data_table", title="表格")
        assert brief.consistency_hash == table.consistency_hash
        assert audit_artifact_consistency(db, notebook_id=notebook.id)["status"] == "pass"

        conflict = create_claim(
            db,
            notebook_id=notebook.id,
            claim_key="budget_conflict",
            text="项目预算为 120 万元。",
            criticality="critical",
            status="accepted",
            passage_ids=[passages[2].id],
            depends_on_claim_ids=[],
            facts={"budget": 120},
            owner_label="review",
        )
        upsert_section(
            db,
            notebook_id=notebook.id,
            section_key="investment",
            title="投资与计划",
            claim_ids=[budget.id, schedule.id, conflict.id],
        )
        compiled = compile_notebook_sections(db, notebook_id=notebook.id)
        assert compiled["status"] == "blocked"
        assert compiled["global_findings"][0]["key"] == "fact_conflict:budget"


def test_spaces_acl_connectors_and_signed_skill_sandbox() -> None:
    with _session() as db:
        user = _user(db)
        owner_id = str(user.id)
        space = create_space(
            db,
            owner_user_id=user.id,
            name="可信知识空间",
            description="共享评审",
            visibility="shared",
        )
        upsert_membership(db, space=space, member_id="reviewer-1", role="reviewer")
        assert require_space_access(db, space_id=space.id, actor_id="reviewer-1", minimum_role="reviewer") == space
        with pytest.raises(AccessDeniedError):
            require_space_access(db, space_id=space.id, actor_id="viewer-without-membership")

        local = create_connector(
            db,
            space_id=space.id,
            name="Local evidence",
            connector_type="local_folder",
            endpoint="/tmp",
            permissions=["read:sources"],
        )
        assert dry_run_connector(db, connector=local).status == "ready"
        remote = create_connector(
            db,
            space_id=space.id,
            name="Controlled MCP",
            connector_type="mcp",
            endpoint="https://mcp.example.test",
            permissions=["read:sources"],
        )
        assert dry_run_connector(db, connector=remote).status == "blocked"
        assert remote.last_dry_run_payload["network_executed"] is False
        mcp_plan = invoke_controlled_mcp(
            db,
            connector=remote,
            action="read_resource",
            arguments={"uri": "knowledge://demo"},
            granted_permissions=["mcp:read"],
        )
        assert mcp_plan["status"] == "blocked"
        assert mcp_plan["plan"]["network_executed"] is False

        skill = next(
            row for row in ensure_first_party_skills(db, user_id=user.id)
            if row.skill_key == "evidence-and-entity-auditor"
        )
        key = "test-release-signing-key"
        sign_skill(db, skill=skill, signing_key=key)
        record_skill_benchmark(db, skill=skill, score=0.92, case_count=100, evidence_ref="artifact:test-benchmark")
        approve_skill(db, skill=skill, signing_key=key)
        declared = list(skill.permissions_payload)
        ready = dry_run_skill(
            db,
            skill=skill,
            notebook_id=None,
            actor_id=owner_id,
            requested_permissions=declared,
            granted_permissions=declared,
        )
        assert ready.status == "ready"
        assert ready.plan_payload["network_execution"] is False
        blocked = dry_run_skill(
            db,
            skill=skill,
            notebook_id=None,
            actor_id=owner_id,
            requested_permissions=["shell:execute"],
            granted_permissions=["shell:execute"],
        )
        assert blocked.status == "blocked"
        assert any("Forbidden" in item or "Undeclared" in item for item in blocked.violations_payload)


def test_decision_studio_readiness_inherits_existing_blocked_gate(monkeypatch: pytest.MonkeyPatch) -> None:
    inherited = {
        "generated_at": "2026-07-16T00:00:00Z",
        "release_version": "1.9.1-executable-architecture-evidence",
        "overall_status": "blocked",
        "readiness_score": 72,
        "gates": [],
        "next_actions": [],
    }
    monkeypatch.setattr(readiness_service, "build_release_readiness_snapshot", lambda _db: inherited)
    with _session() as db:
        snapshot = readiness_service.build_decision_studio_readiness(db)
    assert snapshot["release_version"] == "2.2.0-development"
    assert snapshot["overall_status"] == "blocked"
    inherited_gate = next(gate for gate in snapshot["gates"] if gate["key"] == "inherited_release_readiness")
    assert inherited_gate["status"] == "blocked"
    assert "不由代码自动放行" in inherited_gate["observed"]
    assert next(gate for gate in snapshot["gates"] if gate["key"] == "studio_visual_baseline")["status"] == "blocked"
    assert next(gate for gate in snapshot["gates"] if gate["key"] == "external_commercial_acceptance")["status"] == "blocked"


def test_decision_studio_tables_are_registered() -> None:
    expected = {
        "decision_notebooks",
        "decision_sources",
        "decision_source_revisions",
        "decision_passages",
        "decision_document_contracts",
        "decision_claims",
        "decision_sections",
        "decision_knowledge_spaces",
        "governed_skills",
    }
    assert expected <= set(Base.metadata.tables)
    assert DecisionArtifact.__tablename__ == "decision_artifacts"
