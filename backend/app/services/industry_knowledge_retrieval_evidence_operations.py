from __future__ import annotations

import hashlib
import json
import math
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

from app.services.content_extractor import normalize_text
from app.services.industry_knowledge_retrieval_assurance import (
    DEFAULT_APPROVAL_PATH,
    DEFAULT_DRIFT_PATH,
    DEFAULT_SHADOW_PATH,
    build_industry_knowledge_retrieval_assurance_snapshot,
)
from app.services.industry_knowledge_retrieval_benchmark import (
    DEFAULT_ARTIFACT_PATH,
    DEFAULT_REVIEW_PATH,
    STRATEGY_KEYS,
    industry_knowledge_benchmark_artifact_reference,
    industry_knowledge_retrieval_benchmark_digest,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
PROGRAM_VERSION = "2.9.5-retrieval-evidence-operations"
INCIDENT_SCHEMA_VERSION = "industry-knowledge-retrieval-incident-register-v1"
REVOCATION_SCHEMA_VERSION = "industry-knowledge-retrieval-revocation-v1"
HANDOFF_SCHEMA_VERSION = "industry-knowledge-retrieval-audit-handoff-v1"
DEFAULT_INCIDENT_PATH = PROJECT_ROOT / ".tmp" / "industry-knowledge-retrieval-ranking-incidents.json"
DEFAULT_REVOCATION_PATH = PROJECT_ROOT / ".tmp" / "industry-knowledge-retrieval-ranking-revocation.json"
DEFAULT_HANDOFF_PATH = PROJECT_ROOT / ".tmp" / "industry-knowledge-retrieval-ranking-audit-handoff.json"

_REVIEW_MAX_AGE_DAYS = 30
_APPROVAL_MAX_AGE_DAYS = 14
_SHADOW_MAX_AGE_DAYS = 7
_DRIFT_MAX_AGE_DAYS = 7


def _utc_now() -> str:
    return datetime.now(UTC).isoformat()


def _normalized(value: object) -> str:
    return normalize_text(str(value or ""))


def _safe_count(value: object) -> int:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    if not math.isfinite(number) or number < 0 or not number.is_integer():
        return 0
    return int(number)


def _safe_sequence(value: object) -> Sequence[Any]:
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        return value
    return ()


def _read_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.is_file():
        return None, "未发现"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None, "不可读取"
    if not isinstance(payload, dict):
        return None, "根节点不是对象"
    return payload, "可读取"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(f"{path.suffix}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def _canonical_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _artifact_reference(path: Path) -> str:
    return industry_knowledge_benchmark_artifact_reference(path)


def _status_rank(status: str) -> int:
    return {"pass": 100, "watch": 60, "blocked": 0}.get(status, 0)


def _status_from_artifact(payload: Mapping[str, Any] | None, expected_schema: str) -> tuple[str, str]:
    if payload is None:
        return "blocked", "缺少或无法读取工件。"
    if _normalized(payload.get("schema_version")) != expected_schema:
        return "blocked", "schema_version 不匹配。"
    return "pass", "结构可读取。"


def _parse_datetime(value: object) -> datetime | None:
    raw = _normalized(value)
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _freshness(
    payload: Mapping[str, Any] | None,
    *,
    field: str,
    max_age_days: int,
    now: datetime,
) -> tuple[str, str, datetime | None]:
    timestamp = _parse_datetime(payload.get(field) if payload else None)
    if timestamp is None:
        return "blocked", f"缺少有效 {field}。", None
    if timestamp > now + timedelta(minutes=5):
        return "blocked", f"{field} 不能晚于当前时间。", timestamp
    age = now - timestamp
    if age > timedelta(days=max_age_days):
        return "blocked", f"已过期 {round(age.total_seconds() / 86400, 1)} 天，最长允许 {max_age_days} 天。", timestamp
    return "pass", f"距今 {round(age.total_seconds() / 86400, 1)} 天。", timestamp


def _metric(key: str, label: str, observed: str, target: str, status: str, note: str = "") -> dict[str, str]:
    return {
        "key": key,
        "label": label,
        "observed": observed,
        "target": target,
        "status": status,
        "note": note,
    }


def _evidence(label: str, path: Path, status: str, summary: str) -> dict[str, Any]:
    return {
        "label": label,
        "path": _artifact_reference(path),
        "exists": path.is_file(),
        "status": status,
        "summary": summary,
    }


def _round(
    index: int,
    version: str,
    key: str,
    title: str,
    status: str,
    summary: str,
    metrics: Sequence[dict[str, str]],
    next_actions: Sequence[str] = (),
    evidence: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    return {
        "index": index,
        "version": version,
        "key": key,
        "title": title,
        "status": status,
        "summary": summary,
        "metrics": list(metrics),
        "next_actions": [action for action in next_actions if action],
        "evidence": list(evidence),
    }


def _artifact_payloads(
    *,
    benchmark_path: Path,
    review_path: Path,
    approval_path: Path,
    shadow_path: Path,
    drift_path: Path,
    incident_path: Path,
    revocation_path: Path,
    handoff_path: Path,
) -> dict[str, tuple[Path, dict[str, Any] | None, str]]:
    paths = {
        "benchmark": benchmark_path,
        "review": review_path,
        "approval": approval_path,
        "shadow": shadow_path,
        "drift": drift_path,
        "incidents": incident_path,
        "revocation": revocation_path,
        "handoff": handoff_path,
    }
    return {key: (path, *_read_json(path)) for key, path in paths.items()}


def _artifact_chain_digest(
    benchmark_digest: str,
    payloads: Mapping[str, tuple[Path, dict[str, Any] | None, str]],
) -> str:
    chain = {
        "benchmark_digest": benchmark_digest,
        "artifact_digests": {
            key: _canonical_digest(payload) if payload is not None else ""
            for key, (_path, payload, _read_state) in sorted(payloads.items())
            if key != "handoff"
        },
    }
    return _canonical_digest(chain)


def _round_status(snapshot: Mapping[str, Any], key: str) -> str:
    for item in _safe_sequence(snapshot.get("rounds")):
        if isinstance(item, Mapping) and _normalized(item.get("key")) == key:
            value = _normalized(item.get("status")).lower()
            return value if value in {"pass", "watch", "blocked"} else "blocked"
    return "blocked"


def _bound_to_benchmark(payload: Mapping[str, Any] | None, benchmark_digest: str) -> bool:
    return bool(payload and benchmark_digest and _normalized(payload.get("benchmark_digest")) == benchmark_digest)


def _review_coverage(
    benchmark: Mapping[str, Any] | None,
    review: Mapping[str, Any] | None,
) -> tuple[int, int, str]:
    case_count = _safe_count(benchmark.get("case_count") if benchmark else 0)
    expected = case_count * len(STRATEGY_KEYS)
    found: set[tuple[str, str]] = set()
    for entry in _safe_sequence(review.get("entries") if review else ()):
        if not isinstance(entry, Mapping):
            continue
        case_id = _normalized(entry.get("case_id"))
        strategy = _normalized(entry.get("strategy"))
        report_path = _normalized(entry.get("report_artifact_path"))
        score = entry.get("human_review_score")
        if case_id and strategy in STRATEGY_KEYS and report_path and isinstance(score, (int, float)):
            found.add((case_id, strategy))
    status = "pass" if expected and len(found) == expected else "blocked"
    return expected, len(found), status


def _role_separation(
    review: Mapping[str, Any] | None,
    approval: Mapping[str, Any] | None,
    shadow: Mapping[str, Any] | None,
    drift: Mapping[str, Any] | None,
) -> tuple[str, str]:
    roles = {
        "复核人": _normalized(review.get("reviewer_name") if review else None),
        "审批人": _normalized(approval.get("approved_by") if approval else None),
        "影子执行人": _normalized(shadow.get("executed_by") if shadow else None),
        "漂移执行人": _normalized(drift.get("executed_by") if drift else None),
    }
    values = [value.casefold() for value in roles.values() if value]
    if len(values) != len(roles):
        return "blocked", "缺少具名复核、审批或运行责任人。"
    if len(set(values)) != len(values):
        return "blocked", "复核、审批、影子和漂移职责不能由同一人兼任。"
    return "pass", "四类职责均具名且相互分离；仍需由组织侧核验身份。"


def _chronology_status(
    review_at: datetime | None,
    approval_at: datetime | None,
    shadow_at: datetime | None,
    drift_at: datetime | None,
) -> tuple[str, str]:
    values = (review_at, approval_at, shadow_at, drift_at)
    if any(value is None for value in values):
        return "blocked", "缺少复核、审批、影子或漂移时间，无法验证时序。"
    assert review_at is not None and approval_at is not None and shadow_at is not None and drift_at is not None
    if not review_at <= approval_at <= shadow_at <= drift_at:
        return "blocked", "工件时间必须遵循复核 -> 审批 -> 影子 -> 漂移的顺序。"
    return "pass", "复核、审批、影子和漂移的时间顺序一致。"


def _incident_status(payload: Mapping[str, Any] | None, benchmark_digest: str, now: datetime) -> tuple[str, str]:
    structure_status, message = _status_from_artifact(payload, INCIDENT_SCHEMA_VERSION)
    if structure_status != "pass" or payload is None:
        return structure_status, message
    if not _bound_to_benchmark(payload, benchmark_digest):
        return "blocked", "事件登记未绑定当前固定评测摘要。"
    freshness, freshness_message, _ = _freshness(payload, field="updated_at", max_age_days=7, now=now)
    incidents = [item for item in _safe_sequence(payload.get("incidents")) if isinstance(item, Mapping)]
    if _normalized(payload.get("status")).lower() != "complete":
        return "blocked", "事件登记尚未由负责人完成。"
    if not all(_normalized(payload.get(key)) for key in ("updated_by", "attestation")):
        return "blocked", "事件登记缺少负责人或声明。"
    if incidents:
        return "blocked", f"仍有 {len(incidents)} 条未清零事件记录。"
    return freshness, freshness_message if freshness == "pass" else f"事件登记 {freshness_message}"


def _revocation_status(payload: Mapping[str, Any] | None, benchmark_digest: str, now: datetime) -> tuple[str, str]:
    structure_status, message = _status_from_artifact(payload, REVOCATION_SCHEMA_VERSION)
    if structure_status != "pass" or payload is None:
        return structure_status, message
    if not _bound_to_benchmark(payload, benchmark_digest):
        return "blocked", "撤销确认未绑定当前固定评测摘要。"
    if _normalized(payload.get("rollback_target")) != "baseline_hybrid":
        return "blocked", "撤销目标必须是 baseline_hybrid。"
    if _normalized(payload.get("status")).lower() != "acknowledged":
        return "blocked", "撤销/回退方案尚未由负责人确认。"
    if not all(_normalized(payload.get(key)) for key in ("confirmed_by", "attestation")):
        return "blocked", "撤销确认缺少负责人或声明。"
    freshness, freshness_message, _ = _freshness(payload, field="confirmed_at", max_age_days=30, now=now)
    return freshness, freshness_message if freshness == "pass" else f"撤销确认 {freshness_message}"


def _handoff_status(payload: Mapping[str, Any] | None, chain_digest: str, now: datetime) -> tuple[str, str]:
    structure_status, message = _status_from_artifact(payload, HANDOFF_SCHEMA_VERSION)
    if structure_status != "pass" or payload is None:
        return structure_status, message
    if _normalized(payload.get("evidence_chain_digest")) != chain_digest:
        return "blocked", "审计交接未绑定当前证据链摘要。"
    if _normalized(payload.get("status")).lower() != "complete":
        return "blocked", "审计交接尚未完成。"
    if not all(_normalized(payload.get(key)) for key in ("handed_off_by", "attestation")):
        return "blocked", "审计交接缺少负责人或声明。"
    freshness, freshness_message, _ = _freshness(payload, field="handed_off_at", max_age_days=7, now=now)
    return freshness, freshness_message if freshness == "pass" else f"审计交接 {freshness_message}"


def build_industry_knowledge_retrieval_evidence_operations_snapshot(
    *,
    benchmark_payload: Mapping[str, Any] | None = None,
    benchmark_artifact_path: str | Path = DEFAULT_ARTIFACT_PATH,
    review_path: str | Path = DEFAULT_REVIEW_PATH,
    approval_path: str | Path = DEFAULT_APPROVAL_PATH,
    shadow_path: str | Path = DEFAULT_SHADOW_PATH,
    drift_path: str | Path = DEFAULT_DRIFT_PATH,
    incident_path: str | Path = DEFAULT_INCIDENT_PATH,
    revocation_path: str | Path = DEFAULT_REVOCATION_PATH,
    handoff_path: str | Path = DEFAULT_HANDOFF_PATH,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Aggregate the next 15 retrieval-evidence operations without self-promotion.

    This control plane is deliberately read-only.  It derives its status from
    persisted benchmark and human/runtime artifacts, and only reports a pass
    when all bindings, freshness, handoff, and existing assurance gates are
    independently complete.  It never changes the production retrieval default.
    """

    generated_at = (now or datetime.now(UTC)).astimezone(UTC)
    benchmark_file = Path(benchmark_artifact_path)
    review_file = Path(review_path)
    approval_file = Path(approval_path)
    shadow_file = Path(shadow_path)
    drift_file = Path(drift_path)
    incident_file = Path(incident_path)
    revocation_file = Path(revocation_path)
    handoff_file = Path(handoff_path)
    payloads = _artifact_payloads(
        benchmark_path=benchmark_file,
        review_path=review_file,
        approval_path=approval_file,
        shadow_path=shadow_file,
        drift_path=drift_file,
        incident_path=incident_file,
        revocation_path=revocation_file,
        handoff_path=handoff_file,
    )
    benchmark = dict(benchmark_payload) if benchmark_payload is not None else payloads["benchmark"][1]
    review = payloads["review"][1]
    approval = payloads["approval"][1]
    shadow = payloads["shadow"][1]
    drift = payloads["drift"][1]
    incidents = payloads["incidents"][1]
    revocation = payloads["revocation"][1]
    handoff = payloads["handoff"][1]
    parent = build_industry_knowledge_retrieval_assurance_snapshot(
        benchmark_payload=benchmark,
        benchmark_artifact_path=benchmark_file,
        review_path=review_file,
        approval_path=approval_file,
        shadow_path=shadow_file,
        drift_path=drift_file,
    )
    benchmark_digest = _normalized(parent.get("benchmark_digest"))
    if benchmark:
        benchmark_digest = industry_knowledge_retrieval_benchmark_digest(benchmark)
    stored_digest = _normalized(benchmark.get("benchmark_digest") if benchmark else None)
    benchmark_envelope_status = "pass" if benchmark and stored_digest == benchmark_digest else "blocked"
    case_count = _safe_count(benchmark.get("case_count") if benchmark else parent.get("case_count"))
    candidate = _normalized(parent.get("candidate_strategy"))
    default_strategy = _normalized(parent.get("current_default_strategy")) or "baseline_hybrid"
    chain_digest = _artifact_chain_digest(benchmark_digest, payloads)

    artifact_labels = {
        "benchmark": "固定评测快照",
        "review": "完整研报独立复核",
        "approval": "候选策略审批",
        "shadow": "受控影子运行",
        "drift": "固定题集漂移检查",
        "incidents": "事件登记册",
        "revocation": "撤销与回退确认",
        "handoff": "审计交接记录",
    }
    artifact_evidence: list[dict[str, Any]] = []
    readable_count = 0
    for key, label in artifact_labels.items():
        path, payload, read_state = payloads[key]
        status = "pass" if payload is not None else "blocked"
        readable_count += int(payload is not None)
        artifact_evidence.append(_evidence(label, path, status, read_state))

    required_bindings = {
        "完整研报复核": _bound_to_benchmark(review, benchmark_digest),
        "候选审批": _bound_to_benchmark(approval, benchmark_digest),
        "影子运行": _bound_to_benchmark(shadow, benchmark_digest),
        "漂移检查": _bound_to_benchmark(drift, benchmark_digest),
    }
    lineage_status = "pass" if all(required_bindings.values()) else "blocked"
    review_freshness, review_freshness_message, review_at = _freshness(
        review,
        field="reviewed_at",
        max_age_days=_REVIEW_MAX_AGE_DAYS,
        now=generated_at,
    )
    approval_freshness, approval_freshness_message, approval_at = _freshness(
        approval,
        field="approved_at",
        max_age_days=_APPROVAL_MAX_AGE_DAYS,
        now=generated_at,
    )
    shadow_freshness, shadow_freshness_message, shadow_at = _freshness(
        shadow,
        field="executed_at",
        max_age_days=_SHADOW_MAX_AGE_DAYS,
        now=generated_at,
    )
    drift_freshness, drift_freshness_message, drift_at = _freshness(
        drift,
        field="executed_at",
        max_age_days=_DRIFT_MAX_AGE_DAYS,
        now=generated_at,
    )
    freshness_status = "pass" if all(
        status == "pass" for status in (review_freshness, approval_freshness, shadow_freshness, drift_freshness)
    ) else "blocked"
    role_status, role_summary = _role_separation(review, approval, shadow, drift)
    review_expected, review_found, coverage_status = _review_coverage(benchmark, review)
    chronology_status, chronology_summary = _chronology_status(review_at, approval_at, shadow_at, drift_at)
    incident_status, incident_summary = _incident_status(incidents, benchmark_digest, generated_at)
    revocation_status, revocation_summary = _revocation_status(revocation, benchmark_digest, generated_at)
    handoff_status, handoff_summary = _handoff_status(handoff, chain_digest, generated_at)
    reranker_status = _round_status(parent, "cross_encoder_provenance")
    shadow_status = _round_status(parent, "shadow_run")
    drift_status = _round_status(parent, "drift_monitoring")

    rounds = [
        _round(
            1,
            "2.8.1",
            "evidence_envelope",
            "证据封套与摘要完整性",
            benchmark_envelope_status,
            "固定评测工件必须包含可重算且与内容一致的摘要，作为后续所有人工和运行证据的唯一锚点。",
            [
                _metric("benchmark_digest", "评测摘要", benchmark_digest[:12] or "缺失", "已持久化且可重算", benchmark_envelope_status),
                _metric("stored_digest", "工件内摘要", stored_digest[:12] or "缺失", benchmark_digest[:12] or "有效摘要", benchmark_envelope_status),
            ],
            [] if benchmark_envelope_status == "pass" else ["运行并持久化当前固定题集，保留与内容一致的 benchmark_digest。"],
            [artifact_evidence[0]],
        ),
        _round(
            2,
            "2.8.2",
            "artifact_inventory",
            "证据工件清单",
            "pass" if readable_count == len(artifact_labels) else "watch" if readable_count else "blocked",
            "发布判断需要固定评测、人工复核、审批、影子、漂移、事件、撤销和审计交接八类工件，缺失必须可见。",
            [
                _metric("readable_artifacts", "可读取工件", f"{readable_count}/{len(artifact_labels)}", f"{len(artifact_labels)}/{len(artifact_labels)}", "pass" if readable_count == len(artifact_labels) else "blocked"),
                _metric("case_count", "固定题目", str(case_count), ">=12", "pass" if case_count >= 12 else "blocked"),
            ],
            [] if readable_count == len(artifact_labels) else ["补齐缺失的人工或运行工件；模板不能替代完成记录。"],
            artifact_evidence,
        ),
        _round(
            3,
            "2.8.3",
            "artifact_lineage",
            "工件血缘绑定",
            lineage_status,
            "复核、审批、影子和漂移必须全部引用当前 benchmark_digest，旧题集或旧知识库 generation 的记录不可复用。",
            [
                _metric("review_binding", "复核绑定", "已绑定" if required_bindings["完整研报复核"] else "缺失", "当前评测摘要", "pass" if required_bindings["完整研报复核"] else "blocked"),
                _metric("runtime_binding", "运行绑定", "已绑定" if required_bindings["影子运行"] and required_bindings["漂移检查"] else "缺失", "当前评测摘要", "pass" if required_bindings["影子运行"] and required_bindings["漂移检查"] else "blocked"),
            ],
            [] if lineage_status == "pass" else ["重新执行或重新签署与当前 benchmark_digest 精确绑定的证据。"],
            artifact_evidence[1:5],
        ),
        _round(
            4,
            "2.8.4",
            "evidence_freshness",
            "证据时效门",
            freshness_status,
            "复核、审批、影子和漂移不是永久凭证；到期后需要在同一固定题集上续签或重新运行。",
            [
                _metric("review_freshness", "复核时效", review_freshness_message, f"<={_REVIEW_MAX_AGE_DAYS} 天", review_freshness),
                _metric("approval_freshness", "审批时效", approval_freshness_message, f"<={_APPROVAL_MAX_AGE_DAYS} 天", approval_freshness),
                _metric("shadow_freshness", "影子时效", shadow_freshness_message, f"<={_SHADOW_MAX_AGE_DAYS} 天", shadow_freshness),
                _metric("drift_freshness", "漂移时效", drift_freshness_message, f"<={_DRIFT_MAX_AGE_DAYS} 天", drift_freshness),
            ],
            [] if freshness_status == "pass" else ["更新过期或缺失的复核、审批、影子和漂移证据。"],
            artifact_evidence[1:5],
        ),
        _round(
            5,
            "2.8.5",
            "role_separation",
            "复核、审批与运行职责分离",
            role_status,
            "系统仅做字段级职责分离校验；组织身份与独立性仍须由外部负责人核验并留存在工件中。",
            [
                _metric("role_separation", "四类责任人", role_summary, "具名且互不相同", role_status),
                _metric("identity_boundary", "身份核验边界", "字段级", "组织侧独立核验", "watch"),
            ],
            [] if role_status == "pass" else ["由不同的具名复核人、审批人、影子执行人和漂移执行人完成证据。"],
            artifact_evidence[1:5],
        ),
        _round(
            6,
            "2.8.6",
            "review_coverage_matrix",
            "完整研报复核覆盖矩阵",
            coverage_status,
            "每个固定题目和每个策略臂都需要对应完整报告路径与人工评分，缺一项即不可比较。",
            [
                _metric("review_entries", "复核条目", f"{review_found}/{review_expected}", f"{review_expected}/{review_expected}", coverage_status),
                _metric("parent_review_gate", "原始复核门", _round_status(parent, "full_report_review_integrity"), "pass", _round_status(parent, "full_report_review_integrity")),
            ],
            [] if coverage_status == "pass" else ["补齐每题、每策略的完整研报路径和独立人工评分。"],
            [artifact_evidence[1]],
        ),
        _round(
            7,
            "2.8.7",
            "reranker_runtime_preflight",
            "真实复排运行前检",
            reranker_status,
            "候选 B 只有在每个固定题上真实调用本地 Cross Encoder 时才可计为复排；配置或启发式降级不计入。",
            [
                _metric("actual_rerank", "真实复排证据", reranker_status, "pass", reranker_status),
                _metric("default_protection", "生产默认", default_strategy, "baseline_hybrid 直至证据齐全", "pass" if default_strategy == "baseline_hybrid" else "blocked"),
            ],
            [] if reranker_status == "pass" else ["挂载并校验本地 Cross Encoder 缓存后，重新运行固定题集。"],
            [artifact_evidence[0]],
        ),
        _round(
            8,
            "2.8.8",
            "shadow_operations_ledger",
            "影子运行运营账本",
            shadow_status,
            "影子记录必须引用已批准的候选、真实样本量、fallback 和质量回退计数；空模板不构成影子运行。",
            [
                _metric("shadow_gate", "影子运行门", shadow_status, "pass", shadow_status),
                _metric("candidate", "候选策略", candidate or "未形成候选", "已批准候选", "pass" if candidate else "blocked"),
            ],
            [] if shadow_status == "pass" else ["在具名负责人监督下完成至少 30 个真实样本的受控影子运行。"],
            [artifact_evidence[3]],
        ),
        _round(
            9,
            "2.8.9",
            "drift_operations_ledger",
            "漂移检查运营账本",
            drift_status,
            "漂移检查必须在影子运行之后，绑定同一审批摘要，并保留固定题集的回归计数。",
            [
                _metric("drift_gate", "漂移检查门", drift_status, "pass", drift_status),
                _metric("chronology", "运行时序", chronology_summary, "复核 -> 审批 -> 影子 -> 漂移", chronology_status),
            ],
            [] if drift_status == "pass" and chronology_status == "pass" else ["在影子运行后执行固定题集漂移检查并记录零回归结果。"],
            [artifact_evidence[4]],
        ),
        _round(
            10,
            "2.9.0",
            "incident_register",
            "异常与豁免登记",
            incident_status,
            "任何来源降级、fallback、质量回退或人工豁免都必须被登记、关闭或阻断，不能只存在于日志。",
            [
                _metric("incident_register", "事件登记", incident_summary, "具名、绑定、零未关闭事件", incident_status),
                _metric("incident_schema", "登记协议", _normalized(incidents.get("schema_version") if incidents else None) or "缺失", INCIDENT_SCHEMA_VERSION, "pass" if incidents and _normalized(incidents.get("schema_version")) == INCIDENT_SCHEMA_VERSION else "blocked"),
            ],
            [] if incident_status == "pass" else ["导出事件登记模板，由运行负责人记录并关闭所有异常或豁免。"],
            [artifact_evidence[5]],
        ),
        _round(
            11,
            "2.9.1",
            "revocation_acknowledgement",
            "撤销与回退确认",
            revocation_status,
            "任何候选证据失效时都必须可回退到 baseline_hybrid，且该路径需由生产负责人明确确认。",
            [
                _metric("revocation_record", "回退确认", revocation_summary, "baseline_hybrid 已确认", revocation_status),
                _metric("baseline_target", "回退目标", _normalized(revocation.get("rollback_target") if revocation else None) or "缺失", "baseline_hybrid", "pass" if revocation and _normalized(revocation.get("rollback_target")) == "baseline_hybrid" else "blocked"),
            ],
            [] if revocation_status == "pass" else ["由生产负责人确认候选撤销时回退到 baseline_hybrid 的操作路径。"],
            [artifact_evidence[6]],
        ),
        _round(
            12,
            "2.9.2",
            "renewal_chronology",
            "证据续签时序",
            chronology_status,
            "续签后的工件必须保持复核、审批、影子、漂移的单向时间顺序，避免用旧运行结果支撑新审批。",
            [
                _metric("chronology", "证据时序", chronology_summary, "单向递增", chronology_status),
                _metric("freshness", "时效总门", freshness_status, "pass", freshness_status),
            ],
            [] if chronology_status == "pass" else ["按复核、审批、影子、漂移顺序重新完成当前证据链。"],
            artifact_evidence[1:5],
        ),
        _round(
            13,
            "2.9.3",
            "evidence_package_manifest",
            "可复算证据包",
            "pass" if lineage_status == "pass" and readable_count >= 5 else "blocked",
            "证据包用固定评测摘要和各工件内容摘要计算链摘要，便于独立审计时确认未被替换。",
            [
                _metric("evidence_chain_digest", "证据链摘要", chain_digest[:12], "可复算且可交接", "pass" if benchmark_digest else "blocked"),
                _metric("core_artifacts", "核心工件", f"{sum(int(payloads[key][1] is not None) for key in ('benchmark', 'review', 'approval', 'shadow', 'drift'))}/5", "5/5", "pass" if readable_count >= 5 else "blocked"),
            ],
            [] if lineage_status == "pass" and readable_count >= 5 else ["先补齐并绑定核心证据工件，再对外提交证据包。"],
            artifact_evidence[:5],
        ),
        _round(
            14,
            "2.9.4",
            "independent_audit_handoff",
            "独立审计交接",
            handoff_status,
            "审计交接必须明确引用当前证据链摘要并由独立责任人签署；本地模板或代码不能替代该签署。",
            [
                _metric("handoff", "审计交接", handoff_summary, "已完成且绑定当前链摘要", handoff_status),
                _metric("chain_digest", "交接摘要", _normalized(handoff.get("evidence_chain_digest") if handoff else None)[:12] or "缺失", chain_digest[:12], "pass" if handoff and _normalized(handoff.get("evidence_chain_digest")) == chain_digest else "blocked"),
            ],
            [] if handoff_status == "pass" else ["导出审计交接模板，由独立审计责任人完成当前证据包的交接。"],
            [artifact_evidence[7]],
        ),
        _round(
            15,
            "2.9.5",
            "release_readiness_bridge",
            "发布就绪度证据运营桥",
            "blocked",
            "该桥只把 15 个运营门汇总至 release-readiness；它不升级候选策略，也不把本地测试转换成外部批准。",
            [],
        ),
    ]
    # The final release bridge depends on the preceding fourteen rounds.  It is
    # built after their statuses are known to keep the dependency explicit.
    prior_rounds = rounds[:-1]
    bridge_status = "pass" if prior_rounds and all(item["status"] == "pass" for item in prior_rounds) else "blocked"
    rounds[-1] = _round(
        15,
        "2.9.5",
        "release_readiness_bridge",
        "发布就绪度证据运营桥",
        bridge_status,
        "该桥只把 15 个运营门汇总至 release-readiness；它不升级候选策略，也不把本地测试转换成外部批准。",
        [
            _metric("operations_rounds", "运营门通过数", f"{sum(item['status'] == 'pass' for item in prior_rounds)}/14", "14/14", bridge_status),
            _metric("default_protected", "生产默认保护", default_strategy, "baseline_hybrid 直至外部证据完备", "pass" if default_strategy == "baseline_hybrid" else "blocked"),
        ],
        [] if bridge_status == "pass" else ["完成前 14 个证据运营门后，release-readiness 才可将该桥标记为通过。"],
        artifact_evidence,
    )
    pass_count = sum(item["status"] == "pass" for item in rounds)
    watch_count = sum(item["status"] == "watch" for item in rounds)
    blocked_count = sum(item["status"] == "blocked" for item in rounds)
    status = "blocked" if blocked_count else "watch" if watch_count else "pass"
    next_actions: list[str] = []
    for item in rounds:
        for action in item["next_actions"]:
            if action not in next_actions:
                next_actions.append(action)
    warnings = [
        "证据运营快照只读取持久化工件；pending 模板、配置或本地测试不会被计为外部证据。",
        "baseline_hybrid 继续是唯一生产默认策略，直至所有检索保证与运营证据均被独立完成。",
    ]
    if not benchmark_digest:
        warnings.append("当前没有可绑定的固定评测摘要，所有下游人工和运行工件均应视为不可用。")
    return {
        "program_version": PROGRAM_VERSION,
        "generated_at": generated_at,
        "status": status,
        "score": round(sum(_status_rank(item["status"]) for item in rounds) / len(rounds)),
        "parent_program_version": _normalized(parent.get("program_version")),
        "parent_status": _normalized(parent.get("status")) or "blocked",
        "current_default_strategy": default_strategy,
        "candidate_strategy": candidate,
        "benchmark_digest": benchmark_digest,
        "evidence_chain_digest": chain_digest,
        "case_count": case_count,
        "pass_count": pass_count,
        "watch_count": watch_count,
        "blocked_count": blocked_count,
        "rounds": rounds,
        "artifacts": artifact_evidence,
        "next_actions": next_actions[:14],
        "warnings": warnings,
    }


def _pending_template(path: Path, payload: Mapping[str, Any]) -> tuple[dict[str, Any], bool]:
    """Create only missing templates and never overwrite human-authored artifacts."""

    existing, state = _read_json(path)
    if path.exists():
        if existing is None:
            raise ValueError(f"已有证据运营工件{state}；为避免覆盖人工记录，未生成新模板。")
        return existing, False
    _write_json(path, payload)
    return dict(payload), True


def export_industry_knowledge_retrieval_evidence_operations_templates(
    *,
    incident_path: str | Path = DEFAULT_INCIDENT_PATH,
    revocation_path: str | Path = DEFAULT_REVOCATION_PATH,
    handoff_path: str | Path = DEFAULT_HANDOFF_PATH,
    benchmark_payload: Mapping[str, Any] | None = None,
    benchmark_artifact_path: str | Path = DEFAULT_ARTIFACT_PATH,
) -> dict[str, Any]:
    """Export pending operations templates without approving or promoting anything."""

    benchmark_file = Path(benchmark_artifact_path)
    benchmark, _ = _read_json(benchmark_file)
    if benchmark_payload is not None:
        benchmark = dict(benchmark_payload)
    benchmark_digest = industry_knowledge_retrieval_benchmark_digest(benchmark) if benchmark else ""
    if not benchmark_digest:
        raise ValueError("未找到可绑定的固定检索评测结果；为避免生成无摘要模板，未导出运营工件。")
    base = {
        "benchmark_digest": benchmark_digest,
        "production_default": "baseline_hybrid",
    }
    incident_file = Path(incident_path)
    revocation_file = Path(revocation_path)
    handoff_file = Path(handoff_path)
    incident, incident_created = _pending_template(
        incident_file,
        {
            "schema_version": INCIDENT_SCHEMA_VERSION,
            **base,
            "status": "pending",
            "updated_by": "",
            "updated_at": "",
            "attestation": "",
            "incidents": [],
            "instructions": [
                "记录所有 fallback、质量回退、来源降级和人工豁免；没有异常时也须由负责人完成零事件声明。",
                "模板本身不表示事件已关闭，status 仅能由真实负责人改为 complete。",
            ],
        },
    )
    revocation, revocation_created = _pending_template(
        revocation_file,
        {
            "schema_version": REVOCATION_SCHEMA_VERSION,
            **base,
            "status": "pending",
            "rollback_target": "baseline_hybrid",
            "confirmed_by": "",
            "confirmed_at": "",
            "attestation": "",
            "instructions": [
                "确认任何候选证据失效或运行异常时，生产默认都回退到 baseline_hybrid。",
                "模板不改变默认策略，也不构成候选批准。",
            ],
        },
    )
    handoff, handoff_created = _pending_template(
        handoff_file,
        {
            "schema_version": HANDOFF_SCHEMA_VERSION,
            "evidence_chain_digest": "",
            "status": "pending",
            "handed_off_by": "",
            "handed_off_at": "",
            "attestation": "",
            "instructions": [
                "由独立审计责任人将当前 evidence_chain_digest 填入并完成交接。",
                "本模板不会替代独立审计或 release approval。",
            ],
        },
    )
    return {
        "program_version": PROGRAM_VERSION,
        "benchmark_digest": benchmark_digest,
        "incident_register_path": _artifact_reference(incident_file),
        "revocation_record_path": _artifact_reference(revocation_file),
        "audit_handoff_path": _artifact_reference(handoff_file),
        "created_paths": [
            _artifact_reference(path)
            for path, created in (
                (incident_file, incident_created),
                (revocation_file, revocation_created),
                (handoff_file, handoff_created),
            )
            if created
        ],
        "warnings": [
            "模板均为 pending，不能作为人工签署、影子运行、漂移检查、事件关闭或审计交接证据。",
            "生产默认保持 baseline_hybrid。",
        ],
        "template_summaries": {
            "incident": _normalized(incident.get("status")),
            "revocation": _normalized(revocation.get("status")),
            "handoff": _normalized(handoff.get("status")),
        },
    }
