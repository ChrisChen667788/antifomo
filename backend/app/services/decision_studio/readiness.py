from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from typing import Any, Literal
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.decision_studio_entities import (
    DecisionArtifact,
    DecisionClaim,
    DecisionDocumentContract,
    DecisionNotebook,
    DecisionPassage,
    DecisionSection,
    DecisionSource,
    DecisionSourceRevision,
    GovernedSkill,
    KnowledgeConnector,
    KnowledgeSpace,
)
from app.services.decision_studio.artifacts import audit_artifact_consistency
from app.services.decision_studio.claim_graph import claim_evidence_findings
from app.services.decision_studio.validation import build_release_program_snapshot
from app.services.release_readiness_service import build_release_readiness_snapshot


GateStatus = Literal["pass", "watch", "blocked"]
DECISION_STUDIO_RELEASE_VERSION = "2.2.0-development"
PROJECT_ROOT = Path(__file__).resolve().parents[4]
STUDIO_SCREENSHOT_MANIFEST = PROJECT_ROOT / "docs" / "assets" / "screenshots" / "screenshot-manifest.json"
EXTERNAL_ACCEPTANCE_ARTIFACTS = {
    "retrieval_qrels": PROJECT_ROOT / ".tmp" / "decision-studio-retrieval-qrels.json",
    "permission_matrix": PROJECT_ROOT / ".tmp" / "decision-studio-permission-matrix.json",
    "commercial_acceptance": PROJECT_ROOT / ".tmp" / "decision-studio-commercial-acceptance.json",
}


def _gate(
    key: str,
    label: str,
    status: GateStatus,
    score: int,
    observed: str,
    target: str,
    actions: list[str],
    details: dict[str, object] | None = None,
) -> dict[str, object]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "score": max(0, min(100, score)),
        "observed": observed,
        "target": target,
        "summary": observed,
        "evidence": [{"label": label, "status": status, "summary": observed, "details": details or {}}],
        "actions": [
            {"priority": "high" if status == "blocked" else "medium", "owner": "decision-studio", "action": action, "reason": observed}
            for action in actions
        ],
    }


def _notebook_ids(db: Session, notebook_id: UUID | None) -> list[UUID]:
    if notebook_id is not None:
        return [notebook_id]
    return list(db.scalars(select(DecisionNotebook.id)).all())


def _semantic_gate(db: Session, notebook_ids: list[UUID]) -> dict[str, object]:
    if not notebook_ids:
        return _gate("semantic_retrieval", "真实语义检索", "watch", 0, "尚无 Notebook。", "真实向量覆盖当前段落 100%。", ["创建 Notebook 并导入资料。"])
    rows = db.execute(
        select(DecisionPassage.embedding, DecisionPassage.embedding_model)
        .join(DecisionSourceRevision, DecisionSourceRevision.id == DecisionPassage.revision_id)
        .join(DecisionSource, DecisionSource.id == DecisionSourceRevision.source_id)
        .where(DecisionSource.notebook_id.in_(notebook_ids))
        .where(DecisionSource.current_revision_id == DecisionSourceRevision.id)
    ).all()
    total = len(rows)
    indexed = sum(1 for embedding, model in rows if embedding and model)
    models = sorted({str(model) for _embedding, model in rows if model})
    coverage = indexed / total if total else 0.0
    if not total:
        status: GateStatus = "watch"
    elif coverage == 1.0:
        status = "pass"
    else:
        status = "blocked"
    return _gate(
        "semantic_retrieval",
        "真实语义检索",
        status,
        round(coverage * 100),
        f"当前段落 {total}，真实向量 {indexed}，覆盖率 {coverage:.1%}，模型 {models or ['none']}。",
        "当前来源段落真实向量覆盖 100%，查询与索引模型一致。",
        [] if status == "pass" else ["运行 Notebook 语义索引并确认真实模型可用。"],
        {"passage_count": total, "indexed_count": indexed, "models": models},
    )


def _contract_gate(db: Session, notebook_ids: list[UUID]) -> dict[str, object]:
    contracts = list(
        db.scalars(select(DecisionDocumentContract).where(DecisionDocumentContract.notebook_id.in_(notebook_ids))).all()
    ) if notebook_ids else []
    if not contracts:
        return _gate("document_contracts", "中国正式文档合同", "watch", 0, "尚未创建正式文档合同。", "必填资料缺口为 0，公式均有输入血缘。", ["选择政策包创建文档合同。"])
    gaps = sum(len(contract.gaps_payload or []) for contract in contracts)
    calculations = [item for contract in contracts for item in list(contract.calculations_payload or [])]
    broken_calculations = sum(
        1
        for calculation in calculations
        if any(not input_item.get("source_refs") and not input_item.get("assumption_ref") for input_item in calculation.get("inputs", []))
    )
    status: GateStatus = "pass" if gaps == 0 and broken_calculations == 0 else "blocked"
    score = 100 if status == "pass" else max(0, 100 - gaps * 2 - broken_calculations * 20)
    return _gate(
        "document_contracts",
        "中国正式文档合同",
        status,
        score,
        f"合同 {len(contracts)}，资料缺口 {gaps}，无血缘公式 {broken_calculations}。",
        "必填资料缺口为 0，公式均有来源或假设血缘。",
        [] if status == "pass" else ["补齐必填字段并处理资料缺口。", "为每个公式输入绑定来源或假设。"],
    )


def _claim_gate(db: Session, notebook_ids: list[UUID]) -> dict[str, object]:
    claims = list(db.scalars(select(DecisionClaim).where(DecisionClaim.notebook_id.in_(notebook_ids))).all()) if notebook_ids else []
    accepted = [claim for claim in claims if claim.status == "accepted"]
    cited = [claim for claim in accepted if claim.passage_ids]
    critical_uncited = [claim for claim in accepted if claim.criticality == "critical" and not claim.passage_ids]
    invalid_citations = claim_evidence_findings(db, accepted)
    sections = list(db.scalars(select(DecisionSection).where(DecisionSection.notebook_id.in_(notebook_ids))).all()) if notebook_ids else []
    blocked_sections = [section for section in sections if section.status == "blocked"]
    coverage = len(cited) / len(accepted) if accepted else 0.0
    if not accepted:
        status: GateStatus = "watch"
    elif critical_uncited or invalid_citations or blocked_sections:
        status = "blocked"
    elif coverage < 0.95:
        status = "watch"
    else:
        status = "pass"
    return _gate(
        "claim_graph",
        "Claim Graph 与章节编译",
        status,
        round(coverage * 100),
        f"已接受 Claim {len(accepted)}，段落引用覆盖 {coverage:.1%}，失效引用 {len(invalid_citations)}，阻断章节 {len(blocked_sections)}。",
        "关键 Claim 引用 100%，全部 Claim 引用不低于 95%，跨章冲突为 0。",
        [] if status == "pass" else ["补齐 Claim 段落引用并重新编译阻断章节。"],
    )


def _knowledge_gate(db: Session) -> dict[str, object]:
    spaces = int(db.scalar(select(func.count(KnowledgeSpace.id))) or 0)
    connectors = list(db.scalars(select(KnowledgeConnector)).all())
    ready_connectors = sum(1 for connector in connectors if connector.status == "ready")
    sources = list(db.scalars(select(DecisionSource).where(DecisionSource.admission_status == "accepted")).all())
    untrusted_sources = [
        source
        for source in sources
        if source.trust_status != "verified" or not source.owner_label.strip()
    ]
    if untrusted_sources:
        status: GateStatus = "blocked"
    elif not spaces:
        status = "watch"
    elif connectors and ready_connectors != len(connectors):
        status = "blocked"
    else:
        status = "pass"
    score = 100 if status == "pass" else (40 if untrusted_sources else (50 if spaces else 0))
    return _gate(
        "knowledge_spaces",
        "Knowledge Space、ACL 与连接器",
        status,
        score,
        f"Knowledge Space {spaces}，可信来源 {len(sources) - len(untrusted_sources)}/{len(sources)}，连接器 {len(connectors)}，dry-run ready {ready_connectors}。",
        "来源责任人和有效期可信，空间 ACL 生效，已配置连接器全部通过 allowlist dry-run。",
        [] if status == "pass" else ["验证来源责任人/有效期，并完成 Knowledge Space 与连接器权限 dry-run。"],
    )


def _skill_gate(db: Session) -> dict[str, object]:
    skills = list(db.scalars(select(GovernedSkill)).all())
    approved = [skill for skill in skills if skill.status == "approved"]
    benchmarked = [skill for skill in approved if skill.benchmark_payload]
    if not skills:
        status: GateStatus = "watch"
    elif len(approved) != len(skills) or len(benchmarked) != len(approved):
        status = "blocked"
    else:
        status = "pass"
    score = round(100 * len(approved) / len(skills)) if skills else 0
    return _gate(
        "governed_skills",
        "签名 Skill 与权限沙箱",
        status,
        score,
        f"Skill {len(skills)}，签名且 benchmark 后批准 {len(approved)}。",
        "启用的 Skill 100% 签名、benchmark 通过并完成最小权限 dry-run。",
        [] if status == "pass" else ["配置签名密钥，记录 benchmark 并批准通过验证的 Skill。"],
    )


def _artifact_gate(db: Session, notebook_ids: list[UUID]) -> dict[str, object]:
    artifacts = list(db.scalars(select(DecisionArtifact).where(DecisionArtifact.notebook_id.in_(notebook_ids))).all()) if notebook_ids else []
    stale = [artifact for artifact in artifacts if artifact.stale]
    audits = [audit_artifact_consistency(db, notebook_id=value) for value in notebook_ids]
    blocked_audits = [audit for audit in audits if audit["status"] == "blocked"]
    if not artifacts:
        status: GateStatus = "watch"
    elif stale or blocked_audits:
        status = "blocked"
    else:
        status = "pass"
    current = len(artifacts) - len(stale)
    score = round(100 * current / len(artifacts)) if artifacts else 0
    return _gate(
        "decision_artifacts",
        "证据绑定多形态 Studio",
        status,
        score,
        f"产物 {len(artifacts)}，当前有效 {current}，跨形态一致性阻断 {len(blocked_audits)}。",
        "所有发布产物绑定当前来源修订，关键 Claim 跨形态覆盖 100%。",
        [] if status == "pass" else ["重建 stale 产物并修复跨形态 Claim 一致性。"],
    )


def _studio_visual_gate() -> dict[str, object]:
    payload: dict[str, object] = {}
    if STUDIO_SCREENSHOT_MANIFEST.exists():
        try:
            loaded = json.loads(STUDIO_SCREENSHOT_MANIFEST.read_text(encoding="utf-8"))
            payload = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError):
            payload = {}
    rows = [row for row in list(payload.get("screenshots") or []) if isinstance(row, dict)]
    studio_rows = [
        row
        for row in rows
        if "/studio" in str(row.get("route") or row.get("url") or row.get("path") or row.get("file") or "")
    ]
    themes = {str(row.get("theme") or "") for row in studio_rows}
    version = str(payload.get("version") or "")
    supported_version = version.startswith(("2.0.5", "2.0.6", "2.0.7", "2.1.", "2.2."))
    passed = supported_version and {"light", "dark"}.issubset(themes)
    return _gate(
        "studio_visual_baseline",
        "Decision Studio 视觉基线",
        "pass" if passed else "blocked",
        100 if passed else 0,
        f"manifest version={version or 'missing'}，/studio captures={len(studio_rows)}，themes={sorted(themes)}。",
        "2.0.5+ manifest 包含 /studio 日间与夜间人工确认截图。",
        [] if passed else ["生成 /studio 日间/夜间截图，完成人工视觉确认并更新 2.0.5+ manifest。"],
        {"manifest": str(STUDIO_SCREENSHOT_MANIFEST)},
    )


def _external_acceptance_gate() -> dict[str, object]:
    states: dict[str, str] = {}
    for key, path in EXTERNAL_ACCEPTANCE_ARTIFACTS.items():
        status = "missing"
        if path.exists():
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
                status = str(payload.get("status") or "unknown") if isinstance(payload, dict) else "invalid"
            except (OSError, json.JSONDecodeError):
                status = "invalid"
        states[key] = status
    passed = all(status in {"pass", "passed", "approved"} for status in states.values())
    return _gate(
        "external_commercial_acceptance",
        "外部评测与商业验收",
        "pass" if passed else "blocked",
        100 if passed else 0,
        "，".join(f"{key}={status}" for key, status in states.items()),
        "300-query human qrels、跨面权限矩阵和真实客户商业验收 artifact 全部通过。",
        [] if passed else ["完成真实 qrels、权限泄漏矩阵和客户验收，生成带审阅者声明的独立 artifacts。"],
        {key: str(path) for key, path in EXTERNAL_ACCEPTANCE_ARTIFACTS.items()},
    )


def _release_program_gate(db: Session, *, user_id: UUID) -> dict[str, object]:
    program = build_release_program_snapshot(db, user_id=user_id)
    milestones = list(program["milestones"])
    accepted = [row for row in milestones if row["acceptance_status"] == "pass"]
    blockers = [
        f"{row['version']} / {suite['label']}: {', '.join(suite['blockers'][:2])}"
        for row in milestones
        for suite in row["suites"]
        if suite["status"] != "pass"
    ]
    return _gate(
        "post_2_0_release_program",
        "2.0.1-2.0.6 版本验收程序",
        program["overall_status"],
        int(program["readiness_score"]),
        f"六个版本工程实现完成；验收通过 {len(accepted)}/{len(milestones)}，不可变验证运行按 suite 聚合。",
        "2.0.1-2.0.6 全部 suite 具备达标指标和对应人工/专家/安全/视觉原始证据。",
        blockers[:8] or [],
        {"milestones": milestones, "release_version": program["release_version"]},
    )


def build_decision_studio_readiness(
    db: Session,
    *,
    notebook_id: UUID | None = None,
    user_id: UUID | None = None,
) -> dict[str, Any]:
    inherited = build_release_readiness_snapshot(db)
    notebook_ids = _notebook_ids(db, notebook_id)
    gates = [
        _semantic_gate(db, notebook_ids),
        _contract_gate(db, notebook_ids),
        _claim_gate(db, notebook_ids),
        _knowledge_gate(db),
        _skill_gate(db),
        _artifact_gate(db, notebook_ids),
        _studio_visual_gate(),
        _external_acceptance_gate(),
        _release_program_gate(db, user_id=user_id or UUID("00000000-0000-0000-0000-000000000001")),
    ]
    inherited_status: GateStatus = inherited["overall_status"]
    inherited_gate = _gate(
        "inherited_release_readiness",
        "1.9.1 既有发布门禁",
        inherited_status,
        int(inherited["readiness_score"]),
        f"既有门禁为 {inherited_status}；专家校准、三行业盲测与客户验收不由代码自动放行。",
        "既有 release-readiness 全部通过。",
        [] if inherited_status == "pass" else ["按既有 readiness actions 完成外部复核和客户验收。"],
        {"release_version": inherited["release_version"]},
    )
    all_gates = [inherited_gate, *gates]
    blocked = sum(1 for gate in all_gates if gate["status"] == "blocked")
    watch = sum(1 for gate in all_gates if gate["status"] == "watch")
    passed = sum(1 for gate in all_gates if gate["status"] == "pass")
    overall: GateStatus = "blocked" if blocked else ("watch" if watch else "pass")
    score = round(sum(int(gate["score"]) for gate in all_gates) / max(1, len(all_gates)))
    next_actions = [
        {**action, "gate_key": gate["key"], "gate_label": gate["label"]}
        for gate in all_gates
        if gate["status"] != "pass"
        for action in list(gate["actions"])
    ]
    return {
        "generated_at": datetime.now(UTC),
        "release_version": DECISION_STUDIO_RELEASE_VERSION,
        "overall_status": overall,
        "readiness_score": score,
        "summary_lines": [
            f"2.0.6 Decision Studio：{passed} pass / {watch} watch / {blocked} blocked。",
            f"总体 readiness score {score}/100，overall_status={overall}。",
            "2.0.1-2.0.6 工程能力与商业发布证据分开判定；既有人工门禁继续保持真实状态。",
        ],
        "gates": all_gates,
        "next_actions": next_actions,
        "inherited_readiness": inherited,
    }
