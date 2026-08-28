from __future__ import annotations

import base64
import binascii
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.decision_studio_entities import (
    DecisionArtifact,
    DecisionClaim,
    DecisionDocumentContract,
    DecisionPassage,
    DecisionPolicyPack,
    DecisionSection,
    DecisionSource,
    DecisionValidationRun,
    GovernedSkill,
    KnowledgeConnector,
    KnowledgeReviewThread,
)
from app.models.entities import User
from app.schemas.decision_studio import (
    ArtifactGenerateRequest,
    ClaimCreateRequest,
    ConnectorCreateRequest,
    ConnectorInvokeRequest,
    ContractAssumptionRequest,
    ContractCalculationRequest,
    ContractCreateRequest,
    ContractFieldUpdateRequest,
    DataActivationRequest,
    MembershipUpdateRequest,
    NotebookCreateRequest,
    ReviewCommentRequest,
    ReviewCreateRequest,
    ReviewDecisionRequest,
    ReliabilityProbeRequest,
    SectionCompileRequest,
    SectionUpsertRequest,
    SemanticSearchRequest,
    SkillBenchmarkRequest,
    SkillRegisterRequest,
    SkillRunRequest,
    SourceRevisionCreateRequest,
    SourceTrustUpdateRequest,
    SpaceCreateRequest,
    ValidationRunRequest,
)
from app.services.decision_studio.activation import preview_data_activation, run_data_activation
from app.services.decision_studio.artifacts import (
    generate_artifact,
    list_artifacts,
    serialize_artifact,
)
from app.services.decision_studio.claim_graph import (
    compile_notebook_sections,
    create_claim,
    serialize_claim,
    serialize_section,
    upsert_section,
)
from app.services.decision_studio.contracts import (
    add_contract_assumption,
    add_contract_calculation,
    create_document_contract,
    ensure_builtin_policy_packs,
    serialize_contract,
    serialize_policy_pack,
    update_contract_field,
)
from app.services.decision_studio.embedding import (
    SemanticBackendUnavailable,
    index_notebook_passages,
    search_notebook_passages,
)
from app.services.decision_studio.notebooks import (
    create_notebook,
    create_source_revision,
    get_passage_payload,
    list_notebooks,
    list_sources,
    serialize_notebook,
    serialize_source,
    update_source_trust,
)
from app.services.decision_studio.readiness import build_decision_studio_readiness
from app.services.decision_studio.skills import (
    approve_skill,
    dry_run_skill,
    ensure_first_party_skills,
    execute_skill,
    record_skill_benchmark,
    register_skill,
    serialize_skill,
    serialize_skill_run,
    sign_skill,
)
from app.services.decision_studio.spaces import (
    AccessDeniedError,
    accessible_space_ids,
    add_review_comment,
    create_connector,
    create_review_thread,
    create_space,
    decide_review,
    dry_run_connector,
    invoke_controlled_mcp,
    list_accessible_spaces,
    require_notebook_access,
    require_space_access,
    serialize_connector,
    serialize_review,
    serialize_space,
    upsert_membership,
)
from app.services.decision_studio.validation import (
    build_release_program_snapshot,
    build_validation_audit_export,
    list_validation_runs,
    preview_validation_run,
    record_validation_run,
    run_local_reliability_probe,
    serialize_validation_run,
    validation_specs_payload,
)
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api/decision-studio", tags=["decision-studio"])
settings = get_settings()


def _actor_id(x_anti_fomo_actor_id: str | None = Header(default=None)) -> str:
    return (x_anti_fomo_actor_id or str(settings.single_user_id)).strip()


def _actor_user(db: Session, actor_id: str) -> User:
    demo_user = ensure_demo_user(db)
    if actor_id == str(demo_user.id):
        return demo_user
    try:
        user = db.get(User, UUID(actor_id))
    except ValueError:
        user = None
    if user is None:
        raise AccessDeniedError("A persisted user is required to own a Space or Notebook.")
    return user


def _service_error(exc: Exception) -> None:
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, AccessDeniedError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    if isinstance(exc, SemanticBackendUnavailable):
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail=str(exc)) from exc


def _source_for_actor(db: Session, source_id: UUID, actor_id: str, *, role: str = "viewer") -> DecisionSource:
    source = db.get(DecisionSource, source_id)
    if source is None:
        raise HTTPException(status_code=404, detail="Source not found.")
    require_notebook_access(db, notebook_id=source.notebook_id, actor_id=actor_id, minimum_role=role)
    return source


def _contract_for_actor(db: Session, contract_id: UUID, actor_id: str, *, role: str = "viewer") -> DecisionDocumentContract:
    contract = db.get(DecisionDocumentContract, contract_id)
    if contract is None:
        raise HTTPException(status_code=404, detail="Document contract not found.")
    require_notebook_access(db, notebook_id=contract.notebook_id, actor_id=actor_id, minimum_role=role)
    return contract


def _skill_for_actor(db: Session, skill_id: UUID, actor_id: str) -> GovernedSkill:
    skill = db.get(GovernedSkill, skill_id)
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found.")
    if str(skill.user_id) != actor_id:
        raise AccessDeniedError("Skill registry access denied.")
    return skill


@router.get("/overview")
def get_overview(db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        user = _actor_user(db, actor_id)
        packs = ensure_builtin_policy_packs(db)
        skills = ensure_first_party_skills(db, user_id=user.id)
        space_ids = accessible_space_ids(db, actor_id=actor_id)
        notebooks = list_notebooks(db, user_id=user.id, space_ids=space_ids)
        return {
            "version": "2.2.0-development",
            "capabilities": [
                "1.9.2", "1.9.3", "1.9.4", "1.9.5", "1.9.6", "2.0.0",
                "2.0.1", "2.0.2", "2.0.3", "2.0.4", "2.0.5", "2.0.6", "2.0.7",
                "2.1.0", "2.1.1", "2.1.2", "2.1.3", "2.1.4", "2.1.5", "2.2.0",
            ],
            "embedding": {
                "enabled": settings.decision_embedding_enabled,
                "provider": settings.decision_embedding_provider,
                "model": settings.decision_embedding_model,
                "device": settings.decision_embedding_device,
                "batch_size": settings.decision_embedding_batch_size,
                "cache_dir": settings.decision_embedding_cache_dir,
                "xet_cache_dir": settings.decision_embedding_xet_cache_dir,
            },
            "spaces": [serialize_space(db, space, actor_id=actor_id) for space in list_accessible_spaces(db, actor_id=actor_id)],
            "notebooks": [serialize_notebook(db, notebook) for notebook in notebooks],
            "policy_packs": [serialize_policy_pack(pack) for pack in packs],
            "skills": [serialize_skill(skill, signing_key=settings.decision_skill_signing_key) for skill in skills],
        }
    except Exception as exc:
        _service_error(exc)


@router.get("/spaces")
def get_spaces(db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> list[dict]:
    return [serialize_space(db, space, actor_id=actor_id) for space in list_accessible_spaces(db, actor_id=actor_id)]


@router.post("/spaces", status_code=201)
def post_space(payload: SpaceCreateRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        user = _actor_user(db, actor_id)
        space = create_space(db, owner_user_id=user.id, **payload.model_dump())
        return serialize_space(db, space, actor_id=actor_id)
    except Exception as exc:
        _service_error(exc)


@router.put("/spaces/{space_id}/members")
def put_space_member(space_id: UUID, payload: MembershipUpdateRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        space = require_space_access(db, space_id=space_id, actor_id=actor_id, minimum_role="owner")
        membership = upsert_membership(db, space=space, **payload.model_dump())
        return {"id": str(membership.id), "member_id": membership.member_id, "role": membership.role}
    except Exception as exc:
        _service_error(exc)


@router.get("/spaces/{space_id}/reviews")
def get_reviews(space_id: UUID, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> list[dict]:
    try:
        require_space_access(db, space_id=space_id, actor_id=actor_id, minimum_role="viewer")
        rows = db.scalars(select(KnowledgeReviewThread).where(KnowledgeReviewThread.space_id == space_id)).all()
        return [serialize_review(row) for row in rows]
    except Exception as exc:
        _service_error(exc)


@router.post("/spaces/{space_id}/reviews", status_code=201)
def post_review(space_id: UUID, payload: ReviewCreateRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        require_space_access(db, space_id=space_id, actor_id=actor_id, minimum_role="reviewer")
        return serialize_review(create_review_thread(db, space_id=space_id, actor_id=actor_id, **payload.model_dump()))
    except Exception as exc:
        _service_error(exc)


@router.post("/reviews/{review_id}/comments")
def post_review_comment(review_id: UUID, payload: ReviewCommentRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        review = db.get(KnowledgeReviewThread, review_id)
        if review is None:
            raise HTTPException(status_code=404, detail="Review thread not found.")
        require_space_access(db, space_id=review.space_id, actor_id=actor_id, minimum_role="reviewer")
        return serialize_review(add_review_comment(db, thread=review, actor_id=actor_id, comment=payload.comment))
    except HTTPException:
        raise
    except Exception as exc:
        _service_error(exc)


@router.post("/reviews/{review_id}/decision")
def post_review_decision(review_id: UUID, payload: ReviewDecisionRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        review = db.get(KnowledgeReviewThread, review_id)
        if review is None:
            raise HTTPException(status_code=404, detail="Review thread not found.")
        require_space_access(db, space_id=review.space_id, actor_id=actor_id, minimum_role="reviewer")
        return serialize_review(decide_review(db, thread=review, actor_id=actor_id, decision=payload.decision))
    except HTTPException:
        raise
    except Exception as exc:
        _service_error(exc)


@router.get("/spaces/{space_id}/connectors")
def get_connectors(space_id: UUID, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> list[dict]:
    try:
        require_space_access(db, space_id=space_id, actor_id=actor_id, minimum_role="viewer")
        rows = db.scalars(select(KnowledgeConnector).where(KnowledgeConnector.space_id == space_id)).all()
        return [serialize_connector(row) for row in rows]
    except Exception as exc:
        _service_error(exc)


@router.post("/spaces/{space_id}/connectors", status_code=201)
def post_connector(space_id: UUID, payload: ConnectorCreateRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        require_space_access(db, space_id=space_id, actor_id=actor_id, minimum_role="owner")
        return serialize_connector(create_connector(db, space_id=space_id, **payload.model_dump()))
    except Exception as exc:
        _service_error(exc)


@router.post("/connectors/{connector_id}/dry-run")
def post_connector_dry_run(connector_id: UUID, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        connector = db.get(KnowledgeConnector, connector_id)
        if connector is None:
            raise HTTPException(status_code=404, detail="Connector not found.")
        require_space_access(db, space_id=connector.space_id, actor_id=actor_id, minimum_role="owner")
        return serialize_connector(dry_run_connector(db, connector=connector))
    except HTTPException:
        raise
    except Exception as exc:
        _service_error(exc)


@router.post("/connectors/{connector_id}/invoke")
def post_connector_invoke(
    connector_id: UUID,
    payload: ConnectorInvokeRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        connector = db.get(KnowledgeConnector, connector_id)
        if connector is None:
            raise HTTPException(status_code=404, detail="Connector not found.")
        require_space_access(db, space_id=connector.space_id, actor_id=actor_id, minimum_role="editor")
        return invoke_controlled_mcp(db, connector=connector, **payload.model_dump())
    except HTTPException:
        raise
    except Exception as exc:
        _service_error(exc)


@router.get("/notebooks")
def get_notebooks(db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> list[dict]:
    try:
        user_id = UUID(actor_id)
    except ValueError:
        user_id = None
    rows = list_notebooks(db, user_id=user_id, space_ids=accessible_space_ids(db, actor_id=actor_id))
    return [serialize_notebook(db, row) for row in rows]


@router.post("/notebooks", status_code=201)
def post_notebook(payload: NotebookCreateRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        user = _actor_user(db, actor_id)
        if payload.space_id:
            require_space_access(db, space_id=payload.space_id, actor_id=actor_id, minimum_role="editor")
        notebook = create_notebook(db, user_id=user.id, **payload.model_dump())
        return serialize_notebook(db, notebook)
    except Exception as exc:
        _service_error(exc)


@router.get("/notebooks/{notebook_id}")
def get_notebook(notebook_id: UUID, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        notebook = require_notebook_access(db, notebook_id=notebook_id, actor_id=actor_id)
        return {
            **serialize_notebook(db, notebook),
            "sources": [serialize_source(db, source) for source in list_sources(db, notebook_id=notebook_id)],
            "contracts": [serialize_contract(row) for row in db.scalars(select(DecisionDocumentContract).where(DecisionDocumentContract.notebook_id == notebook_id)).all()],
            "claims": [serialize_claim(db, row) for row in db.scalars(select(DecisionClaim).where(DecisionClaim.notebook_id == notebook_id)).all()],
            "sections": [serialize_section(row) for row in db.scalars(select(DecisionSection).where(DecisionSection.notebook_id == notebook_id)).all()],
            "artifacts": [serialize_artifact(row) for row in list_artifacts(db, notebook_id=notebook_id)],
        }
    except Exception as exc:
        _service_error(exc)


@router.get("/notebooks/{notebook_id}/sources")
def get_sources(notebook_id: UUID, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> list[dict]:
    try:
        require_notebook_access(db, notebook_id=notebook_id, actor_id=actor_id)
        return [serialize_source(db, source, include_revisions=True) for source in list_sources(db, notebook_id=notebook_id)]
    except Exception as exc:
        _service_error(exc)


@router.post("/notebooks/{notebook_id}/sources", status_code=201)
def post_source(notebook_id: UUID, payload: SourceRevisionCreateRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        require_notebook_access(db, notebook_id=notebook_id, actor_id=actor_id, minimum_role="editor")
        if payload.content_base64 is not None:
            try:
                data = base64.b64decode(payload.content_base64, validate=True)
            except (binascii.Error, ValueError) as exc:
                raise ValueError("content_base64 is invalid.") from exc
        else:
            data = (payload.content or "").encode("utf-8")
        values = payload.model_dump(exclude={"content", "content_base64"})
        values["prefer_docling"] = bool(values["prefer_docling"] and settings.decision_docling_enabled)
        source, revision, parsed, stale_count = create_source_revision(db, notebook_id=notebook_id, data=data, **values)
        return {
            "source": serialize_source(db, source, include_revisions=True),
            "revision_id": str(revision.id),
            "parser": parsed.parser_name,
            "warnings": list(parsed.warnings),
            "stale_artifact_count": stale_count,
        }
    except Exception as exc:
        _service_error(exc)


@router.get("/sources/{source_id}")
def get_source(source_id: UUID, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        return serialize_source(db, _source_for_actor(db, source_id, actor_id), include_revisions=True)
    except HTTPException:
        raise
    except Exception as exc:
        _service_error(exc)


@router.put("/sources/{source_id}/trust")
def put_source_trust(source_id: UUID, payload: SourceTrustUpdateRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        source = _source_for_actor(db, source_id, actor_id, role="editor")
        return serialize_source(db, update_source_trust(db, source=source, **payload.model_dump()), include_revisions=True)
    except HTTPException:
        raise
    except Exception as exc:
        _service_error(exc)


@router.get("/passages/{passage_id}")
def get_passage(passage_id: UUID, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        payload = get_passage_payload(db, passage_id)
        if payload is None:
            raise HTTPException(status_code=404, detail="Passage not found.")
        require_notebook_access(db, notebook_id=UUID(str(payload["notebook_id"])), actor_id=actor_id)
        return payload
    except HTTPException:
        raise
    except Exception as exc:
        _service_error(exc)


@router.post("/notebooks/{notebook_id}/semantic-index")
def post_semantic_index(notebook_id: UUID, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        require_notebook_access(db, notebook_id=notebook_id, actor_id=actor_id, minimum_role="editor")
        return index_notebook_passages(db, notebook_id=notebook_id)
    except Exception as exc:
        _service_error(exc)


@router.post("/notebooks/{notebook_id}/search")
def post_search(notebook_id: UUID, payload: SemanticSearchRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        require_notebook_access(db, notebook_id=notebook_id, actor_id=actor_id)
        return search_notebook_passages(db, notebook_id=notebook_id, **payload.model_dump())
    except Exception as exc:
        _service_error(exc)


@router.get("/policy-packs")
def get_policy_packs(db: Session = Depends(get_db)) -> list[dict]:
    return [serialize_policy_pack(pack) for pack in ensure_builtin_policy_packs(db)]


@router.get("/notebooks/{notebook_id}/contracts")
def get_contracts(notebook_id: UUID, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> list[dict]:
    try:
        require_notebook_access(db, notebook_id=notebook_id, actor_id=actor_id)
        rows = db.scalars(select(DecisionDocumentContract).where(DecisionDocumentContract.notebook_id == notebook_id)).all()
        return [serialize_contract(row) for row in rows]
    except Exception as exc:
        _service_error(exc)


@router.post("/notebooks/{notebook_id}/contracts", status_code=201)
def post_contract(notebook_id: UUID, payload: ContractCreateRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        require_notebook_access(db, notebook_id=notebook_id, actor_id=actor_id, minimum_role="editor")
        return serialize_contract(create_document_contract(db, notebook_id=notebook_id, **payload.model_dump()))
    except Exception as exc:
        _service_error(exc)


@router.get("/contracts/{contract_id}")
def get_contract(contract_id: UUID, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        return serialize_contract(_contract_for_actor(db, contract_id, actor_id))
    except HTTPException:
        raise
    except Exception as exc:
        _service_error(exc)


@router.put("/contracts/{contract_id}/fields/{field_key}")
def put_contract_field(contract_id: UUID, field_key: str, payload: ContractFieldUpdateRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        contract = _contract_for_actor(db, contract_id, actor_id, role="editor")
        return serialize_contract(update_contract_field(db, contract=contract, field_key=field_key, **payload.model_dump()))
    except HTTPException:
        raise
    except Exception as exc:
        _service_error(exc)


@router.post("/contracts/{contract_id}/assumptions")
def post_contract_assumption(contract_id: UUID, payload: ContractAssumptionRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        contract = _contract_for_actor(db, contract_id, actor_id, role="editor")
        return serialize_contract(add_contract_assumption(db, contract=contract, **payload.model_dump()))
    except HTTPException:
        raise
    except Exception as exc:
        _service_error(exc)


@router.post("/contracts/{contract_id}/calculations")
def post_contract_calculation(contract_id: UUID, payload: ContractCalculationRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        contract = _contract_for_actor(db, contract_id, actor_id, role="editor")
        values = payload.model_dump()
        values["inputs"] = [item.model_dump() for item in payload.inputs]
        return serialize_contract(add_contract_calculation(db, contract=contract, **values))
    except HTTPException:
        raise
    except Exception as exc:
        _service_error(exc)


@router.get("/notebooks/{notebook_id}/claims")
def get_claims(notebook_id: UUID, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> list[dict]:
    try:
        require_notebook_access(db, notebook_id=notebook_id, actor_id=actor_id)
        rows = db.scalars(select(DecisionClaim).where(DecisionClaim.notebook_id == notebook_id)).all()
        return [serialize_claim(db, row) for row in rows]
    except Exception as exc:
        _service_error(exc)


@router.post("/notebooks/{notebook_id}/claims", status_code=201)
def post_claim(notebook_id: UUID, payload: ClaimCreateRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        require_notebook_access(db, notebook_id=notebook_id, actor_id=actor_id, minimum_role="editor")
        return serialize_claim(db, create_claim(db, notebook_id=notebook_id, **payload.model_dump()))
    except Exception as exc:
        _service_error(exc)


@router.get("/notebooks/{notebook_id}/sections")
def get_sections(notebook_id: UUID, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> list[dict]:
    try:
        require_notebook_access(db, notebook_id=notebook_id, actor_id=actor_id)
        rows = db.scalars(select(DecisionSection).where(DecisionSection.notebook_id == notebook_id)).all()
        return [serialize_section(row) for row in rows]
    except Exception as exc:
        _service_error(exc)


@router.put("/notebooks/{notebook_id}/sections")
def put_section(notebook_id: UUID, payload: SectionUpsertRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        require_notebook_access(db, notebook_id=notebook_id, actor_id=actor_id, minimum_role="editor")
        return serialize_section(upsert_section(db, notebook_id=notebook_id, **payload.model_dump()))
    except Exception as exc:
        _service_error(exc)


@router.post("/notebooks/{notebook_id}/sections/compile")
def post_compile(notebook_id: UUID, payload: SectionCompileRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        require_notebook_access(db, notebook_id=notebook_id, actor_id=actor_id, minimum_role="editor")
        return compile_notebook_sections(db, notebook_id=notebook_id, **payload.model_dump())
    except Exception as exc:
        _service_error(exc)


@router.get("/skills")
def get_skills(db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> list[dict]:
    try:
        user = _actor_user(db, actor_id)
        ensure_first_party_skills(db, user_id=user.id)
        rows = db.scalars(select(GovernedSkill).where(GovernedSkill.user_id == user.id)).all()
        return [serialize_skill(row, signing_key=settings.decision_skill_signing_key) for row in rows]
    except Exception as exc:
        _service_error(exc)


@router.post("/skills", status_code=201)
def post_skill(payload: SkillRegisterRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        user = _actor_user(db, actor_id)
        skill = register_skill(db, user_id=user.id, **payload.model_dump())
        return serialize_skill(skill, signing_key=settings.decision_skill_signing_key)
    except Exception as exc:
        _service_error(exc)


@router.post("/skills/{skill_id}/sign")
def post_skill_sign(skill_id: UUID, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        skill = sign_skill(db, skill=_skill_for_actor(db, skill_id, actor_id), signing_key=settings.decision_skill_signing_key or "")
        return serialize_skill(skill, signing_key=settings.decision_skill_signing_key)
    except HTTPException:
        raise
    except Exception as exc:
        _service_error(exc)


@router.post("/skills/{skill_id}/benchmark")
def post_skill_benchmark(skill_id: UUID, payload: SkillBenchmarkRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        skill = record_skill_benchmark(db, skill=_skill_for_actor(db, skill_id, actor_id), **payload.model_dump())
        return serialize_skill(skill, signing_key=settings.decision_skill_signing_key)
    except HTTPException:
        raise
    except Exception as exc:
        _service_error(exc)


@router.post("/skills/{skill_id}/approve")
def post_skill_approve(skill_id: UUID, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        skill = approve_skill(db, skill=_skill_for_actor(db, skill_id, actor_id), signing_key=settings.decision_skill_signing_key)
        return serialize_skill(skill, signing_key=settings.decision_skill_signing_key)
    except HTTPException:
        raise
    except Exception as exc:
        _service_error(exc)


@router.post("/skills/{skill_id}/dry-run")
def post_skill_dry_run(skill_id: UUID, payload: SkillRunRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        skill = _skill_for_actor(db, skill_id, actor_id)
        if payload.notebook_id:
            require_notebook_access(db, notebook_id=payload.notebook_id, actor_id=actor_id, minimum_role="editor")
        run = dry_run_skill(db, skill=skill, actor_id=actor_id, **payload.model_dump())
        return serialize_skill_run(run)
    except HTTPException:
        raise
    except Exception as exc:
        _service_error(exc)


@router.post("/skills/{skill_id}/execute")
def post_skill_execute(skill_id: UUID, payload: SkillRunRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        if payload.notebook_id is None:
            raise ValueError("notebook_id is required for execution.")
        require_notebook_access(db, notebook_id=payload.notebook_id, actor_id=actor_id, minimum_role="editor")
        run = execute_skill(db, skill=_skill_for_actor(db, skill_id, actor_id), actor_id=actor_id, **payload.model_dump())
        return serialize_skill_run(run)
    except HTTPException:
        raise
    except Exception as exc:
        _service_error(exc)


@router.get("/notebooks/{notebook_id}/artifacts")
def get_artifacts(notebook_id: UUID, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> list[dict]:
    try:
        require_notebook_access(db, notebook_id=notebook_id, actor_id=actor_id)
        return [serialize_artifact(row) for row in list_artifacts(db, notebook_id=notebook_id)]
    except Exception as exc:
        _service_error(exc)


@router.post("/notebooks/{notebook_id}/artifacts", status_code=201)
def post_artifact(notebook_id: UUID, payload: ArtifactGenerateRequest, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        require_notebook_access(db, notebook_id=notebook_id, actor_id=actor_id, minimum_role="editor")
        artifact, reused = generate_artifact(db, notebook_id=notebook_id, **payload.model_dump())
        return {**serialize_artifact(artifact), "reused": reused}
    except Exception as exc:
        _service_error(exc)


@router.get("/artifacts/{artifact_id}")
def get_artifact(artifact_id: UUID, db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    try:
        artifact = db.get(DecisionArtifact, artifact_id)
        if artifact is None:
            raise HTTPException(status_code=404, detail="Artifact not found.")
        require_notebook_access(db, notebook_id=artifact.notebook_id, actor_id=actor_id)
        return serialize_artifact(artifact)
    except HTTPException:
        raise
    except Exception as exc:
        _service_error(exc)


@router.get("/validation-specs")
def get_validation_specs() -> dict:
    return validation_specs_payload()


@router.post("/activation/preview")
def post_activation_preview(
    payload: DataActivationRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        user = _actor_user(db, actor_id)
        values = payload.model_dump(exclude={"notebook_name"})
        return preview_data_activation(db, user_id=user.id, **values)
    except Exception as exc:
        _service_error(exc)


@router.post("/activation/run", status_code=201)
def post_activation_run(
    payload: DataActivationRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        user = _actor_user(db, actor_id)
        return run_data_activation(db, user_id=user.id, **payload.model_dump())
    except Exception as exc:
        _service_error(exc)


@router.post("/validation-runs/preview")
def post_validation_preview(
    payload: ValidationRunRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        user = _actor_user(db, actor_id)
        return preview_validation_run(user_id=user.id, **payload.model_dump())
    except Exception as exc:
        _service_error(exc)


@router.post("/validation-runs", status_code=201)
def post_validation_run(
    payload: ValidationRunRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        user = _actor_user(db, actor_id)
        return serialize_validation_run(record_validation_run(db, user_id=user.id, **payload.model_dump()))
    except Exception as exc:
        _service_error(exc)


@router.get("/validation-runs")
def get_validation_runs(
    suite_key: str | None = Query(default=None, max_length=80),
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> list[dict]:
    user = _actor_user(db, actor_id)
    return [
        serialize_validation_run(row)
        for row in list_validation_runs(db, user_id=user.id, suite_key=suite_key, limit=limit)
    ]


@router.get("/validation-runs/audit-export")
def get_validation_audit_export(
    limit: int = Query(default=1000, ge=1, le=10_000),
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    user = _actor_user(db, actor_id)
    return build_validation_audit_export(db, user_id=user.id, limit=limit)


@router.get("/validation-runs/{run_id}")
def get_validation_run(
    run_id: UUID,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    user = _actor_user(db, actor_id)
    run = db.get(DecisionValidationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="Validation run not found.")
    if run.user_id != user.id:
        raise HTTPException(status_code=403, detail="Validation run access denied.")
    return serialize_validation_run(run)


@router.get("/release-program")
def get_release_program(db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    user = _actor_user(db, actor_id)
    return build_release_program_snapshot(db, user_id=user.id)


@router.post("/reliability/probe")
def post_reliability_probe(
    payload: ReliabilityProbeRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    user = _actor_user(db, actor_id)
    return run_local_reliability_probe(db, user_id=user.id, **payload.model_dump())


@router.get("/readiness")
def get_readiness(
    notebook_id: UUID | None = Query(default=None),
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        if notebook_id:
            require_notebook_access(db, notebook_id=notebook_id, actor_id=actor_id)
        elif actor_id != str(settings.single_user_id):
            raise AccessDeniedError("Shared actors must select a Notebook for readiness inspection.")
        user = _actor_user(db, actor_id)
        return build_decision_studio_readiness(db, notebook_id=notebook_id, user_id=user.id)
    except Exception as exc:
        _service_error(exc)
