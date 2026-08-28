from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
import json
from pathlib import Path
from threading import Lock
from time import monotonic
from typing import Any, Iterable, Literal

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.research_entities import ResearchJob
from app.schemas.research import (
    ResearchAssuranceMetricOut,
    ResearchAssuranceRoundOut,
    ResearchAssuranceSnapshotOut,
    ResearchReportResponse,
)
from app.services.model_control_plane_service import build_model_control_plane_snapshot
from app.services.research.evaluation_dataset import DATASET_PATH, load_research_evaluation_dataset
from app.services.research.evaluation_review import (
    ResearchEvaluationReviewArtifact,
    validate_research_evaluation_review,
)
from app.services.research.expert_calibration import (
    ExpertCalibrationArtifact,
    validate_expert_calibration,
)
from app.services.research_review_service import list_low_quality_research_review_queue
from app.services.research_experience_service import build_research_experience_readiness


AssuranceStatus = Literal["pass", "watch", "blocked"]

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ASSURANCE_PROGRAM_VERSION = "2.6.5"
DEFAULT_REVIEW_PATH = PROJECT_ROOT / ".tmp" / "research-evaluation-independent-review.json"
DEFAULT_CALIBRATION_PATH = PROJECT_ROOT / ".tmp" / "research-evaluation-expert-calibration.json"
DEFAULT_SCREENSHOT_MANIFEST_PATH = PROJECT_ROOT / "docs" / "assets" / "screenshots" / "screenshot-manifest.json"
DEFAULT_PACKAGE_PATH = PROJECT_ROOT / "package.json"
SNAPSHOT_CACHE_TTL_SECONDS = 5.0

_snapshot_cache_lock = Lock()
_snapshot_cache_created_at = 0.0
_snapshot_cache: dict[str, Any] | None = None


@dataclass(frozen=True, slots=True)
class _ReportRecord:
    job: ResearchJob
    report: ResearchReportResponse
    metrics: dict[str, Any]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _metric(
    key: str,
    label: str,
    observed: str,
    target: str,
    status: AssuranceStatus,
    summary: str,
) -> ResearchAssuranceMetricOut:
    return ResearchAssuranceMetricOut(
        key=key,
        label=label,
        observed=observed,
        target=target,
        status=status,
        summary=summary,
    )


def _round(
    index: int,
    version: str,
    key: str,
    label: str,
    status: AssuranceStatus,
    summary: str,
    metrics: Iterable[ResearchAssuranceMetricOut],
    next_actions: Iterable[str],
) -> ResearchAssuranceRoundOut:
    score = {"pass": 100, "watch": 65, "blocked": 25}[status]
    return ResearchAssuranceRoundOut(
        index=index,
        version=version,
        key=key,
        label=label,
        status=status,
        score=score,
        summary=summary,
        metrics=list(metrics),
        next_actions=_dedupe(next_actions, limit=4),
    )


def _dedupe(values: Iterable[str], *, limit: int) -> list[str]:
    result: list[str] = []
    for value in values:
        normalized = " ".join(str(value or "").split())
        if normalized and normalized not in result:
            result.append(normalized)
        if len(result) >= limit:
            break
    return result


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return None
    return value if isinstance(value, dict) else None


def _load_reports(
    db: Session,
    *,
    limit: int,
) -> tuple[list[ResearchJob], list[_ReportRecord], list[ResearchJob]]:
    settings = get_settings()
    jobs = list(
        db.scalars(
            select(ResearchJob)
            .where(ResearchJob.user_id == settings.single_user_id)
            .order_by(desc(ResearchJob.created_at))
            .limit(max(1, int(limit)))
        ).all()
    )
    records: list[_ReportRecord] = []
    invalid: list[ResearchJob] = []
    for job in jobs:
        payload = job.report_payload
        expects_report = job.status in {"succeeded", "needs_evidence"}
        if not isinstance(payload, dict):
            if expects_report:
                invalid.append(job)
            continue
        try:
            report = ResearchReportResponse.model_validate(payload)
        except Exception:
            invalid.append(job)
            continue
        records.append(
            _ReportRecord(
                job=job,
                report=report,
                metrics=job.metrics_payload if isinstance(job.metrics_payload, dict) else {},
            )
        )
    return jobs, records, invalid


def _resolved_delivery_truth(report: ResearchReportResponse) -> bool:
    truth = report.delivery_truth
    return bool(
        truth.status != "awaiting_user"
        or truth.next_action
        or truth.decisive_reasons
        or truth.blocking_gate_keys
    )


def _is_formal(report: ResearchReportResponse) -> bool:
    return report.delivery_truth.status == "formal"


def _artifact_review_round(path: Path) -> tuple[AssuranceStatus, int, int, list[str]]:
    if not path.exists():
        return "blocked", 0, 100, ["尚未导出并完成 100 条独立复核工件。"]
    try:
        manifest, cases = load_research_evaluation_dataset(DATASET_PATH)
        artifact = ResearchEvaluationReviewArtifact.model_validate_json(path.read_text(encoding="utf-8"))
        validation = validate_research_evaluation_review(manifest, cases, artifact)
    except Exception as exc:
        return "blocked", 0, 100, [f"独立复核工件校验失败：{exc}"]
    status: AssuranceStatus = "pass" if validation.independent_review_complete else "blocked"
    return status, validation.approved_case_count, validation.case_count, validation.blockers


def _artifact_calibration_round(path: Path) -> tuple[AssuranceStatus, int, int, int, list[str]]:
    if not path.exists():
        return "blocked", 0, 100, 0, ["尚未导出并完成专家校准与客户验收工件。"]
    try:
        manifest, cases = load_research_evaluation_dataset(DATASET_PATH)
        artifact = ExpertCalibrationArtifact.model_validate_json(path.read_text(encoding="utf-8"))
        validation = validate_expert_calibration(manifest, cases, artifact)
    except Exception as exc:
        return "blocked", 0, 100, 0, [f"专家校准工件校验失败：{exc}"]
    status: AssuranceStatus = "pass" if validation.calibration_complete else "blocked"
    return (
        status,
        validation.quality_audit_completed,
        validation.case_count,
        validation.customer_acceptance_completed,
        validation.blockers,
    )


def _screenshot_version_state(
    screenshot_manifest_path: Path,
    package_path: Path,
) -> tuple[AssuranceStatus, str, str, list[str]]:
    package = _read_json(package_path) or {}
    expected_version = str(package.get("version") or ASSURANCE_PROGRAM_VERSION)
    manifest = _read_json(screenshot_manifest_path)
    if not manifest:
        return "blocked", "缺失", expected_version, ["未找到当前版本的发布截图清单。"]
    version = str(manifest.get("version") or "")
    quality_gate = manifest.get("quality_gate") if isinstance(manifest.get("quality_gate"), dict) else {}
    expected_count = int(quality_gate.get("expected_screenshot_count") or len(manifest.get("screenshots") or []))
    accepted_count = int(quality_gate.get("accepted_screenshot_count") or 0)
    if version == expected_version and expected_count > 0 and accepted_count >= expected_count:
        return "pass", f"{accepted_count}/{expected_count}", expected_version, []
    return (
        "blocked",
        f"{accepted_count}/{expected_count}，版本={version or '缺失'}",
        expected_version,
        ["重新生成发布截图，并确保截图清单版本与当前应用版本一致。"],
    )


def _build_research_assurance_snapshot(
    db: Session,
    *,
    now: datetime | None = None,
    report_limit: int = 500,
    review_path: Path = DEFAULT_REVIEW_PATH,
    calibration_path: Path = DEFAULT_CALIBRATION_PATH,
    screenshot_manifest_path: Path = DEFAULT_SCREENSHOT_MANIFEST_PATH,
    package_path: Path = DEFAULT_PACKAGE_PATH,
) -> dict[str, Any]:
    """Aggregate the post-2.5.0 quality program without manufacturing human evidence."""

    generated_at = now or _utc_now()
    jobs, records, invalid_jobs = _load_reports(db, limit=report_limit)
    reports = [record.report for record in records]
    report_count = len(reports)
    sample_size = report_count + len(invalid_jobs)
    quality_queue = list_low_quality_research_review_queue(db, top=40, include_resolved=True)
    experience = build_research_experience_readiness(now=generated_at, db=db)

    rounds: list[ResearchAssuranceRoundOut] = []

    payload_status: AssuranceStatus
    if invalid_jobs:
        payload_status = "blocked"
    elif sample_size:
        payload_status = "pass"
    else:
        payload_status = "watch"
    rounds.append(
        _round(
            1,
            "2.5.1",
            "payload_compatibility",
            "历史报告数据兼容性",
            payload_status,
            "所有进入质量运营面的已完成研报都必须能被当前数据结构读取。",
            [
                _metric(
                    "report_schema",
                    "可解析研报",
                    f"{report_count}/{sample_size}",
                    "无效报告数据 = 0",
                    payload_status,
                    "成功任务缺失或无法读取的研报数据会直接阻断后续质量判断。",
                )
            ],
            ["先迁移或隔离无法通过当前数据结构读取的历史研报。"] if invalid_jobs else [],
        )
    )

    topology_instrumented = sum(
        bool(report.research_source_admissions or report.source_diagnostics.source_topology_counts)
        for report in reports
    )
    snapshot_reused = sum(report.source_diagnostics.snapshot_recovery_used for report in reports)
    topology_violations = sum(
        _is_formal(report)
        and (
            (report.delivery_truth.delivery_mode == "account_pursuit" and report.research_evidence_gate.local_target_proof_count < 1)
            or report.source_diagnostics.snapshot_recovery_used
        )
        for report in reports
    )
    topology_status: AssuranceStatus = (
        "blocked"
        if topology_violations
        else "pass"
        if report_count and topology_instrumented == report_count and not snapshot_reused
        else "watch"
    )
    rounds.append(
        _round(
            2,
            "2.5.2",
            "source_topology_freshness",
            "来源拓扑与新鲜度",
            topology_status,
            "本地甲方证据、外部标杆与历史上下文必须分道，快照不能满足新鲜证据门。",
            [
                _metric(
                    "topology_coverage",
                    "拓扑已标注",
                    f"{topology_instrumented}/{report_count}",
                    "全部当前报告",
                    "pass" if report_count and topology_instrumented == report_count else "watch",
                    "来源准入与来源分层记录用于复核来源用途。",
                ),
                _metric(
                    "formal_topology_violation",
                    "正式交付拓扑违规",
                    str(topology_violations),
                    "0",
                    "blocked" if topology_violations else "pass",
                    "账户推进不能由外部标杆、快照或历史来源替代本地当前证明。",
                ),
                _metric(
                    "snapshot_reuse",
                    "快照复用报告",
                    str(snapshot_reused),
                    "明确标注且不作为新鲜证据",
                    "watch" if snapshot_reused else "pass",
                    "快照复用不是失败，但必须显式降级为非新鲜证据。",
                ),
            ],
            ["为缺少来源分层标注的历史报告补跑来源准入审计。"] if topology_status == "watch" else [],
        )
    )

    entity_enforced = sum(report.research_entity_authenticity_gate.enforced for report in reports)
    entity_failures = sum(
        report.research_entity_authenticity_gate.enforced
        and not report.research_entity_authenticity_gate.passed
        for report in reports
    )
    formal_entity_bypasses = sum(
        _is_formal(report)
        and (
            not report.research_entity_authenticity_gate.enforced
            or not report.research_entity_authenticity_gate.passed
        )
        for report in reports
    )
    entity_status: AssuranceStatus = (
        "blocked"
        if formal_entity_bypasses
        else "pass"
        if report_count and entity_enforced == report_count and not entity_failures
        else "watch"
    )
    rounds.append(
        _round(
            3,
            "2.5.3",
            "entity_role_truth",
            "实体角色真值",
            entity_status,
            "排名、标题和导出中的机构必须有真实身份和角色证据。",
            [
                _metric(
                    "entity_gate_coverage",
                    "实体门已执行",
                    f"{entity_enforced}/{report_count}",
                    "全部当前报告",
                    "pass" if report_count and entity_enforced == report_count else "watch",
                    "实体门缺失的历史研报只能作为待审计样本。",
                ),
                _metric(
                    "formal_entity_bypass",
                    "正式交付实体绕过",
                    str(formal_entity_bypasses),
                    "0",
                    "blocked" if formal_entity_bypasses else "pass",
                    "正式报告不能包含未经实体真值门验证的账户、竞品或伙伴。",
                ),
            ],
            ["将实体门失败项保留在候选池，不进入正式账户排序。"] if entity_failures else [],
        )
    )

    formal_reports = [report for report in reports if _is_formal(report)]
    formal_claim_violations = sum(
        report.research_claim_evidence_ledger.high_confidence_coverage_percent < 100
        or report.research_claim_evidence_ledger.conflicted_claim_count > 0
        or report.research_claim_evidence_ledger.status != "pass"
        for report in formal_reports
    )
    total_claims = sum(report.research_claim_evidence_ledger.claim_count for report in reports)
    claim_status: AssuranceStatus = (
        "blocked"
        if formal_claim_violations
        else "pass"
        if formal_reports and not formal_claim_violations
        else "watch"
    )
    rounds.append(
        _round(
            4,
            "2.5.4",
            "claim_coverage_conflict",
            "主张覆盖与冲突",
            claim_status,
            "高置信度主张必须有证据关系，冲突主张不得进入正式交付。",
            [
                _metric(
                    "formal_claim_violations",
                    "正式报告主张违规",
                    str(formal_claim_violations),
                    "0",
                    "blocked" if formal_claim_violations else "pass",
                    "检查高置信度主张覆盖、冲突和主张台账状态。",
                ),
                _metric(
                    "claim_inventory",
                    "已登记主张",
                    str(total_claims),
                    "每份正式报告均有记录",
                    "pass" if formal_reports and total_claims else "watch",
                    "没有主张台账不能被解释为正式交付通过。",
                ),
            ],
            ["补齐关键主张来源，或将其改为假设/待核验项。"] if claim_status != "pass" else [],
        )
    )

    delivery_unresolved = sum(not _resolved_delivery_truth(report) for report in reports)
    delivery_contradictions = sum(
        _is_formal(report)
        and (
            not report.delivery_truth.formal_delivery_allowed
            or not report.research_evidence_gate.formal_report_allowed
            or not report.research_citation_gate.passed
        )
        for report in reports
    )
    delivery_status: AssuranceStatus = (
        "blocked"
        if delivery_contradictions
        else "pass"
        if report_count and not delivery_unresolved
        else "watch"
    )
    rounds.append(
        _round(
            5,
            "2.5.5",
            "delivery_truth_convergence",
            "交付真值一致性",
            delivery_status,
            "正式、受限草稿、等待补充和系统降级必须由同一交付真值控制。",
            [
                _metric(
                    "resolved_delivery_truth",
                    "已决交付真值",
                    f"{report_count - delivery_unresolved}/{report_count}",
                    "全部当前报告",
                    "pass" if report_count and not delivery_unresolved else "watch",
                    "早期数据的默认值会被识别为未决，不会被误当作用户阻断。",
                ),
                _metric(
                    "formal_delivery_contradictions",
                    "正式交付矛盾",
                    str(delivery_contradictions),
                    "0",
                    "blocked" if delivery_contradictions else "pass",
                    "引用或证据未通过时不得同时显示为正式交付。",
                ),
            ],
            ["为历史输出回填交付真值，或在导出前重新评估。"] if delivery_unresolved else [],
        )
    )

    low_quality_total = int(quality_queue.get("total_reports") or 0)
    low_quality_flagged = int(quality_queue.get("flagged_reports") or 0)
    low_quality_invalid = int(quality_queue.get("invalid_payloads") or 0)
    low_quality_rate = low_quality_flagged / max(1, low_quality_total)
    low_quality_status: AssuranceStatus = (
        "blocked"
        if low_quality_invalid
        else "pass"
        if low_quality_total and low_quality_rate <= 0.10
        else "watch"
    )
    rounds.append(
        _round(
            6,
            "2.5.6",
            "low_quality_remediation",
            "低质量修复闭环",
            low_quality_status,
            "低质量队列只自动呈现可审计的重写差异，接受/回退仍需人工确认。",
            [
                _metric(
                    "flagged_rate",
                    "低质量率",
                    f"{low_quality_flagged}/{low_quality_total} ({low_quality_rate * 100:.1f}%)",
                    "<= 10%",
                    low_quality_status,
                    "风险队列来源于已保存研报，而不是模型自评。",
                ),
                _metric(
                    "invalid_payloads",
                    "无效报告数据",
                    str(low_quality_invalid),
                    "0",
                    "blocked" if low_quality_invalid else "pass",
                    "无法读取的历史研报必须先修复，不能通过重写掩盖。",
                ),
            ],
            list(quality_queue.get("recommendations") or [])[:2],
        )
    )

    clarification_status: AssuranceStatus = experience.status
    rounds.append(
        _round(
            7,
            "2.5.7",
            "clarification_recovery_cohorts",
            "澄清恢复队列",
            clarification_status,
            "以真实任务衡量证据缺口到可用结果的恢复，而不把空白输出当作成功。",
            [
                _metric(
                    "experience_sample",
                    "真实体验样本",
                    str(experience.metrics.sample_size),
                    str(experience.sample_target),
                    "pass" if experience.metrics.sample_size >= experience.sample_target else "blocked",
                    "样本、行业覆盖、澄清恢复和反馈共同决定体验门禁。",
                ),
                _metric(
                    "clarification_conversion",
                    "澄清恢复转化",
                    f"{experience.metrics.clarification_conversion_rate:.1f}%",
                    "样本达到门槛后 >= 65%",
                    "pass" if experience.metrics.clarification_conversion_rate >= 65 else "watch",
                    "低样本率只作为观察值，不能被解释为已验证的用户体验。",
                ),
            ],
            experience.next_actions[:2],
        )
    )

    model_snapshot = build_model_control_plane_snapshot(get_settings())
    routes = list(model_snapshot.get("routes") or [])
    report_fallbacks = sum(report.source_diagnostics.generation_fallback_used for report in reports)
    configured_generation_routes = sum(
        str(route.get("key")) in {"generation", "strategy"}
        and str(route.get("status")) in {"configured", "local", "external"}
        for route in routes
    )
    model_status: AssuranceStatus = (
        "blocked"
        if report_fallbacks
        else "pass"
        if report_count and configured_generation_routes >= 2
        else "watch"
    )
    rounds.append(
        _round(
            8,
            "2.5.8",
            "model_fallback_truth",
            "模型降级真值",
            model_status,
            "正式研报降级必须可见且不可伪装为正式成品，模型路由由控制面统一展示。",
            [
                _metric(
                    "generation_fallbacks",
                    "正式生成降级",
                    str(report_fallbacks),
                    "0",
                    "blocked" if report_fallbacks else "pass",
                    "确定性模拟结果只能作为降级草稿，不能替代正式研报。",
                ),
                _metric(
                    "configured_routes",
                    "可用生成/策略路由",
                    f"{configured_generation_routes}/2",
                    "2",
                    "pass" if configured_generation_routes >= 2 else "watch",
                    "控制面只公开模型名称和策略，不暴露凭据。",
                ),
            ],
            ["处理正式生成降级后，使用全新证据重新生成。"] if report_fallbacks else [],
        )
    )

    cost_ledgers = [
        record.metrics.get("cost_ledger")
        for record in records
        if isinstance(record.metrics.get("cost_ledger"), dict)
    ]
    model_call_count = sum(int(ledger.get("model_call_count") or 0) for ledger in cost_ledgers)
    priced_entry_count = sum(int(ledger.get("priced_entry_count") or 0) for ledger in cost_ledgers)
    unpriced_entry_count = sum(int(ledger.get("unpriced_entry_count") or 0) for ledger in cost_ledgers)
    total_cost = sum(float(ledger.get("estimated_cost_usd") or 0.0) for ledger in cost_ledgers)
    cost_status: AssuranceStatus = (
        "blocked"
        if model_call_count and priced_entry_count < model_call_count
        else "pass"
        if model_call_count and priced_entry_count >= model_call_count
        else "watch"
    )
    rounds.append(
        _round(
            9,
            "2.5.9",
            "cost_ledger_coverage",
            "成本账本覆盖",
            cost_status,
            "模型调用、token、定价和单篇成本必须形成可审计账本。",
            [
                _metric(
                    "priced_model_calls",
                    "已定价模型调用",
                    f"{priced_entry_count}/{model_call_count}",
                    "所有模型调用均已定价",
                    cost_status,
                    "未配置价格时，真实调用成本不可被估算为零。",
                ),
                _metric(
                    "observed_cost",
                    "观测成本",
                    f"${total_cost:.6f}",
                    "每份报告均可核算",
                    "pass" if model_call_count and priced_entry_count >= model_call_count else "watch",
                    f"未定价账本条目 {unpriced_entry_count} 条。",
                ),
            ],
            ["为当前模型填写输入、缓存输入和输出价格，再重跑真实样本。"] if cost_status != "pass" else [],
        )
    )

    reranker_expected = sum(report.source_diagnostics.runtime_source_reranker_enabled for report in reports)
    reranker_used = sum(
        report.source_diagnostics.runtime_source_reranker_enabled and report.source_diagnostics.reranker_used
        for report in reports
    )
    reranker_degraded = sum(
        report.source_diagnostics.runtime_source_reranker_enabled
        and report.source_diagnostics.runtime_strategy_status == "degraded"
        and not report.source_diagnostics.reranker_used
        for report in reports
    )
    reranker_status: AssuranceStatus = (
        "blocked"
        if reranker_degraded
        else "pass"
        if reranker_expected and reranker_expected == reranker_used
        else "watch"
    )
    rounds.append(
        _round(
            10,
            "2.6.0",
            "reranker_adoption_drift",
            "重排采用率与漂移",
            reranker_status,
            "交叉编码器只在来源硬门禁之后运行，启用的运行必须留下采用或降级记录。",
            [
                _metric(
                    "reranker_adoption",
                    "重排采用率",
                    f"{reranker_used}/{reranker_expected}",
                    "启用的报告均实际使用重排",
                    reranker_status,
                    "未启用不等于失败；启用后降级且未使用才是运行问题。",
                ),
                _metric(
                    "reranker_degraded",
                    "重排降级未使用",
                    str(reranker_degraded),
                    "0",
                    "blocked" if reranker_degraded else "pass",
                    "需区分硬来源规则与相关性排序，后者不能替代前者。",
                ),
            ],
            ["先以固定 qrels 验证重排收益和延迟，再扩大启用范围。"] if reranker_status != "pass" else [],
        )
    )

    industry_target = 6
    experience_target = 120
    industry_status: AssuranceStatus = (
        "pass"
        if experience.metrics.sample_size >= experience_target and experience.metrics.industry_bucket_count >= industry_target
        else "blocked"
    )
    rounds.append(
        _round(
            11,
            "2.6.1",
            "cross_industry_coverage",
            "跨行业样本覆盖",
            industry_status,
            "六行业真实任务覆盖用于检验通用主题策略，而不是把单一行业调优外推到所有主题。",
            [
                _metric(
                    "industry_buckets",
                    "行业桶",
                    str(experience.metrics.industry_bucket_count),
                    str(industry_target),
                    "pass" if experience.metrics.industry_bucket_count >= industry_target else "blocked",
                    "行业分布来自持久化真实任务，而非静态演示样本。",
                ),
                _metric(
                    "real_task_volume",
                    "真实任务数",
                    str(experience.metrics.sample_size),
                    str(experience_target),
                    "pass" if experience.metrics.sample_size >= experience_target else "blocked",
                    "样本不足时，不得宣称跨行业质量已通过。",
                ),
            ],
            ["补齐政务、医疗、金融、文旅、教育、制造六类真实任务及结果标签。"],
        )
    )

    review_status, approved_count, review_case_count, review_blockers = _artifact_review_round(review_path)
    rounds.append(
        _round(
            12,
            "2.6.2",
            "independent_review_packet",
            "独立复核工件",
            review_status,
            "100 条独立复核必须绑定锁定数据集、评审身份、实质备注和内容摘要校验。",
            [
                _metric(
                    "approved_cases",
                    "独立复核批准",
                    f"{approved_count}/{review_case_count}",
                    "100/100 已批准",
                    review_status,
                    "模板文件存在不等于独立复核已经完成。",
                )
            ],
            review_blockers[:2] or ["完成真实独立复核并确认最终工件。"],
        )
    )

    calibration_status, audit_count, calibration_case_count, accepted_customers, calibration_blockers = _artifact_calibration_round(
        calibration_path
    )
    rounds.append(
        _round(
            13,
            "2.6.3",
            "expert_calibration_customer_acceptance",
            "专家校准与客户验收",
            calibration_status,
            "专家盲评、来源相关性标注、固定证据 A/B 和三行业客户验收必须由外部人员完成。",
            [
                _metric(
                    "quality_audits",
                    "质量审计",
                    f"{audit_count}/{calibration_case_count}",
                    "100/100",
                    calibration_status,
                    "每个样本都需要独立质量审计和来源相关性标注摘要。",
                ),
                _metric(
                    "customer_acceptance",
                    "客户验收样本",
                    str(accepted_customers),
                    "3 个行业",
                    "pass" if calibration_status == "pass" else "blocked",
                    "客户侧评审人与专家盲评评审人必须保持独立。",
                ),
            ],
            calibration_blockers[:2] or ["收集三行业客户侧真实验收结论。"],
        )
    )

    screenshot_status, screenshot_observed, screenshot_target, screenshot_actions = _screenshot_version_state(
        screenshot_manifest_path,
        package_path,
    )
    failed_jobs = sum(job.status == "failed" for job in jobs)
    stale_running_jobs = sum(
        job.status == "running"
        and job.lease_expires_at is not None
        and job.lease_expires_at.replace(tzinfo=timezone.utc) < generated_at
        for job in jobs
    )
    queue_status: AssuranceStatus = "blocked" if stale_running_jobs else "watch" if failed_jobs else "pass"
    visual_queue_status: AssuranceStatus = "blocked" if screenshot_status == "blocked" or queue_status == "blocked" else queue_status
    rounds.append(
        _round(
            14,
            "2.6.4",
            "visual_office_queue_durability",
            "视觉、Office 与持久队列",
            visual_queue_status,
            "发布截图、Office 往返验证与持久任务队列必须能共同复现当前交付状态。",
            [
                _metric(
                    "screenshot_manifest",
                    "发布截图清单",
                    screenshot_observed,
                    f"版本={screenshot_target}",
                    screenshot_status,
                    "截图数、接受数和版本必须同步；旧截图不能代表新版本。",
                ),
                _metric(
                    "stale_jobs",
                    "过期运行任务",
                    str(stale_running_jobs),
                    "0",
                    "blocked" if stale_running_jobs else "pass",
                    "过期任务租约必须由持久队列恢复，而不是依赖进程内线程。",
                ),
                _metric(
                    "failed_jobs",
                    "失败任务",
                    str(failed_jobs),
                    "已复核或已重试",
                    queue_status,
                    "失败任务保留状态和错误，供重试与根因复盘。",
                ),
            ],
            [*screenshot_actions, "对失败或过期任务执行可审计的重试/恢复。" if failed_jobs or stale_running_jobs else ""],
        )
    )

    first_fourteen = list(rounds)
    predecessor_statuses = [round.status for round in first_fourteen]
    program_status: AssuranceStatus = (
        "blocked"
        if "blocked" in predecessor_statuses
        else "watch"
        if "watch" in predecessor_statuses
        else "pass"
    )
    rounds.append(
        _round(
            15,
            "2.6.5",
            "assurance_command_center",
            "统一质量保障控制台",
            program_status,
            "将 15 个版本的质量合同收敛到同一只读控制面，并向发布就绪度提供可追溯状态。",
            [
                _metric(
                    "round_completion",
                    "通过轮次",
                    f"{sum(round.status == 'pass' for round in first_fourteen)}/{len(first_fourteen)}",
                    "全部本地与外部条件均通过",
                    program_status,
                    "工程功能完成不等同于外部专家、客户或视觉验收完成。",
                )
            ],
            [
                "按被阻断轮次的真实证据要求推进，不得以模型自评替代外部结论。",
                "在每次真实样本、复核或视觉基线更新后重新读取此快照。",
            ],
        )
    )

    pass_count = sum(round.status == "pass" for round in rounds)
    watch_count = sum(round.status == "watch" for round in rounds)
    blocked_count = sum(round.status == "blocked" for round in rounds)
    score = round(sum(round.score for round in rounds) / max(1, len(rounds)))
    all_actions = _dedupe(
        (action for round in rounds if round.status != "pass" for action in round.next_actions),
        limit=12,
    )
    return ResearchAssuranceSnapshotOut(
        generated_at=generated_at,
        program_version=ASSURANCE_PROGRAM_VERSION,
        status=program_status,
        score=score,
        report_sample_size=sample_size,
        valid_report_count=report_count,
        invalid_report_count=len(invalid_jobs),
        rounds=rounds,
        summary_lines=[
            f"2.5.1-2.6.5 质量保障计划：{pass_count} 通过 / {watch_count} 关注 / {blocked_count} 阻断。",
            f"可解析研报 {report_count}/{sample_size}；低质量队列 {low_quality_flagged}/{low_quality_total}。",
            "外部独立复核、专家校准、客户验收与当前版本视觉证据只读取真实工件，不由本地代码自动批准。",
        ],
        next_actions=all_actions,
    ).model_dump(mode="json")


def _cacheable_snapshot_request(
    db: Session,
    *,
    now: datetime | None,
    report_limit: int,
    review_path: Path,
    calibration_path: Path,
    screenshot_manifest_path: Path,
    package_path: Path,
) -> bool:
    """Avoid caching in tests, custom artifact checks, and deterministic snapshots."""

    if (
        now is not None
        or report_limit != 500
        or review_path != DEFAULT_REVIEW_PATH
        or calibration_path != DEFAULT_CALIBRATION_PATH
        or screenshot_manifest_path != DEFAULT_SCREENSHOT_MANIFEST_PATH
        or package_path != DEFAULT_PACKAGE_PATH
    ):
        return False
    bind = db.get_bind()
    database = str(getattr(getattr(bind, "url", None), "database", "") or "")
    return database not in {"", ":memory:"}


def build_research_assurance_snapshot(
    db: Session,
    *,
    now: datetime | None = None,
    report_limit: int = 500,
    review_path: Path = DEFAULT_REVIEW_PATH,
    calibration_path: Path = DEFAULT_CALIBRATION_PATH,
    screenshot_manifest_path: Path = DEFAULT_SCREENSHOT_MANIFEST_PATH,
    package_path: Path = DEFAULT_PACKAGE_PATH,
) -> dict[str, Any]:
    """Build a current assurance snapshot and coalesce duplicate dashboard reads briefly."""

    cacheable = _cacheable_snapshot_request(
        db,
        now=now,
        report_limit=report_limit,
        review_path=review_path,
        calibration_path=calibration_path,
        screenshot_manifest_path=screenshot_manifest_path,
        package_path=package_path,
    )
    if not cacheable:
        return _build_research_assurance_snapshot(
            db,
            now=now,
            report_limit=report_limit,
            review_path=review_path,
            calibration_path=calibration_path,
            screenshot_manifest_path=screenshot_manifest_path,
            package_path=package_path,
        )

    global _snapshot_cache_created_at, _snapshot_cache
    with _snapshot_cache_lock:
        if _snapshot_cache is not None and monotonic() - _snapshot_cache_created_at < SNAPSHOT_CACHE_TTL_SECONDS:
            return deepcopy(_snapshot_cache)
        snapshot = _build_research_assurance_snapshot(
            db,
            now=now,
            report_limit=report_limit,
            review_path=review_path,
            calibration_path=calibration_path,
            screenshot_manifest_path=screenshot_manifest_path,
            package_path=package_path,
        )
        _snapshot_cache = deepcopy(snapshot)
        _snapshot_cache_created_at = monotonic()
        return snapshot
