from __future__ import annotations

from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.session import get_db
from app.models.decision_program_entities import (
    DecisionAgentApproval,
    DecisionAgentRun,
    DecisionCustomerPilot,
    DecisionDocumentDraft,
    DecisionQualityBenchmark,
    DecisionResearchRun,
    DecisionVerticalPack,
    EnterpriseIdentityProfile,
)
from app.models.decision_studio_entities import GovernedSkill, KnowledgeConnector
from app.models.entities import User
from app.schemas.decision_program import (
    AgentApprovalDecisionRequest,
    AgentRunActionRequest,
    AgentRunCreateRequest,
    ConnectorSyncRequest,
    CustomerPilotCreateRequest,
    CustomerPilotUpdateRequest,
    DocumentBlockUpdateRequest,
    DocumentDraftCreateRequest,
    DocumentExportRequest,
    DocumentExportConfirmationRequest,
    DocumentRegenerateRequest,
    IdentityProfileCreateRequest,
    QualityBenchmarkRecordRequest,
    ReleaseCandidateFreezeRequest,
    ResearchRunActionRequest,
    ResearchRunCreateRequest,
    ResearchRunPlanUpdateRequest,
    VerticalPackBenchmarkRequest,
)
from app.services.decision_program.agent_operations import (
    create_agent_run,
    decide_agent_approval,
    list_agent_approvals,
    serialize_agent_approval,
    serialize_agent_run,
    transition_agent_run,
)
from app.services.decision_program.commercial import (
    create_customer_pilot,
    serialize_customer_pilot,
    update_customer_pilot,
)
from app.services.decision_program.control_room import (
    compare_research_runs,
    create_research_run,
    revise_research_run_plan,
    serialize_research_run,
    transition_research_run,
)
from app.services.decision_program.document_editor import (
    DocumentRevisionConflict,
    create_document_draft,
    confirm_document_export,
    export_document_draft,
    regenerate_document_blocks,
    serialize_document_draft,
    update_document_block,
)
from app.services.decision_program.enterprise import (
    create_identity_profile,
    record_connector_sync,
    serialize_connector_sync,
    serialize_identity_profile,
)
from app.services.decision_program.overview import build_decision_program_overview
from app.services.decision_program.quality import record_quality_benchmark, serialize_quality_benchmark
from app.services.decision_program.release_candidates import (
    freeze_release_candidate,
    list_release_candidates,
    preview_release_candidate,
    serialize_release_candidate,
)
from app.services.decision_program.verticals import (
    record_vertical_pack_benchmark,
    seed_vertical_packs,
    serialize_vertical_pack,
)
from app.services.decision_studio.spaces import AccessDeniedError, require_notebook_access, require_space_access
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api/decision-studio/program", tags=["decision-program"])
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
        raise AccessDeniedError("A persisted user is required for Decision Program operations.")
    return user


def _service_error(exc: Exception) -> None:
    if isinstance(exc, HTTPException):
        raise exc
    if isinstance(exc, DocumentRevisionConflict):
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if isinstance(exc, AccessDeniedError):
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    raise HTTPException(status_code=400, detail=str(exc)) from exc


def _research_run(db: Session, run_id: UUID, actor_id: str, *, role: str = "viewer") -> DecisionResearchRun:
    row = db.get(DecisionResearchRun, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Research run not found.")
    require_notebook_access(db, notebook_id=row.notebook_id, actor_id=actor_id, minimum_role=role)
    return row


def _document_draft(db: Session, draft_id: UUID, actor_id: str, *, role: str = "viewer") -> DecisionDocumentDraft:
    row = db.get(DecisionDocumentDraft, draft_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Document draft not found.")
    require_notebook_access(db, notebook_id=row.notebook_id, actor_id=actor_id, minimum_role=role)
    return row


def _agent_run(db: Session, run_id: UUID, actor_id: str, *, role: str = "viewer") -> DecisionAgentRun:
    row = db.get(DecisionAgentRun, run_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Agent run not found.")
    if row.notebook_id:
        require_notebook_access(db, notebook_id=row.notebook_id, actor_id=actor_id, minimum_role=role)
    elif row.actor_id != actor_id:
        raise AccessDeniedError("Agent run access denied.")
    return row


@router.get("/overview")
def get_program_overview(db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> dict:
    user = _actor_user(db, actor_id)
    seed_vertical_packs(db)
    return build_decision_program_overview(db, user_id=user.id)


@router.post("/release-candidates", status_code=201)
def post_release_candidate(
    payload: ReleaseCandidateFreezeRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        user = _actor_user(db, actor_id)
        row = freeze_release_candidate(db, user_id=user.id, **payload.model_dump())
        return serialize_release_candidate(row, db)
    except Exception as exc:
        _service_error(exc)


@router.post("/release-candidates/preview")
def post_release_candidate_preview(
    payload: ReleaseCandidateFreezeRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        user = _actor_user(db, actor_id)
        return preview_release_candidate(db, user_id=user.id, **payload.model_dump())
    except Exception as exc:
        _service_error(exc)


@router.get("/release-candidates")
def get_release_candidates(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> list[dict]:
    user = _actor_user(db, actor_id)
    return [serialize_release_candidate(row) for row in list_release_candidates(db, user_id=user.id, limit=limit)]


@router.post("/research-runs", status_code=201)
def post_research_run(
    payload: ResearchRunCreateRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        user = _actor_user(db, actor_id)
        require_notebook_access(db, notebook_id=payload.notebook_id, actor_id=actor_id, minimum_role="editor")
        row = create_research_run(db, user_id=user.id, actor_id=actor_id, **payload.model_dump())
        return serialize_research_run(row)
    except Exception as exc:
        _service_error(exc)


@router.get("/research-runs")
def get_research_runs(
    notebook_id: UUID | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> list[dict]:
    user = _actor_user(db, actor_id)
    query = select(DecisionResearchRun).where(DecisionResearchRun.user_id == user.id)
    if notebook_id:
        require_notebook_access(db, notebook_id=notebook_id, actor_id=actor_id)
        query = query.where(DecisionResearchRun.notebook_id == notebook_id)
    rows = list(db.scalars(query.order_by(DecisionResearchRun.updated_at.desc()).limit(limit)).all())
    return [serialize_research_run(row) for row in rows]


@router.post("/research-runs/{run_id}/actions")
def post_research_run_action(
    run_id: UUID,
    payload: ResearchRunActionRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        row = _research_run(db, run_id, actor_id, role="editor")
        return serialize_research_run(transition_research_run(db, run=row, actor_id=actor_id, **payload.model_dump()))
    except Exception as exc:
        _service_error(exc)


@router.put("/research-runs/{run_id}/plan")
def put_research_run_plan(
    run_id: UUID,
    payload: ResearchRunPlanUpdateRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        row = _research_run(db, run_id, actor_id, role="editor")
        return serialize_research_run(
            revise_research_run_plan(db, run=row, actor_id=actor_id, **payload.model_dump())
        )
    except Exception as exc:
        _service_error(exc)


@router.get("/research-runs/compare")
def get_research_run_comparison(
    left_id: UUID,
    right_id: UUID,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    left = _research_run(db, left_id, actor_id)
    right = _research_run(db, right_id, actor_id)
    return compare_research_runs(left, right)


@router.post("/quality-benchmarks", status_code=201)
def post_quality_benchmark(
    payload: QualityBenchmarkRecordRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        user = _actor_user(db, actor_id)
        row = record_quality_benchmark(db, user_id=user.id, **payload.model_dump())
        return serialize_quality_benchmark(row)
    except Exception as exc:
        _service_error(exc)


@router.get("/quality-benchmarks")
def get_quality_benchmarks(
    kind: str | None = Query(default=None, max_length=30),
    limit: int = Query(default=100, ge=1, le=500),
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> list[dict]:
    user = _actor_user(db, actor_id)
    query = select(DecisionQualityBenchmark).where(DecisionQualityBenchmark.user_id == user.id)
    if kind:
        query = query.where(DecisionQualityBenchmark.benchmark_kind == kind)
    rows = list(db.scalars(query.order_by(DecisionQualityBenchmark.created_at.desc()).limit(limit)).all())
    return [serialize_quality_benchmark(row) for row in rows]


@router.post("/document-drafts", status_code=201)
def post_document_draft(
    payload: DocumentDraftCreateRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        require_notebook_access(db, notebook_id=payload.notebook_id, actor_id=actor_id, minimum_role="editor")
        return serialize_document_draft(create_document_draft(db, **payload.model_dump()))
    except Exception as exc:
        _service_error(exc)


@router.get("/document-drafts")
def get_document_drafts(
    notebook_id: UUID,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> list[dict]:
    require_notebook_access(db, notebook_id=notebook_id, actor_id=actor_id)
    rows = list(
        db.scalars(
            select(DecisionDocumentDraft)
            .where(DecisionDocumentDraft.notebook_id == notebook_id)
            .order_by(DecisionDocumentDraft.updated_at.desc())
        ).all()
    )
    return [serialize_document_draft(row) for row in rows]


@router.put("/document-drafts/{draft_id}/blocks")
def put_document_block(
    draft_id: UUID,
    payload: DocumentBlockUpdateRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        draft = _document_draft(db, draft_id, actor_id, role="editor")
        values = payload.model_dump(exclude={"owner"})
        return serialize_document_draft(update_document_block(db, draft=draft, actor_id=actor_id, **values))
    except Exception as exc:
        _service_error(exc)


@router.post("/document-drafts/{draft_id}/regenerate")
def post_document_regeneration(
    draft_id: UUID,
    payload: DocumentRegenerateRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        draft = _document_draft(db, draft_id, actor_id, role="editor")
        return serialize_document_draft(
            regenerate_document_blocks(db, draft=draft, actor_id=actor_id, **payload.model_dump())
        )
    except Exception as exc:
        _service_error(exc)


@router.post("/document-drafts/{draft_id}/export")
def post_document_export(
    draft_id: UUID,
    payload: DocumentExportRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> Response:
    try:
        draft = _document_draft(db, draft_id, actor_id, role="editor")
        filename, mime, artifact, metadata = export_document_draft(
            db,
            draft=draft,
            export_format=payload.format,
            brand_template=payload.brand_template,
        )
        return Response(
            content=artifact,
            media_type=mime,
            headers={
                "Content-Disposition": f"attachment; filename=decision-document.{payload.format}; filename*=UTF-8''{quote(filename)}",
                "X-Anti-Fomo-Artifact-Digest": str(metadata["artifact_digest"]),
                "X-Anti-Fomo-Office-Status": str(metadata["status"]),
            },
        )
    except Exception as exc:
        _service_error(exc)


@router.post("/document-drafts/{draft_id}/export-confirmation")
def post_document_export_confirmation(
    draft_id: UUID,
    payload: DocumentExportConfirmationRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        draft = _document_draft(db, draft_id, actor_id, role="reviewer")
        notebook = require_notebook_access(db, notebook_id=draft.notebook_id, actor_id=actor_id, minimum_role="reviewer")
        return serialize_document_draft(
            confirm_document_export(
                db,
                draft=draft,
                owner_user_id=notebook.user_id,
                actor_id=actor_id,
                **payload.model_dump(),
            )
        )
    except Exception as exc:
        _service_error(exc)


@router.post("/identity-profiles", status_code=201)
def post_identity_profile(
    payload: IdentityProfileCreateRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        require_space_access(db, space_id=payload.space_id, actor_id=actor_id, minimum_role="owner")
        return serialize_identity_profile(create_identity_profile(db, **payload.model_dump()))
    except Exception as exc:
        _service_error(exc)


@router.get("/identity-profiles")
def get_identity_profiles(
    space_id: UUID,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> list[dict]:
    require_space_access(db, space_id=space_id, actor_id=actor_id, minimum_role="editor")
    rows = list(db.scalars(select(EnterpriseIdentityProfile).where(EnterpriseIdentityProfile.space_id == space_id)).all())
    return [serialize_identity_profile(row) for row in rows]


@router.post("/connectors/{connector_id}/sync", status_code=201)
def post_connector_sync(
    connector_id: UUID,
    payload: ConnectorSyncRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        connector = db.get(KnowledgeConnector, connector_id)
        if connector is None:
            raise HTTPException(status_code=404, detail="Connector not found.")
        require_space_access(db, space_id=connector.space_id, actor_id=actor_id, minimum_role="editor")
        return serialize_connector_sync(record_connector_sync(db, connector=connector, actor_id=actor_id, **payload.model_dump()))
    except Exception as exc:
        _service_error(exc)


@router.post("/agent-runs", status_code=201)
def post_agent_run(
    payload: AgentRunCreateRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        user = _actor_user(db, actor_id)
        skill = db.get(GovernedSkill, payload.skill_id)
        if skill is None:
            raise HTTPException(status_code=404, detail="Skill not found.")
        if skill.user_id != user.id:
            raise AccessDeniedError("Skill access denied.")
        if payload.notebook_id:
            require_notebook_access(db, notebook_id=payload.notebook_id, actor_id=actor_id, minimum_role="editor")
        run = create_agent_run(db, skill=skill, actor_id=actor_id, **payload.model_dump(exclude={"skill_id"}))
        return serialize_agent_run(run, approvals=list_agent_approvals(db, run_id=run.id))
    except Exception as exc:
        _service_error(exc)


@router.post("/agent-runs/{run_id}/actions")
def post_agent_run_action(
    run_id: UUID,
    payload: AgentRunActionRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        run = _agent_run(db, run_id, actor_id, role="editor")
        skill = db.get(GovernedSkill, run.skill_id)
        if skill is None:
            raise HTTPException(status_code=404, detail="Skill not found.")
        row = transition_agent_run(db, run=run, skill=skill, actor_id=actor_id, **payload.model_dump())
        return serialize_agent_run(row, approvals=list_agent_approvals(db, run_id=row.id))
    except Exception as exc:
        _service_error(exc)


@router.post("/agent-approvals/{approval_id}")
def post_agent_approval(
    approval_id: UUID,
    payload: AgentApprovalDecisionRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        approval = db.get(DecisionAgentApproval, approval_id)
        if approval is None:
            raise HTTPException(status_code=404, detail="Agent approval not found.")
        _agent_run(db, approval.run_id, actor_id, role="reviewer")
        return serialize_agent_approval(
            decide_agent_approval(db, approval=approval, reviewer_id=actor_id, **payload.model_dump())
        )
    except Exception as exc:
        _service_error(exc)


@router.post("/vertical-packs/seed")
def post_vertical_pack_seed(db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> list[dict]:
    _actor_user(db, actor_id)
    return [serialize_vertical_pack(row) for row in seed_vertical_packs(db)]


@router.get("/vertical-packs")
def get_vertical_packs(db: Session = Depends(get_db), actor_id: str = Depends(_actor_id)) -> list[dict]:
    _actor_user(db, actor_id)
    return [serialize_vertical_pack(row) for row in seed_vertical_packs(db)]


@router.post("/vertical-packs/{pack_id}/benchmark")
def post_vertical_pack_benchmark(
    pack_id: UUID,
    payload: VerticalPackBenchmarkRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        _actor_user(db, actor_id)
        pack = db.get(DecisionVerticalPack, pack_id)
        if pack is None:
            raise HTTPException(status_code=404, detail="Vertical pack not found.")
        return serialize_vertical_pack(record_vertical_pack_benchmark(db, pack=pack, **payload.model_dump()))
    except Exception as exc:
        _service_error(exc)


@router.post("/customer-pilots", status_code=201)
def post_customer_pilot(
    payload: CustomerPilotCreateRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        require_space_access(db, space_id=payload.space_id, actor_id=actor_id, minimum_role="owner")
        return serialize_customer_pilot(create_customer_pilot(db, **payload.model_dump()))
    except Exception as exc:
        _service_error(exc)


@router.get("/customer-pilots")
def get_customer_pilots(
    space_id: UUID,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> list[dict]:
    require_space_access(db, space_id=space_id, actor_id=actor_id)
    rows = list(
        db.scalars(
            select(DecisionCustomerPilot)
            .where(DecisionCustomerPilot.space_id == space_id)
            .order_by(DecisionCustomerPilot.updated_at.desc())
        ).all()
    )
    return [serialize_customer_pilot(row) for row in rows]


@router.post("/customer-pilots/{pilot_id}/actions")
def post_customer_pilot_action(
    pilot_id: UUID,
    payload: CustomerPilotUpdateRequest,
    db: Session = Depends(get_db),
    actor_id: str = Depends(_actor_id),
) -> dict:
    try:
        user = _actor_user(db, actor_id)
        pilot = db.get(DecisionCustomerPilot, pilot_id)
        if pilot is None:
            raise HTTPException(status_code=404, detail="Customer Pilot not found.")
        require_space_access(db, space_id=pilot.space_id, actor_id=actor_id, minimum_role="owner")
        return serialize_customer_pilot(update_customer_pilot(db, pilot=pilot, user_id=user.id, **payload.model_dump()))
    except Exception as exc:
        _service_error(exc)
