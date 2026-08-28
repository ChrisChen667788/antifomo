from __future__ import annotations

from datetime import UTC, datetime
import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Iterable, Literal

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.services.research.evaluation_dataset import DATASET_PATH, load_research_evaluation_dataset
from app.services.research.evaluation_review import (
    ResearchEvaluationReviewArtifact,
    validate_research_evaluation_review,
)
from app.services.research.expert_calibration import (
    ExpertCalibrationArtifact,
    validate_expert_calibration,
)
from app.schemas.research import ResearchReportResponse, ResearchSourceOut
from app.services.research.evidence_governance import (
    build_research_claim_governance,
    build_research_evidence_governance,
)
from app.services.research.source_documents import SourceDocument
from app.services.research_review_service import list_low_quality_research_review_queue
from app.services.research_upgrade_diagnostics_service import build_research_upgrade_diagnostics
from app.services.research.hard_failure_policy import evaluate_research_hard_failures
from app.services.research_experience_service import build_research_experience_readiness
from app.services.research_assurance_service import build_research_assurance_snapshot
from app.services.industry_knowledge_retrieval_assurance import (
    build_industry_knowledge_retrieval_assurance_snapshot,
)
from app.services.industry_knowledge_retrieval_evidence_operations import (
    DEFAULT_HANDOFF_PATH,
    DEFAULT_INCIDENT_PATH,
    DEFAULT_REVOCATION_PATH,
    build_industry_knowledge_retrieval_evidence_operations_snapshot,
)
from app.services.delivery.decision_engineering import (
    build_reference_architecture_decision_engineering,
    validate_architecture_decision_engineering,
)
from app.services.delivery.executable_validation import (
    DEFAULT_PROOF_ARTIFACT_PATH,
    load_reference_proof_artifact,
)


ReleaseGateStatus = Literal["pass", "watch", "blocked"]
ReleaseActionPriority = Literal["high", "medium", "low"]

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_REVIEW_PATH = PROJECT_ROOT / ".tmp" / "research-evaluation-independent-review.json"
DEFAULT_CALIBRATION_PATH = PROJECT_ROOT / ".tmp" / "research-evaluation-expert-calibration.json"
DEFAULT_STABILITY_REPORT_PATH = PROJECT_ROOT / ".tmp" / "stability_smoke_report.json"
DEFAULT_SCREENSHOT_MANIFEST_PATH = PROJECT_ROOT / "docs" / "assets" / "screenshots" / "screenshot-manifest.json"
DEFAULT_VISUAL_MANIFEST_PATHS = (
    PROJECT_ROOT / ".tmp" / "formal-artifact-visual-baseline" / "visual-baseline-manifest.json",
    PROJECT_ROOT / ".tmp" / "formal-artifact-visual-baseline" / "roundtrip-manifest.json",
    Path("/tmp/af-p25-office/roundtrip-manifest.json"),
    Path("/tmp/af-p26-real-business-baseline/visual-baseline-manifest.json"),
    Path("/tmp/af-p26-real-business-baseline/roundtrip-manifest.json"),
    Path("/tmp/af-p27-real-business-baseline/visual-baseline-manifest.json"),
    Path("/tmp/af-p27-real-business-baseline/roundtrip-manifest.json"),
)

LOW_QUALITY_TARGET_RATE = 0.10
LOW_QUALITY_LEGACY_BASELINE_RATE = 0.303
DIAGNOSTICS_TARGET_SCORE = 80
STALE_STABILITY_ARTIFACT_DAYS = 3
RELEASE_SEMVER = "2.9.5"
RELEASE_VERSION = "2.9.5-retrieval-evidence-operations-command-center"


def _action(priority: ReleaseActionPriority, owner: str, action: str, reason: str) -> dict[str, str]:
    return {
        "priority": priority,
        "owner": owner,
        "action": action,
        "reason": reason,
    }


def _command(gate_key: str, gate_label: str, label: str, command: str, purpose: str) -> dict[str, str]:
    return {
        "gate_key": gate_key,
        "gate_label": gate_label,
        "label": label,
        "command": command,
        "purpose": purpose,
    }


def _artifact(
    gate_key: str,
    gate_label: str,
    label: str,
    path: Path,
    status: ReleaseGateStatus,
    summary: str,
) -> dict[str, Any]:
    return {
        "gate_key": gate_key,
        "gate_label": gate_label,
        "label": label,
        "path": str(path),
        "exists": path.exists(),
        "status": status,
        "summary": summary,
    }


def _evidence(
    label: str,
    status: ReleaseGateStatus,
    summary: str,
    *,
    source: str = "",
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "label": label,
        "status": status,
        "summary": summary,
        "source": source,
        "details": details or {},
    }


def _gate(
    key: str,
    label: str,
    status: ReleaseGateStatus,
    score: int,
    target: str,
    observed: str,
    summary: str,
    evidence: list[dict[str, Any]],
    actions: list[dict[str, str]],
) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "status": status,
        "score": max(0, min(100, int(score))),
        "target": target,
        "observed": observed,
        "summary": summary,
        "evidence": evidence,
        "actions": actions,
    }


def _read_json(path: Path) -> dict[str, Any] | list[Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _parse_datetime(value: object) -> datetime | None:
    if not value:
        return None
    try:
        text_value = str(value)
        if text_value.endswith("Z"):
            text_value = f"{text_value[:-1]}+00:00"
        parsed = datetime.fromisoformat(text_value)
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=UTC)
        return parsed.astimezone(UTC)
    except ValueError:
        return None


def _status_from_artifact(value: object) -> ReleaseGateStatus:
    normalized = str(value or "").strip().casefold()
    if normalized in {"pass", "passed", "ok", "accepted", "ready", "approved"}:
        return "pass"
    if normalized in {"fail", "failed", "error", "timeout", "blocked", "rejected"}:
        return "blocked"
    return "watch"


def _status_is_blocking(value: object) -> bool:
    return str(value or "").strip().casefold() in {"fail", "failed", "error", "timeout", "blocked", "rejected"}


def _collect_statuses(payload: Any) -> list[ReleaseGateStatus]:
    statuses: list[ReleaseGateStatus] = []
    if isinstance(payload, dict):
        if "status" in payload:
            statuses.append(_status_from_artifact(payload.get("status")))
        for value in payload.values():
            statuses.extend(_collect_statuses(value))
    elif isinstance(payload, list):
        for item in payload:
            statuses.extend(_collect_statuses(item))
    return statuses


def _evaluate_visual_baseline_manifest(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    artifacts = list(payload.get("artifacts") or [])
    failed_validation = int(summary.get("failed_validation_count") or 0)
    failed_quicklook = int(summary.get("failed_quicklook_count") or 0)
    artifact_count = int(summary.get("artifact_count") or len(artifacts))
    blocked_rows = [
        row
        for row in artifacts
        if isinstance(row, dict)
        and (
            _status_is_blocking(row.get("validation", {}).get("status") if isinstance(row.get("validation"), dict) else "")
            or _status_is_blocking(row.get("quicklook", {}).get("status") if isinstance(row.get("quicklook"), dict) else "")
        )
    ]
    if failed_validation or failed_quicklook or blocked_rows:
        status: ReleaseGateStatus = "blocked"
    elif artifact_count and artifacts:
        status = "pass"
    else:
        status = "watch"
    return _evidence(
        path.name,
        status,
        f"视觉基线 artifact={artifact_count}，validation failures={failed_validation}，quicklook failures={failed_quicklook}。",
        source=str(path),
        details={
            "baseline_id": payload.get("baseline_id"),
            "artifact_count": artifact_count,
            "sample_count": summary.get("sample_count"),
            "failed_validation_count": failed_validation,
            "failed_quicklook_count": failed_quicklook,
        },
    )


def _evaluate_roundtrip_manifest(path: Path, payload: dict[str, Any]) -> dict[str, Any]:
    artifacts = [row for row in list(payload.get("artifacts") or []) if isinstance(row, dict)]
    structure_failures = [row.get("file") for row in artifacts if _status_is_blocking(row.get("status"))]
    quicklook_failures = [
        row.get("file")
        for row in artifacts
        if isinstance(row.get("quicklook"), dict) and _status_is_blocking(row["quicklook"].get("status"))
    ]
    conversion_failures = [
        row.get("file")
        for row in artifacts
        if isinstance(row.get("libreoffice_conversion"), dict)
        and _status_is_blocking(row["libreoffice_conversion"].get("status"))
    ]
    if structure_failures or quicklook_failures or conversion_failures:
        status: ReleaseGateStatus = "blocked"
    elif artifacts:
        status = "pass"
    else:
        status = "watch"
    quicklook_rendered = sum(
        1
        for row in artifacts
        if isinstance(row.get("quicklook"), dict) and row["quicklook"].get("status") == "pass"
    )
    libreoffice_skipped = sum(
        1
        for row in artifacts
        if isinstance(row.get("libreoffice_conversion"), dict)
        and row["libreoffice_conversion"].get("status") == "skip"
    )
    return _evidence(
        path.name,
        status,
        f"Office roundtrip artifact={len(artifacts)}，structure failures={len(structure_failures)}，quicklook failures={len(quicklook_failures)}。",
        source=str(path),
        details={
            "artifact_count": len(artifacts),
            "quicklook_rendered": quicklook_rendered,
            "libreoffice_skipped": libreoffice_skipped,
            "structure_failure_count": len(structure_failures),
            "quicklook_failure_count": len(quicklook_failures),
            "libreoffice_failure_count": len(conversion_failures),
        },
    )


def _evaluate_visual_manifest_payload(path: Path, payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return _evidence(path.name, "watch", "manifest 不是可解析 JSON object。", source=str(path))
    if payload.get("baseline_id") or payload.get("dataset"):
        return _evaluate_visual_baseline_manifest(path, payload)
    if isinstance(payload.get("artifacts"), list):
        return _evaluate_roundtrip_manifest(path, payload)
    statuses = _collect_statuses(payload)
    if any(status == "blocked" for status in statuses):
        status: ReleaseGateStatus = "blocked"
    elif statuses and all(status == "pass" for status in statuses):
        status = "pass"
    else:
        status = "watch"
    return _evidence(path.name, status, f"解析到 {len(statuses)} 个状态字段，当前为 {status}。", source=str(path))


def _latest_stability_evidence(now: datetime, report_path: Path) -> tuple[ReleaseGateStatus, dict[str, Any]]:
    payload = _read_json(report_path)
    if not isinstance(payload, dict):
        return (
            "watch",
            _evidence(
                "Stability smoke artifact",
                "watch",
                "未找到最近 stability smoke 报告，发布前需要重跑 `npm run stability:smoke`。",
                source=str(report_path),
            ),
        )
    artifact_status = _status_from_artifact(payload.get("status"))
    generated_at = _parse_datetime(payload.get("generatedAt") or payload.get("generated_at"))
    age_days = (now - generated_at).days if generated_at else None
    stale = age_days is None or age_days > STALE_STABILITY_ARTIFACT_DAYS
    if artifact_status == "blocked":
        status: ReleaseGateStatus = "blocked"
    elif stale:
        status = "watch"
    else:
        status = artifact_status
    age_text = f"{age_days} 天前" if age_days is not None else "时间未知"
    return (
        status,
        _evidence(
            "Stability smoke artifact",
            status,
            f"最近 stability smoke 为 `{payload.get('status', 'unknown')}`，生成于 {age_text}。",
            source=str(report_path),
            details={
                "passed": payload.get("passed"),
                "failed": payload.get("failed"),
                "generated_at": payload.get("generatedAt") or payload.get("generated_at"),
            },
        ),
    )


def _build_health_gate(db: Session, now: datetime, stability_report_path: Path) -> dict[str, Any]:
    evidence: list[dict[str, Any]] = []
    actions: list[dict[str, str]] = []
    db_ok = True
    try:
        db.execute(text("SELECT 1")).scalar_one()
    except Exception as exc:
        db_ok = False
        evidence.append(
            _evidence(
                "Database connectivity",
                "blocked",
                f"数据库探针失败：{exc}",
            )
        )
    if db_ok:
        evidence.append(_evidence("API health", "pass", "`/healthz` 可由当前 FastAPI 进程提供。", source="/healthz"))
        evidence.append(_evidence("Database connectivity", "pass", "SQLAlchemy `SELECT 1` 探针通过。"))

    stability_status, stability_evidence = _latest_stability_evidence(now, stability_report_path)
    evidence.append(stability_evidence)
    if not db_ok:
        status: ReleaseGateStatus = "blocked"
        score = 20
        summary = "系统健康探针未通过。"
        actions.append(_action("high", "platform", "修复 API/数据库健康探针", "release-readiness 不能在基础健康失败时放行。"))
    elif stability_status == "blocked":
        status = "blocked"
        score = 45
        summary = "基础 API 可用，但 stability smoke 最近失败。"
        actions.append(_action("high", "qa", "重跑并修复 stability smoke", "`npm run stability:smoke` 最近报告失败。"))
    elif stability_status == "watch":
        status = "watch"
        score = 75
        summary = "基础 API 和数据库可用，但 stability smoke 需要刷新。"
        actions.append(_action("medium", "qa", "刷新 stability smoke 报告", "当前 smoke artifact 缺失或超过刷新窗口。"))
    else:
        status = "pass"
        score = 100
        summary = "API、数据库和最近 stability smoke 均通过。"
    return _gate(
        "health",
        "系统健康与稳定性",
        status,
        score,
        "API/DB healthy, recent stability smoke passed",
        "API route responding",
        summary,
        evidence,
        actions,
    )


def _build_diagnostics_gate() -> dict[str, Any]:
    diagnostics = build_research_upgrade_diagnostics()
    diagnostics_status = str(diagnostics.get("status") or "watch")
    score = int(diagnostics.get("readiness_score") or 0)
    rounds = list(diagnostics.get("roadmap_rounds") or [])
    blocked = sum(1 for item in rounds if str(item.get("status")) == "blocked")
    ready = sum(1 for item in rounds if str(item.get("status")) == "ready")
    status: ReleaseGateStatus = "pass" if diagnostics_status == "ready" and score >= DIAGNOSTICS_TARGET_SCORE else "watch"
    if diagnostics_status == "blocked" or blocked:
        status = "blocked"
    actions = [
        _action(
            str(item.get("priority") or "medium"),  # type: ignore[arg-type]
            str(item.get("owner") or "research"),
            str(item.get("action") or "补齐 research diagnostics"),
            str(item.get("reason") or "研究升级诊断仍有待处理项。"),
        )
        for item in list(diagnostics.get("fallback_actions") or [])[:4]
    ]
    return _gate(
        "research_diagnostics",
        "Research Upgrade Diagnostics",
        status,
        score,
        f"status=ready and score>={DIAGNOSTICS_TARGET_SCORE}",
        f"{score}/100 · {diagnostics_status}",
        f"15 轮研究升级诊断 ready {ready}/{len(rounds)}，blocked {blocked}/{len(rounds)}。",
        [
            _evidence(
                "Diagnostics preview",
                status,
                "复用 `/api/research/upgrade-diagnostics/preview` 的确定性 diagnostics payload。",
                source="/api/research/upgrade-diagnostics/preview",
                details={
                    "readiness_score": score,
                    "status": diagnostics_status,
                    "roadmap_rounds": len(rounds),
                    "summary_lines": diagnostics.get("summary_lines") or [],
                },
            )
        ],
        actions,
    )


def _build_evidence_governance_gate() -> dict[str, Any]:
    scope_hints = {
        "regions": ["上海"],
        "industries": ["医疗", "大模型", "人工智能"],
        "industry_methodology_profile": "医疗",
        "industry_methodology_questions": [
            "医疗AI的临床和运营需求是什么？",
            "政策与试点信号是什么？",
            "医院采购、预算和组织入口是什么？",
            "方案、厂商和竞争格局是什么？",
        ],
        "strategy_must_include_terms": ["医疗", "医院", "卫健", "临床"],
    }

    def source(title: str, body: str, domain: str, tier: str = "media") -> SourceDocument:
        return SourceDocument(
            title=title,
            url=f"https://{domain}/evidence",
            domain=domain,
            snippet=body,
            search_query="上海 医疗 AI",
            source_type="policy" if tier == "official" else "web",
            content_status="extracted",
            excerpt=body,
            source_label=domain,
            source_tier=tier,
        )

    negative = build_research_evidence_governance(
        [
            source("Codex model update", "Codex adds coding models and developer tooling.", "tech-a.example"),
            source("OpenAI account policy", "OpenAI updates access policy for coding tools.", "tech-b.example"),
        ],
        keyword="2026年下半年上海医疗行业AI潜在需求行业调研及商机情报分析",
        research_focus=None,
        research_mode="deep",
        scope_hints=scope_hints,
    )
    positive_sources = [
        source("上海医疗AI试点", "上海卫健委发布医疗AI临床试点政策和行动计划。", "wsjkw.sh.gov.cn", "official"),
        source("医院采购意向", "上海医院信息科发布医疗AI系统采购意向、预算和招标项目。", "ccgp-sh.gov.cn", "official"),
        source("医院平台方案", "上海医院医疗AI平台架构、系统集成方案和厂商合作要求。", "hospital-a.cn", "official"),
        source("临床需求", "医疗AI用于临床诊疗、医务运营和科研教学场景。", "med-research.cn"),
        source("投入产出", "医院医疗AI投资成本、实施周期、ROI收益和扩容测算。", "health-economics.cn"),
        source("数据安全", "医疗AI涉及患者数据安全、隐私合规、模型审计和交付风险。", "cac-health.gov.cn", "official"),
        source("厂商竞争", "医疗AI产品、平台厂商、竞品、标杆案例和生态伙伴竞争格局。", "medical-market.cn"),
        source("医院运维", "医疗AI系统上线后的运维绩效、交付周期和院内扩容路径。", "hospital-b.cn"),
    ]
    positive = build_research_evidence_governance(
        positive_sources,
        keyword="2026年下半年上海医疗行业AI需求与商机分析",
        research_focus="临床场景、医院采购和解决方案",
        research_mode="deep",
        scope_hints=scope_hints,
    )
    claim_text = "上海市第一人民医院2026年医疗AI系统采购预算为100万元"
    claim_report = ResearchReportResponse(
        keyword="上海医疗AI采购",
        output_language="zh-CN",
        research_mode="deep",
        report_title="上海医疗AI采购研判",
        executive_summary=claim_text,
        consulting_angle="用于核验采购窗口和预算。",
        source_count=1,
        sources=[
            ResearchSourceOut(
                title="上海市第一人民医院医疗AI采购公告",
                url="https://hospital.example/procurement",
                domain="hospital.example",
                snippet=claim_text,
                search_query="上海 医疗 AI 采购",
                source_type="procurement",
                content_status="extracted",
                source_label="医院官网",
                source_tier="official",
            )
        ],
        generated_at=datetime.now(UTC),
    )
    claim_gate = build_research_claim_governance(claim_report).citation_gate
    passed = (
        negative.gate.status == "blocked_topic_mismatch"
        and negative.gate.accepted_source_count == 0
        and positive.gate.passed
        and positive.question_tree.coverage_percent >= 80
        and claim_gate.passed
    )
    status: ReleaseGateStatus = "pass" if passed else "blocked"
    actions = [] if passed else [
        _action(
            "high",
            "report-quality",
            "修复 evidence governance 回归",
            "医疗硬负例、正向证据包或主张引用门未达到 1.8.2/1.8.3 目标。",
        )
    ]
    return _gate(
        "evidence_governance",
        "1.8.2/1.8.3 Evidence Governance",
        status,
        100 if passed else 25,
        "hard negative blocked, positive evidence ready, claim citation gate passed",
        f"negative={negative.gate.status} · positive={positive.gate.status} · citation={claim_gate.status}",
        "主题硬门禁、问题覆盖和主张引用回归均通过。" if passed else "证据治理回归未通过。",
        [
            _evidence(
                "Evidence governance deterministic regression",
                status,
                "不调用网络或模型，验证医疗跑题硬负例、8 条正向证据包和主张级引用。",
                details={
                    "negative_status": negative.gate.status,
                    "negative_accepted": negative.gate.accepted_source_count,
                    "positive_status": positive.gate.status,
                    "positive_accepted": positive.gate.accepted_source_count,
                    "question_coverage_percent": positive.question_tree.coverage_percent,
                    "citation_status": claim_gate.status,
                    "critical_claim_coverage_percent": claim_gate.critical_claim_coverage_percent,
                },
            )
        ],
        actions,
    )


def _build_low_quality_gate(db: Session) -> dict[str, Any]:
    queue = list_low_quality_research_review_queue(db, top=12, include_resolved=False)
    total = int(queue.get("total_reports") or 0)
    flagged = int(queue.get("flagged_reports") or 0)
    invalid = int(queue.get("invalid_payloads") or 0)
    rate = flagged / total if total else 0.0
    percent = round(rate * 100, 1)
    if total == 0:
        status: ReleaseGateStatus = "watch"
        score = 60
        summary = "当前库内没有可审计研报，无法证明低质量率。"
    elif invalid:
        status = "blocked"
        score = 25
        summary = f"低质量审计发现 {invalid} 个 invalid payload。"
    elif rate <= LOW_QUALITY_TARGET_RATE:
        status = "pass"
        score = 100
        summary = f"低质量率 {percent}% 已达到 ≤10% 目标。"
    elif rate <= LOW_QUALITY_LEGACY_BASELINE_RATE:
        status = "watch"
        score = 72
        summary = f"低质量率 {percent}% 已低于历史 30.3% 基线，但未达到 ≤10%。"
    else:
        status = "blocked"
        score = 40
        summary = f"低质量率 {percent}% 高于历史 30.3% 基线。"
    actions: list[dict[str, str]] = []
    if status != "pass":
        actions.append(
            _action(
                "high" if status == "blocked" else "medium",
                "report-quality",
                "收口低质量审计队列",
                "发布目标要求 low-quality flag rate ≤10% 且 invalid payloads=0。",
            )
        )
    recommendations = list(queue.get("recommendations") or [])
    return _gate(
        "low_quality_audit",
        "低质量审计",
        status,
        score,
        "flagged/total <= 10%, invalid_payloads=0",
        f"{flagged}/{total} flagged · {invalid} invalid · {percent}%",
        summary,
        [
            _evidence(
                "Low-quality review queue",
                status,
                "复用 `/api/research/review-queue/low-quality` 的实时审计队列。",
                source="/api/research/review-queue/low-quality?top=12",
                details={
                    "total_reports": total,
                    "flagged_reports": flagged,
                    "invalid_payloads": invalid,
                    "flagged_rate": rate,
                    "issue_summary": queue.get("issue_summary") or [],
                    "recommendations": recommendations[:3],
                },
            )
        ],
        actions,
    )


def _build_independent_review_gate(review_path: Path) -> dict[str, Any]:
    actions = [
        _action(
            "high",
            "evaluation-owner",
            "完成 1.2.0 独立复核并生成 digest",
            "scope-corrected evaluation cases 不能用 pending template 代替独立批准。",
        )
    ]
    if not review_path.exists():
        return _gate(
            "independent_review",
            "独立复核",
            "blocked",
            0,
            "validated independent review complete",
            "review artifact missing",
            "未找到独立复核 artifact。",
            [
                _evidence(
                    "Independent review artifact",
                    "blocked",
                    "缺少 `.tmp/research-evaluation-independent-review.json`。",
                    source=str(review_path),
                )
            ],
            actions,
        )
    try:
        manifest, cases = load_research_evaluation_dataset(DATASET_PATH)
        artifact = ResearchEvaluationReviewArtifact.model_validate_json(review_path.read_text(encoding="utf-8"))
        result = validate_research_evaluation_review(manifest, cases, artifact)
    except Exception as exc:
        return _gate(
            "independent_review",
            "独立复核",
            "blocked",
            10,
            "validated independent review complete",
            "review validation error",
            f"独立复核 artifact 校验异常：{exc}",
            [
                _evidence(
                    "Independent review validation",
                    "blocked",
                    str(exc),
                    source=str(review_path),
                )
            ],
            actions,
        )
    status: ReleaseGateStatus = "pass" if result.independent_review_complete else "blocked"
    score = 100 if status == "pass" else round(result.approved_case_count / max(1, result.case_count) * 80)
    blockers = list(result.blockers or [])
    return _gate(
        "independent_review",
        "独立复核",
        status,
        score,
        "100/100 cases approved, reviewer metadata, attestation, digest valid",
        f"{result.approved_case_count}/{result.case_count} approved · {result.review_status}",
        "独立复核已完成。" if status == "pass" else "独立复核仍未完成，不能作为 release approval。",
        [
            _evidence(
                "Independent review validation",
                status,
                "校验 locked dataset identity、case decisions、reviewer metadata、attestation 和 content digest。",
                source=str(review_path),
                details=result.model_dump(mode="json"),
            )
        ],
        [] if status == "pass" else actions + [
            _action("medium", "evaluation-owner", "处理复核 blockers", "; ".join(blockers[:3]) or "补齐复核字段。")
        ],
    )


def _build_hard_failure_policy_gate() -> dict[str, Any]:
    def evidence_gate(status: str) -> SimpleNamespace:
        return SimpleNamespace(enforced=True, passed=False, status=status, blockers=[status])

    citation_gate = SimpleNamespace(enforced=True, passed=False, status="fail", blockers=["unsupported"])
    fallback_diagnostics = SimpleNamespace(
        generation_fallback_used=True,
        generation_notes=["generation fallback"],
    )
    missing_account_gate = SimpleNamespace(
        enforced=True,
        passed=True,
        status="evidence_ready",
        blockers=[],
        local_target_proof_count=0,
        local_decision_source_count=0,
        external_benchmark_count=0,
    )
    benchmark_only_gate = SimpleNamespace(
        enforced=True,
        passed=True,
        status="evidence_ready",
        blockers=[],
        local_target_proof_count=1,
        local_decision_source_count=0,
        external_benchmark_count=1,
    )
    account_contract = SimpleNamespace(task_type="account_intelligence")
    cases = {
        "topic_mismatch": evaluate_research_hard_failures(
            SimpleNamespace(research_evidence_gate=evidence_gate("blocked_topic_mismatch"), research_citation_gate=None)
        ),
        "minimum_evidence_failed": evaluate_research_hard_failures(
            SimpleNamespace(research_evidence_gate=evidence_gate("evidence_gap"), research_citation_gate=None)
        ),
        "unsupported_critical_claim": evaluate_research_hard_failures(
            SimpleNamespace(research_evidence_gate=None, research_citation_gate=citation_gate)
        ),
        "generation_fallback": evaluate_research_hard_failures(
            SimpleNamespace(
                research_evidence_gate=None,
                research_citation_gate=None,
                source_diagnostics=fallback_diagnostics,
            )
        ),
        "unverified_account_truth": evaluate_research_hard_failures(
            SimpleNamespace(
                research_evidence_gate=missing_account_gate,
                research_citation_gate=None,
                research_scope_contract=account_contract,
            )
        ),
        "source_topology_failed": evaluate_research_hard_failures(
            SimpleNamespace(
                research_evidence_gate=benchmark_only_gate,
                research_citation_gate=None,
                research_scope_contract=account_contract,
            )
        ),
    }
    observed_caps = {key: value.score_cap for key, value in cases.items()}
    expected_caps = {
        "topic_mismatch": 20,
        "minimum_evidence_failed": 40,
        "unsupported_critical_claim": 59,
        "generation_fallback": 45,
        "unverified_account_truth": 25,
        "source_topology_failed": 30,
    }
    passed = observed_caps == expected_caps and all(value.blocked for value in cases.values())
    status: ReleaseGateStatus = "pass" if passed else "blocked"
    return _gate(
        "hard_failure_policy",
        "1.8.4/2.3.4 硬失败分数上限",
        status,
        100 if passed else 0,
        "topic mismatch <=20, minimum evidence failure <=40, unsupported critical claim <=59, generation fallback <=45, unverified account <=25, benchmark-only topology <=30",
        ", ".join(f"{key}={value}" for key, value in observed_caps.items()),
        "六个硬失败上限由统一策略执行，且交付状态保持 blocked。" if passed else "硬失败统一策略回归失败。",
        [
            _evidence(
                "Hard-failure deterministic regression",
                status,
                "同一策略函数供质量评分、自动评测、report readiness 和方案交付使用。",
                details={"observed_caps": observed_caps, "expected_caps": expected_caps},
            )
        ],
        [] if passed else [_action("high", "report-quality", "修复统一硬失败策略", "分数上限或 blocked 状态发生回归。")],
    )


def _build_expert_calibration_gate(calibration_path: Path) -> dict[str, Any]:
    if not calibration_path.exists():
        return _gate(
            "expert_calibration",
            "1.8.4 专家盲评与校准",
            "blocked",
            0,
            "100 primary + 30 dual blind reviews, source-topology audits, paired A/B, 3 customer acceptances",
            "calibration artifact missing",
            "未找到专家校准 artifact；不能把模板视为 2.5.0 校准或客户验收证据。",
            [_evidence("Expert calibration artifact", "blocked", "缺少 100-case 质量审计与客户验收工件。", source=str(calibration_path))],
            [_action("high", "evaluation-owner", "导出并完成专家校准工件", "需真实领域评审、盲评、拓扑审计、固定证据集 A/B 和客户验收。")],
        )
    try:
        manifest, cases = load_research_evaluation_dataset(DATASET_PATH)
        artifact = ExpertCalibrationArtifact.model_validate_json(calibration_path.read_text(encoding="utf-8"))
        result = validate_expert_calibration(manifest, cases, artifact)
    except Exception as exc:
        return _gate(
            "expert_calibration",
            "1.8.4 专家盲评与校准",
            "blocked",
            5,
            "valid expert calibration artifact",
            "calibration validation error",
            f"专家校准工件校验异常：{exc}",
            [_evidence("Expert calibration validation", "blocked", str(exc), source=str(calibration_path))],
            [_action("high", "evaluation-owner", "修复专家校准工件", "Pydantic 或 digest 校验失败。")],
        )
    status: ReleaseGateStatus = "pass" if result.calibration_complete else "blocked"
    completion = (
        result.primary_completed / max(1, result.case_count) * 30
        + result.dual_review_completed / 30 * 15
        + result.auto_judge_completed / max(1, result.case_count) * 10
        + result.arbitration_completed / max(1, result.arbitration_required) * 5
        + result.quality_audit_completed / max(1, result.case_count) * 20
        + result.paired_model_prompt_completed / 30 * 10
        + result.customer_acceptance_completed / 3 * 10
    )
    return _gate(
        "expert_calibration",
        "1.8.4 专家盲评与校准",
        status,
        100 if status == "pass" else round(min(95, completion)),
        "100 primary + 30 dual blind reviews, topology/entity/account/architecture audits, paired A/B, 3 customer acceptances",
        (
            f"primary {result.primary_completed}/{result.case_count} · dual {result.dual_review_completed}/30 · "
            f"auto {result.auto_judge_completed}/{result.case_count} · quality {result.quality_audit_completed}/{result.case_count} · "
            f"paired {result.paired_model_prompt_completed}/30 · customer {result.customer_acceptance_completed}/3 · "
            f"entity {result.entity_precision_percent:.1f}% · recall {result.auto_gate_undeliverable_recall:.1%}"
        ),
        "专家、拓扑、A/B 与客户验收证据完整。" if status == "pass" else "专家、拓扑、A/B 或客户验收仍待真实完成，release 保持 blocked。",
        [
            _evidence(
                "Expert calibration validation",
                status,
                "校验盲评隔离、仲裁、实体/拓扑精度、账户与架构评分、固定证据集 A/B、客户验收、自动裁判偏差和硬上限。",
                source=str(calibration_path),
                details=result.model_dump(mode="json"),
            )
        ],
        [] if status == "pass" else [
            _action("high", "evaluation-owner", "完成真实专家、A/B 与客户验收校准", "; ".join(result.blockers[:3]))
        ],
    )


def _build_architecture_engineering_gate() -> dict[str, Any]:
    try:
        engineering = build_reference_architecture_decision_engineering()
        result = validate_architecture_decision_engineering(engineering)
    except Exception as exc:
        result = {"status": "blocked", "blockers": [str(exc)]}
    passed = result.get("status") == "pass"
    status: ReleaseGateStatus = "pass" if passed else "blocked"
    return _gate(
        "architecture_engineering",
        "1.9.0 架构决策工程",
        status,
        100 if passed else 20,
        "measurable QAW, 3-option ADR, complete ATAM, 5 C4 views, 100% traceability, 0 orphans",
        (
            f"QAW {result.get('qaw_scenario_count', 0)} · ADR {result.get('adr_count', 0)} · "
            f"C4 {result.get('c4_view_count', 0)} · trace {result.get('traceability_coverage_percent', 0)}% · "
            f"orphans {result.get('orphan_component_count', 0)}"
        ),
        "QAW/ATAM/ADR/C4 与架构追溯契约回归通过。" if passed else "架构决策工程契约回归失败。",
        [_evidence("Architecture decision contract regression", status, "不调用模型或网络的确定性架构契约回归。", details=result)],
        [] if passed else [_action("high", "solution-architecture", "修复架构决策工程回归", "; ".join(result.get("blockers", [])[:3]))],  # type: ignore[index]
    )


def _build_executable_validation_gate(proof_path: Path) -> dict[str, Any]:
    payload, digest = load_reference_proof_artifact(proof_path)
    if payload is None:
        return _gate(
            "executable_validation",
            "1.9.1 可执行验证与验收证据",
            "blocked",
            0,
            "3 domain prototypes machine-pass plus real blind review and customer acceptance evidence",
            "proof artifact missing or invalid",
            "未找到有效的最小纵向样机 artifact。",
            [_evidence("Proof-of-architecture artifact", "blocked", "缺失或 digest 无效。", source=str(proof_path))],
            [_action("high", "solution-architecture", "运行最小纵向样机", "先生成医疗、金融、文旅三类机器执行证据。")],
        )
    machine_pass = (
        payload.get("machine_status") == "passed"
        and int(payload.get("scenario_count") or 0) == 3
        and int(payload.get("passed_scenario_count") or 0) == 3
        and all(len(row.get("checks") or []) >= 8 for row in payload.get("scenarios") or [] if isinstance(row, dict))
    )
    human_pass = (
        payload.get("blind_review_status") == "approved"
        and payload.get("customer_confirmation_status") == "approved"
        and len(payload.get("external_acceptance_artifacts") or []) >= 3
    )
    status: ReleaseGateStatus = "pass" if machine_pass and human_pass else "blocked"
    score = 100 if status == "pass" else 75 if machine_pass else 25
    failure_types = sorted(
        {
            str(check.get("category") or "unknown")
            for scenario in payload.get("scenarios") or []
            if isinstance(scenario, dict)
            for check in scenario.get("checks") or []
            if isinstance(check, dict) and check.get("status") != "passed"
        }
    )
    return _gate(
        "executable_validation",
        "1.9.1 可执行验证与验收证据",
        status,
        score,
        "3 domain prototypes machine-pass plus real blind review and customer acceptance evidence",
        (
            f"machine {payload.get('passed_scenario_count', 0)}/{payload.get('scenario_count', 0)} · "
            f"blind {payload.get('blind_review_status')} · customer {payload.get('customer_confirmation_status')}"
        ),
        (
            "样机、真实盲评和客户验收证据均完成。"
            if status == "pass"
            else "机器样机已通过，但真实三行业盲评和客户验收不能由模型或参考夹具替代。"
            if machine_pass
            else "最小纵向样机机器检查失败。"
        ),
        [
            _evidence(
                "Proof-of-architecture execution",
                "pass" if machine_pass else "blocked",
                "医疗、金融、文旅三类契约、数据流、成本、威胁、权限、恢复、观测和回滚检查。",
                source=str(proof_path),
                details={
                    "artifact_sha256": digest,
                    "machine_status": payload.get("machine_status"),
                    "quality_failure_types": failure_types,
                    "correction_rounds": payload.get("correction_rounds", 0),
                    "human_conclusion": payload.get("blind_review_status"),
                    "release_status": status,
                    "evidence_scope": payload.get("evidence_scope"),
                },
            )
        ],
        [] if status == "pass" else [
            _action(
                "high",
                "delivery-review",
                "补真实三行业盲评与客户验收 artifact" if machine_pass else "修复最小纵向样机失败",
                "机器参考回归不得替代真实数据、专家结论或客户确认。",
            )
        ],
    )


def _evaluate_screenshot_manifest(path: Path) -> dict[str, Any]:
    payload = _read_json(path)
    if not isinstance(payload, dict):
        return _evidence("Release screenshot manifest", "watch", "未找到截图 manifest。", source=str(path))
    gate = payload.get("quality_gate") if isinstance(payload.get("quality_gate"), dict) else {}
    expected = int(gate.get("expected_screenshot_count") or len(payload.get("screenshots") or []))
    accepted = int(gate.get("accepted_screenshot_count") or 0)
    version = str(payload.get("version") or "")
    counts_passed = expected > 0 and accepted >= expected
    version_passed = version == RELEASE_SEMVER
    status: ReleaseGateStatus = "pass" if counts_passed and version_passed else "blocked"
    release_tag = str(payload.get("release_tag") or f"v{version}")
    summary = f"截图门禁 accepted {accepted}/{expected}，version={version}，release_tag={release_tag}。"
    if counts_passed and not version_passed:
        summary = f"截图数量通过，但 manifest version={version or 'missing'}，当前版本要求 {RELEASE_SEMVER}。"
    return _evidence(
        "Release screenshot manifest",
        status,
        summary,
        source=str(path),
        details={
            "version": version,
            "release_tag": release_tag,
            "required_version": RELEASE_SEMVER,
            "expected_screenshot_count": expected,
            "accepted_screenshot_count": accepted,
        },
    )


def _evaluate_visual_manifests(paths: Iterable[Path]) -> tuple[ReleaseGateStatus, list[dict[str, Any]]]:
    evidence: list[dict[str, Any]] = []
    existing = [path for path in paths if path.exists()]
    if not existing:
        return (
            "watch",
            [
                _evidence(
                    "Office visual/roundtrip manifests",
                    "watch",
                    "未找到本轮 Office visual-baseline 或 roundtrip manifest，需重跑或人工确认。",
                    details={"searched_paths": [str(path) for path in paths]},
                )
            ],
        )
    aggregate_status: ReleaseGateStatus = "pass"
    for path in existing:
        payload = _read_json(path)
        manifest_evidence = _evaluate_visual_manifest_payload(path, payload)
        status = manifest_evidence["status"]
        if status == "blocked":
            aggregate_status = "blocked"
        elif status == "watch" and aggregate_status != "blocked":
            aggregate_status = "watch"
        evidence.append(manifest_evidence)
    return aggregate_status, evidence


def _build_visual_gate(
    screenshot_manifest_path: Path,
    visual_manifest_paths: Iterable[Path],
) -> dict[str, Any]:
    screenshot_evidence = _evaluate_screenshot_manifest(screenshot_manifest_path)
    visual_status, visual_evidence = _evaluate_visual_manifests(tuple(visual_manifest_paths))
    evidence = [screenshot_evidence, *visual_evidence]
    statuses = [item["status"] for item in evidence]
    if "blocked" in statuses:
        status: ReleaseGateStatus = "blocked"
        score = 45
        summary = "视觉/Office 自动门禁存在失败或缺关键截图。"
    elif visual_status == "watch" or "watch" in statuses:
        status = "watch"
        score = 70
        summary = "截图基线可用，但 Office roundtrip/人工视觉确认仍需收口。"
    else:
        status = "pass"
        score = 100
        summary = "截图、visual baseline 与 Office roundtrip 机器门禁均已记录通过。"
    actions: list[dict[str, str]] = []
    if status != "pass":
        actions.append(
            _action(
                "medium",
                "delivery-review",
                "补齐 Office/视觉确认 manifest",
                "运行 `npm run office:visual-baseline`、`npm run office:roundtrip`，或记录人工 Word/PPT/Preview 视觉确认。",
            )
        )
    return _gate(
        "visual_gate",
        "视觉与 Office 门禁",
        status,
        score,
        "screenshots accepted, visual baseline pass, Office roundtrip pass",
        summary,
        summary,
        evidence,
        actions,
    )


def _build_research_experience_gate(db: Session, now: datetime) -> dict[str, Any]:
    readiness = build_research_experience_readiness(now=now, db=db)
    metrics = readiness.metrics
    return _gate(
        "research_experience",
        "研报澄清与体验门禁",
        readiness.status,
        readiness.score,
        "3+ 行业 / 120 条真实任务 / 20 条澄清链路 / 30 条人工反馈",
        (
            f"{metrics.industry_bucket_count} 个行业 / {metrics.sample_size} 条任务 / "
            f"{metrics.clarification_started_count} 条澄清 / {metrics.feedback_count} 条反馈"
        ),
        "受限草稿、补充材料续跑和渐进披露必须经过真实体验样本验证。",
        [
            _evidence(
                "澄清体验指标",
                readiness.status,
                (
                    f"恢复转化率 {metrics.clarification_conversion_rate:.1f}%，"
                    f"平均反馈 {metrics.average_feedback_score:.2f}/5，"
                    f"门禁绕过 {metrics.formal_gate_bypass_count} 条。"
                ),
                source="/api/research/experience/readiness",
                details=metrics.model_dump(mode="json"),
            )
        ],
        [
            _action("high", "Research QA", action, reason)
            for action, reason in (
                (
                    "完成跨行业真实任务与澄清恢复样本",
                    readiness.blockers[0] if readiness.blockers else "体验门禁仍有观察项。",
                ),
                (
                    "复核体验反馈、来源血缘和正式门禁绕过",
                    "真实验收证据不能由模型自评替代。",
                ),
            )
        ]
        if readiness.status != "pass"
        else [],
    )


def _build_assurance_program_gate(
    db: Session,
    now: datetime | None,
    *,
    review_path: Path,
    calibration_path: Path,
    screenshot_manifest_path: Path,
) -> dict[str, Any]:
    """Expose the post-2.5.0 program as a release gate without rewriting evidence."""

    snapshot = build_research_assurance_snapshot(
        db,
        now=now,
        review_path=review_path,
        calibration_path=calibration_path,
        screenshot_manifest_path=screenshot_manifest_path,
    )
    status = str(snapshot["status"])
    if status not in {"pass", "watch", "blocked"}:
        status = "blocked"
    rounds = list(snapshot.get("rounds") or [])
    pass_count = sum(row.get("status") == "pass" for row in rounds if isinstance(row, dict))
    blocked_count = sum(row.get("status") == "blocked" for row in rounds if isinstance(row, dict))
    actions = list(snapshot.get("next_actions") or [])
    first_action = str(actions[0]) if actions else "补齐保障计划要求的真实证据。"
    priority: ReleaseActionPriority = "high" if status == "blocked" else "medium"
    return _gate(
        "assurance_program",
        "2.5.1-2.6.5 质量保障计划",
        status,  # type: ignore[arg-type]
        int(snapshot.get("score") or 0),
        "15 个质量保障轮次均具备当前、可追溯的工程与外部证据",
        f"{pass_count}/{len(rounds)} 通过 · {blocked_count} 阻断 · 评分 {snapshot.get('score', 0)}/100",
        "只读聚合真实研报、质量队列、模型账本、人工复核工件和发布工件；缺失人工证据保持阻断。",
        [
            _evidence(
                "质量保障快照",
                status,  # type: ignore[arg-type]
                f"{snapshot.get('program_version')}：{pass_count} 通过 / {blocked_count} 阻断。",
                source="/api/research/assurance/preview",
                details={
                    "program_version": snapshot.get("program_version"),
                    "report_sample_size": snapshot.get("report_sample_size"),
                    "valid_report_count": snapshot.get("valid_report_count"),
                    "invalid_report_count": snapshot.get("invalid_report_count"),
                },
            )
        ],
        []
        if status == "pass"
        else [
            _action(
                priority,
                "research-quality-owner",
                first_action,
                "质量保障控制台只读取真实状态，不能以本地实现替代外部复核、校准、验收或视觉证据。",
            )
        ],
    )


def _build_industry_retrieval_assurance_gate() -> dict[str, Any]:
    """Expose the local-knowledge retrieval program without allowing self-promotion."""

    snapshot = build_industry_knowledge_retrieval_assurance_snapshot()
    status = str(snapshot.get("status") or "blocked")
    if status not in {"pass", "watch", "blocked"}:
        status = "blocked"
    pass_count = int(snapshot.get("pass_count") or 0)
    watch_count = int(snapshot.get("watch_count") or 0)
    blocked_count = int(snapshot.get("blocked_count") or 0)
    candidate = str(snapshot.get("candidate_strategy") or "")
    default = str(snapshot.get("current_default_strategy") or "baseline_hybrid")
    actions = [
        _action(
            "high" if status == "blocked" else "medium",
            "retrieval-quality-owner",
            str(action),
            "候选策略必须经过固定题集、独立完整研报复核、审批、影子和漂移证据；缺一不可切换默认策略。",
        )
        for action in list(snapshot.get("next_actions") or [])[:3]
        if str(action).strip()
    ]
    return _gate(
        "industry_retrieval_assurance",
        "2.6.6-2.8.0 本地知识检索保证",
        status,  # type: ignore[arg-type]
        int(snapshot.get("score") or 0),
        "15 个检索保证轮次、人工复核、审批、影子与漂移证据完整；否则保持基线默认",
        (
            f"{pass_count}/15 通过 · {watch_count} 观察 · {blocked_count} 阻断 · "
            f"默认 {default}" + (f" · 候选 {candidate}" if candidate else "")
        ),
        "只读聚合行业知识库 A/B、完整研报人工复核和候选受控上线证据；不会自动改变生产默认策略。",
        [
            _evidence(
                "检索保证快照",
                status,  # type: ignore[arg-type]
                f"{snapshot.get('program_version')}：当前默认 {default}，候选 {candidate or '未满足上线条件'}。",
                source="/api/research/industry-skills/retrieval-ranking-assurance",
                details={
                    "benchmark_id": snapshot.get("benchmark_id"),
                    "case_count": snapshot.get("case_count"),
                    "dataset_sha256": snapshot.get("dataset_sha256"),
                    "knowledge_base_generation_id": snapshot.get("knowledge_base_generation_id"),
                    "promotion_decision": snapshot.get("promotion_decision"),
                },
            )
        ],
        actions,
    )


def _build_industry_retrieval_evidence_operations_gate() -> dict[str, Any]:
    """Expose the post-assurance operations chain without treating templates as proof."""

    snapshot = build_industry_knowledge_retrieval_evidence_operations_snapshot()
    status = str(snapshot.get("status") or "blocked")
    if status not in {"pass", "watch", "blocked"}:
        status = "blocked"
    pass_count = int(snapshot.get("pass_count") or 0)
    watch_count = int(snapshot.get("watch_count") or 0)
    blocked_count = int(snapshot.get("blocked_count") or 0)
    default = str(snapshot.get("current_default_strategy") or "baseline_hybrid")
    chain_digest = str(snapshot.get("evidence_chain_digest") or "")
    actions = [
        _action(
            "high" if status == "blocked" else "medium",
            "retrieval-quality-owner",
            str(action),
            "证据运营工件必须由真实责任人完成、保持时效并绑定同一证据链；模板和本地测试不能替代外部证据。",
        )
        for action in list(snapshot.get("next_actions") or [])[:3]
        if str(action).strip()
    ]
    return _gate(
        "industry_retrieval_evidence_operations",
        "2.8.1-2.9.5 检索证据运营",
        status,  # type: ignore[arg-type]
        int(snapshot.get("score") or 0),
        "15 个证据运营门、时效、事件/撤销记录和独立审计交接完整；否则保持基线默认",
        f"{pass_count}/15 通过 · {watch_count} 观察 · {blocked_count} 阻断 · 默认 {default}",
        "只读聚合检索证据链、时效和审计交接；不批准候选，也不会改变生产默认策略。",
        [
            _evidence(
                "检索证据运营快照",
                status,  # type: ignore[arg-type]
                f"{snapshot.get('program_version')}：当前默认 {default}，证据链 {chain_digest[:12] or '缺失'}。",
                source="/api/research/industry-skills/retrieval-evidence-operations",
                details={
                    "benchmark_digest": snapshot.get("benchmark_digest"),
                    "evidence_chain_digest": chain_digest,
                    "case_count": snapshot.get("case_count"),
                    "parent_program_version": snapshot.get("parent_program_version"),
                    "parent_status": snapshot.get("parent_status"),
                },
            )
        ],
        actions,
    )


def _build_operator_commands(
    gates: list[dict[str, Any]],
    review_path: Path,
    calibration_path: Path,
    proof_path: Path,
) -> list[dict[str, str]]:
    gate_by_key = {str(gate["key"]): gate for gate in gates}
    commands: list[dict[str, str]] = []
    if gate_by_key.get("health", {}).get("status") != "pass":
        commands.append(
            _command(
                "health",
                "系统健康与稳定性",
                "刷新 stability smoke",
                "npm run stability:smoke",
                "生成最新 `.tmp/stability_smoke_report.json`，用于 health gate。",
            )
        )
    if gate_by_key.get("research_diagnostics", {}).get("status") != "pass":
        commands.append(
            _command(
                "research_diagnostics",
                "Research Upgrade Diagnostics",
                "检查研究升级诊断 API",
                "curl -fsS http://127.0.0.1:8000/api/research/upgrade-diagnostics/preview",
                "确认 15 轮 diagnostics payload 和 fallback_actions 是否仍为 watch。",
            )
        )
    if gate_by_key.get("industry_retrieval_assurance", {}).get("status") != "pass":
        commands.extend(
            [
                _command(
                    "industry_retrieval_assurance",
                    "2.6.6-2.8.0 本地知识检索保证",
                    "读取检索保证快照",
                    "curl -fsS http://127.0.0.1:8000/api/research/industry-skills/retrieval-ranking-assurance",
                    "检查固定题集、人工复核、真实 Cross Encoder、审批、影子与漂移门禁。",
                ),
                _command(
                    "industry_retrieval_assurance",
                    "2.6.6-2.8.0 本地知识检索保证",
                    "导出候选审批模板",
                    "curl -fsS -X POST http://127.0.0.1:8000/api/research/industry-skills/retrieval-ranking-assurance/approval-template",
                    "仅导出 pending 人工审批模板，不能自动批准或更改生产默认策略。",
                ),
            ]
        )
    if gate_by_key.get("industry_retrieval_evidence_operations", {}).get("status") != "pass":
        commands.extend(
            [
                _command(
                    "industry_retrieval_evidence_operations",
                    "2.8.1-2.9.5 检索证据运营",
                    "读取证据运营快照",
                    "curl -fsS http://127.0.0.1:8000/api/research/industry-skills/retrieval-evidence-operations",
                    "检查工件清单、摘要绑定、时效、事件/撤销登记和审计交接状态。",
                ),
                _command(
                    "industry_retrieval_evidence_operations",
                    "2.8.1-2.9.5 检索证据运营",
                    "导出运营模板",
                    "npm run knowledge:industry-skills:retrieval-ranking:operations:templates",
                    "仅导出 pending 的事件、撤销和审计交接模板，不会创建外部完成证据。",
                ),
            ]
        )
    if gate_by_key.get("evidence_governance", {}).get("status") != "pass":
        commands.append(
            _command(
                "evidence_governance",
                "1.8.2/1.8.3 Evidence Governance",
                "运行证据治理回归",
                "backend/.venv311/bin/pytest -q backend/tests/test_research_evidence_governance.py",
                "验证主题硬负例、正向证据包、问题树和主张引用门。",
            )
        )
    if gate_by_key.get("low_quality_audit", {}).get("status") != "pass":
        commands.append(
            _command(
                "low_quality_audit",
                "低质量审计",
                "修复低质量审计队列",
                "backend/.venv311/bin/python scripts/release_hardening_low_quality_repair.py --target-rate 0.1 --accept-zero-risk",
                "先备份 SQLite，再只接受 rewrite 后 risk_score=0 的条目。",
            )
        )
    if gate_by_key.get("independent_review", {}).get("status") != "pass":
        commands.extend(
            [
                _command(
                    "independent_review",
                    "独立复核",
                    "导出独立复核模板",
                    f"npm run research:evaluate:review:export -- --output {review_path}",
                    "生成包含 100 条 locked case 上下文的待复核 artifact。",
                ),
                _command(
                    "independent_review",
                    "独立复核",
                    "人工复核后 finalize",
                    f"npm run research:evaluate:review:finalize -- --review {review_path} --reviewer-name \"<independent reviewer>\" --reviewer-role \"<role>\" --attestation \"<attestation>\"",
                    "只在真实独立复核完成后写入 reviewer metadata、attestation 和 digest。",
                ),
                _command(
                    "independent_review",
                    "独立复核",
                    "校验独立复核 artifact",
                    f"npm run research:evaluate:review:validate -- --review {review_path}",
                    "验证 100/100 case approved、digest、reviewer metadata 和 attestation。",
                ),
            ]
        )
    if gate_by_key.get("expert_calibration", {}).get("status") != "pass":
        commands.extend(
            [
                _command(
                    "expert_calibration",
                    "1.8.4 专家盲评与校准",
                    "导出 100+30 专家校准工件",
                    f"npm run research:evaluate:calibration:export -- --output {calibration_path}",
                    "生成 100 条主评、30 条分层双盲复评、仲裁和自动裁判对照槽位。",
                ),
                _command(
                    "expert_calibration",
                    "1.8.4 专家盲评与校准",
                    "真实评审完成后 finalize",
                    f"npm run research:evaluate:calibration:finalize -- --artifact {calibration_path}",
                    "只根据已填写的真实专家结论计算 digest、召回、一致性和偏差。",
                ),
                _command(
                    "expert_calibration",
                    "1.8.4 专家盲评与校准",
                    "校验专家校准工件",
                    f"npm run research:evaluate:calibration:validate -- --artifact {calibration_path}",
                    "验证 100+30、盲评隔离、仲裁、五维分数、95% 召回和硬上限。",
                ),
            ]
        )
    if gate_by_key.get("architecture_engineering", {}).get("status") != "pass":
        commands.append(
            _command(
                "architecture_engineering",
                "1.9.0 架构决策工程",
                "运行架构决策契约回归",
                "backend/.venv311/bin/pytest -q backend/tests/test_solution_executable_validation.py",
                "验证 QAW、ATAM、三方案 ADR、五层 C4、100% 追溯和零孤立组件。",
            )
        )
    if gate_by_key.get("executable_validation", {}).get("status") != "pass":
        commands.append(
            _command(
                "executable_validation",
                "1.9.1 可执行验证与验收证据",
                "运行最小纵向样机",
                f"npm run research:architecture:validate -- --output {proof_path}",
                "生成医疗、金融、文旅参考工程回归；真实盲评和客户验收仍需外部 artifact。",
            )
        )
    if gate_by_key.get("visual_gate", {}).get("status") != "pass":
        commands.extend(
            [
                _command(
                    "visual_gate",
                    "视觉与 Office 门禁",
                    "生成 Office 视觉基线",
                    "npm run office:visual-baseline",
                    "生成 DOCX/PPTX/PDF artifact、结构校验和 visual fingerprint manifest。",
                ),
                _command(
                    "visual_gate",
                    "视觉与 Office 门禁",
                    "刷新发布截图",
                    "npm run repo:screenshots",
                    "刷新 release screenshot manifest，避免截图基线与当前版本漂移。",
                ),
                _command(
                    "visual_gate",
                    "视觉与 Office 门禁",
                    "校验 Office roundtrip",
                    "npm run office:roundtrip -- .tmp/formal-artifact-visual-baseline/artifacts/*.docx .tmp/formal-artifact-visual-baseline/artifacts/*.pptx .tmp/formal-artifact-visual-baseline/artifacts/*.pdf --quicklook --quicklook-scope pdf --libreoffice-convert --manifest-out .tmp/formal-artifact-visual-baseline/roundtrip-manifest.json",
                    "记录结构校验、PDF QuickLook 缩略图和可用时的 LibreOffice 转换结果。",
                ),
            ]
        )
    return commands


def _build_release_artifacts(
    gates: list[dict[str, Any]],
    *,
    review_path: Path,
    calibration_path: Path,
    proof_path: Path,
    stability_report_path: Path,
    screenshot_manifest_path: Path,
    visual_manifest_paths: Iterable[Path],
) -> list[dict[str, Any]]:
    gate_by_key = {str(gate["key"]): gate for gate in gates}
    required_visual_paths = {
        PROJECT_ROOT / ".tmp" / "formal-artifact-visual-baseline" / "visual-baseline-manifest.json",
        PROJECT_ROOT / ".tmp" / "formal-artifact-visual-baseline" / "roundtrip-manifest.json",
    }
    artifacts = [
        _artifact(
            "health",
            "系统健康与稳定性",
            "Stability smoke report",
            stability_report_path,
            str(gate_by_key.get("health", {}).get("status") or "watch"),  # type: ignore[arg-type]
            "最近一次 stability smoke 的机器可读结果。",
        ),
        _artifact(
            "independent_review",
            "独立复核",
            "Independent review artifact",
            review_path,
            str(gate_by_key.get("independent_review", {}).get("status") or "blocked"),  # type: ignore[arg-type]
            "独立复核模板或最终批准 artifact；存在不代表已通过。",
        ),
        _artifact(
            "expert_calibration",
            "1.8.4 专家盲评与校准",
            "Expert calibration artifact",
            calibration_path,
            str(gate_by_key.get("expert_calibration", {}).get("status") or "blocked"),  # type: ignore[arg-type]
            "100 条主评、30 条双盲复评、仲裁和自动裁判校准工件；存在不代表已通过。",
        ),
        _artifact(
            "executable_validation",
            "1.9.1 可执行验证与验收证据",
            "Proof-of-architecture artifact",
            proof_path,
            str(gate_by_key.get("executable_validation", {}).get("status") or "blocked"),  # type: ignore[arg-type]
            "医疗、金融、文旅最小纵向样机机器证据及人工验收状态。",
        ),
        _artifact(
            "visual_gate",
            "视觉与 Office 门禁",
            "Release screenshot manifest",
            screenshot_manifest_path,
            str(gate_by_key.get("visual_gate", {}).get("status") or "watch"),  # type: ignore[arg-type]
            "发布截图质量门禁 manifest。",
        ),
        _artifact(
            "industry_retrieval_evidence_operations",
            "2.8.1-2.9.5 检索证据运营",
            "Retrieval incident register",
            DEFAULT_INCIDENT_PATH,
            str(gate_by_key.get("industry_retrieval_evidence_operations", {}).get("status") or "blocked"),  # type: ignore[arg-type]
            "真实 fallback、回退和人工豁免的事件登记；存在不代表已关闭。",
        ),
        _artifact(
            "industry_retrieval_evidence_operations",
            "2.8.1-2.9.5 检索证据运营",
            "Retrieval revocation record",
            DEFAULT_REVOCATION_PATH,
            str(gate_by_key.get("industry_retrieval_evidence_operations", {}).get("status") or "blocked"),  # type: ignore[arg-type]
            "候选撤销和回退 baseline_hybrid 的具名确认；存在不代表已验证。",
        ),
        _artifact(
            "industry_retrieval_evidence_operations",
            "2.8.1-2.9.5 检索证据运营",
            "Retrieval independent audit handoff",
            DEFAULT_HANDOFF_PATH,
            str(gate_by_key.get("industry_retrieval_evidence_operations", {}).get("status") or "blocked"),  # type: ignore[arg-type]
            "绑定当前证据链摘要的独立审计交接；存在不代表已批准。",
        ),
    ]
    for path in visual_manifest_paths:
        if not path.exists() and path not in required_visual_paths:
            continue
        artifacts.append(
            _artifact(
                "visual_gate",
                "视觉与 Office 门禁",
                path.name,
                path,
                "watch" if not path.exists() else str(gate_by_key.get("visual_gate", {}).get("status") or "watch"),  # type: ignore[arg-type]
                "Office visual-baseline 或 roundtrip manifest 搜索路径。",
            )
        )
    for path in sorted((PROJECT_ROOT / ".tmp").glob("release_hardening_low_quality_repair*.json"))[-3:]:
        artifacts.append(
            _artifact(
                "low_quality_audit",
                "低质量审计",
                path.name,
                path,
                str(gate_by_key.get("low_quality_audit", {}).get("status") or "watch"),  # type: ignore[arg-type]
                "低质量审计修复脚本输出报告。",
            )
        )
    return artifacts


def build_release_readiness_snapshot(
    db: Session,
    *,
    now: datetime | None = None,
    review_path: Path = DEFAULT_REVIEW_PATH,
    calibration_path: Path = DEFAULT_CALIBRATION_PATH,
    proof_path: Path = DEFAULT_PROOF_ARTIFACT_PATH,
    stability_report_path: Path = DEFAULT_STABILITY_REPORT_PATH,
    screenshot_manifest_path: Path = DEFAULT_SCREENSHOT_MANIFEST_PATH,
    visual_manifest_paths: Iterable[Path] = DEFAULT_VISUAL_MANIFEST_PATHS,
) -> dict[str, Any]:
    provided_now = now
    generated_at = now or datetime.now(UTC)
    visual_paths = tuple(visual_manifest_paths)
    gates = [
        _build_health_gate(db, generated_at, stability_report_path),
        _build_diagnostics_gate(),
        _build_evidence_governance_gate(),
        _build_hard_failure_policy_gate(),
        _build_low_quality_gate(db),
        _build_independent_review_gate(review_path),
        _build_expert_calibration_gate(calibration_path),
        _build_architecture_engineering_gate(),
        _build_executable_validation_gate(proof_path),
        _build_visual_gate(screenshot_manifest_path, visual_paths),
        _build_research_experience_gate(db, generated_at),
        _build_assurance_program_gate(
            db,
            provided_now,
            review_path=review_path,
            calibration_path=calibration_path,
            screenshot_manifest_path=screenshot_manifest_path,
        ),
        _build_industry_retrieval_assurance_gate(),
        _build_industry_retrieval_evidence_operations_gate(),
    ]
    pass_count = sum(1 for gate in gates if gate["status"] == "pass")
    watch_count = sum(1 for gate in gates if gate["status"] == "watch")
    blocked_count = sum(1 for gate in gates if gate["status"] == "blocked")
    if blocked_count:
        overall_status: ReleaseGateStatus = "blocked"
    elif watch_count:
        overall_status = "watch"
    else:
        overall_status = "pass"
    readiness_score = round(sum(int(gate["score"]) for gate in gates) / max(1, len(gates)))
    next_actions = [
        {**action, "gate_key": gate["key"], "gate_label": gate["label"]}
        for gate in gates
        if gate["status"] != "pass"
        for action in gate["actions"]
    ]
    status_label = {"pass": "通过", "watch": "关注", "blocked": "阻断"}[overall_status]
    summary_lines = [
        f"2.9.5 检索保证、证据运营与质量控制台：{pass_count} 通过 / {watch_count} 关注 / {blocked_count} 阻断。",
        f"总体就绪度评分 {readiness_score}/100；总体状态：{status_label}。",
        "人工复核、候选审批、影子/漂移证据、专家盲评、客户验收和视觉门禁保持真实状态，不用模型自评自动折算为通过。",
    ]
    return {
        "generated_at": generated_at,
        "release_version": RELEASE_VERSION,
        "overall_status": overall_status,
        "readiness_score": readiness_score,
        "summary_lines": summary_lines,
        "gates": gates,
        "next_actions": next_actions,
        "operator_commands": _build_operator_commands(gates, review_path, calibration_path, proof_path),
        "artifacts": _build_release_artifacts(
            gates,
            review_path=review_path,
            calibration_path=calibration_path,
            proof_path=proof_path,
            stability_report_path=stability_report_path,
            screenshot_manifest_path=screenshot_manifest_path,
            visual_manifest_paths=visual_paths,
        ),
    }
