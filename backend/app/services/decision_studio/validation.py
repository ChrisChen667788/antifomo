from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import hashlib
import json
import math
from pathlib import Path
import time
from typing import Any, Callable, Literal
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.decision_studio_entities import DecisionValidationRun


ValidationStatus = Literal["pass", "watch", "blocked"]
MILESTONE_ORDER = ("2.0.1", "2.0.2", "2.0.3", "2.0.4", "2.0.5", "2.0.6")


@dataclass(frozen=True)
class SuiteSpec:
    milestone: str
    label: str
    evidence_class: str
    target: str
    evaluator: Callable[[dict[str, Any]], tuple[dict[str, Any], list[dict[str, Any]]]]
    requires_artifact: bool = False


def _rows(payload: dict[str, Any], key: str = "cases") -> list[dict[str, Any]]:
    value = payload.get(key)
    return [row for row in value if isinstance(row, dict)] if isinstance(value, list) else []


def _finding(key: str, label: str, actual: Any, target: str, passed: bool) -> dict[str, Any]:
    return {
        "key": key,
        "label": label,
        "actual": actual,
        "target": target,
        "status": "pass" if passed else "blocked",
    }


def _ratio(numerator: int | float, denominator: int | float) -> float:
    return float(numerator) / float(denominator) if denominator else 0.0


def _activation_metrics(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    candidates = max(0, int(payload.get("candidate_count") or 0))
    created = max(0, int(payload.get("created_source_count") or 0))
    updated = max(0, int(payload.get("updated_source_count") or 0))
    unchanged = max(0, int(payload.get("unchanged_source_count") or 0))
    failures = max(0, int(payload.get("failed_source_count") or 0))
    provenance = max(0, int(payload.get("provenance_source_count") or 0))
    handled = created + updated + unchanged
    computed = {
        "candidate_count": candidates,
        "created_source_count": created,
        "updated_source_count": updated,
        "unchanged_source_count": unchanged,
        "failed_source_count": failures,
        "handled_rate": round(_ratio(handled, candidates), 6),
        "provenance_coverage": round(_ratio(provenance, handled), 6),
    }
    return computed, [
        _finding("candidate_count", "可激活真实来源", candidates, ">= 1", candidates >= 1),
        _finding("handled_rate", "激活处理完整率", computed["handled_rate"], "= 1.0", candidates > 0 and handled == candidates),
        _finding("failed_source_count", "激活失败来源", failures, "= 0", failures == 0),
        _finding(
            "provenance_coverage",
            "来源血缘覆盖",
            computed["provenance_coverage"],
            "= 1.0",
            handled > 0 and provenance == handled,
        ),
    ]


def _dcg(ranked: list[str], relevant: set[str], limit: int) -> float:
    return sum(1.0 / math.log2(index + 2) for index, value in enumerate(ranked[:limit]) if value in relevant)


def _ndcg(ranked: list[str], relevant: set[str], limit: int) -> float:
    ideal = sum(1.0 / math.log2(index + 2) for index in range(min(limit, len(relevant))))
    return _dcg(ranked, relevant, limit) / ideal if ideal else 0.0


def _retrieval_metrics(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases = _rows(payload)
    domains = {"medical": 0, "finance": 0, "tourism": 0}
    ndcgs: list[float] = []
    baseline_ndcgs: list[float] = []
    recalls: list[float] = []
    clickbacks = 0
    leakage_count = 0
    valid_cases = 0
    for case in cases:
        relevant = {str(value) for value in case.get("relevant_passage_ids") or [] if str(value)}
        ranked = [str(value) for value in case.get("ranked_passage_ids") or [] if str(value)]
        baseline = [str(value) for value in case.get("baseline_ranked_passage_ids") or [] if str(value)]
        if not relevant:
            continue
        valid_cases += 1
        domain = str(case.get("domain") or "").strip().lower()
        if domain in domains:
            domains[domain] += 1
        ndcgs.append(_ndcg(ranked, relevant, 10))
        baseline_ndcgs.append(_ndcg(baseline, relevant, 10))
        recalls.append(_ratio(len(set(ranked[:20]) & relevant), len(relevant)))
        clickbacks += int(case.get("clickback_ok") is True)
        included = {str(value) for value in case.get("included_source_ids") or [] if str(value)}
        returned = {str(value) for value in case.get("returned_source_ids") or [] if str(value)}
        if included:
            leakage_count += len(returned - included)
        elif returned:
            leakage_count += int(case.get("source_scope_required") is True)
    ndcg = _ratio(sum(ndcgs), len(ndcgs))
    baseline_ndcg = _ratio(sum(baseline_ndcgs), len(baseline_ndcgs))
    improvement = _ratio(ndcg - baseline_ndcg, baseline_ndcg) if baseline_ndcg > 0 else (1.0 if ndcg > 0 else 0.0)
    recall = _ratio(sum(recalls), len(recalls))
    clickback_rate = _ratio(clickbacks, valid_cases)
    computed = {
        "case_count": valid_cases,
        "domain_case_counts": domains,
        "ndcg_at_10": round(ndcg, 6),
        "baseline_ndcg_at_10": round(baseline_ndcg, 6),
        "relative_improvement": round(improvement, 6),
        "recall_at_20": round(recall, 6),
        "clickback_rate": round(clickback_rate, 6),
        "source_leakage_count": leakage_count,
    }
    return computed, [
        _finding("case_count", "人工 qrels 总量", valid_cases, ">= 300", valid_cases >= 300),
        *[
            _finding(f"{domain}_cases", f"{domain} qrels", count, ">= 100", count >= 100)
            for domain, count in domains.items()
        ],
        _finding("ndcg_at_10", "nDCG@10", computed["ndcg_at_10"], ">= 0.78", ndcg >= 0.78),
        _finding("relative_improvement", "相对 hash 基线提升", computed["relative_improvement"], ">= 0.15", improvement >= 0.15),
        _finding("recall_at_20", "Recall@20", computed["recall_at_20"], ">= 0.90", recall >= 0.90),
        _finding("clickback_rate", "段落点击回溯成功率", computed["clickback_rate"], ">= 0.98", clickback_rate >= 0.98),
        _finding("source_leakage_count", "来源范围泄漏", leakage_count, "= 0", leakage_count == 0),
    ]


def _parser_metrics(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases = _rows(payload)
    count = len(cases)
    order_rate = _ratio(sum(row.get("order_preserved") is True for row in cases), count)
    table_rate = _ratio(sum(row.get("tables_preserved") is True for row in cases), count)
    locator_rate = _ratio(sum(row.get("locator_clickback_ok") is True for row in cases), count)
    empty_count = sum(not str(row.get("extracted_text") or "").strip() for row in cases)
    computed = {
        "case_count": count,
        "order_preservation_rate": round(order_rate, 6),
        "table_preservation_rate": round(table_rate, 6),
        "locator_clickback_rate": round(locator_rate, 6),
        "empty_output_count": empty_count,
    }
    return computed, [
        _finding("case_count", "真实解析样本", count, ">= 100", count >= 100),
        _finding("order_preservation_rate", "阅读顺序保真率", computed["order_preservation_rate"], ">= 0.98", order_rate >= 0.98),
        _finding("table_preservation_rate", "表格保真率", computed["table_preservation_rate"], ">= 0.98", table_rate >= 0.98),
        _finding("locator_clickback_rate", "定位回溯率", computed["locator_clickback_rate"], ">= 0.98", locator_rate >= 0.98),
        _finding("empty_output_count", "空解析输出", empty_count, "= 0", empty_count == 0),
    ]


def _document_metrics(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases = _rows(payload, "documents")
    kinds = {"government_fsr": 0, "enterprise_fsr": 0, "project_proposal": 0}
    outline_complete = 0
    unsourced_numbers = 0
    formulas_total = 0
    formulas_with_lineage = 0
    for row in cases:
        kind = str(row.get("document_kind") or "")
        if kind in kinds:
            kinds[kind] += 1
        outline_complete += int(row.get("outline_complete") is True)
        unsourced_numbers += max(0, int(row.get("unsourced_number_count") or 0))
        formulas_total += max(0, int(row.get("formula_count") or 0))
        formulas_with_lineage += max(0, int(row.get("formula_lineage_count") or 0))
    count = len(cases)
    outline_rate = _ratio(outline_complete, count)
    formula_rate = _ratio(formulas_with_lineage, formulas_total)
    computed = {
        "document_count": count,
        "document_kind_counts": kinds,
        "outline_completion_rate": round(outline_rate, 6),
        "unsourced_number_count": unsourced_numbers,
        "formula_lineage_rate": round(formula_rate, 6),
        "formula_count": formulas_total,
    }
    return computed, [
        *[
            _finding(f"{kind}_count", f"{kind} 校准样本", value, ">= 20", value >= 20)
            for kind, value in kinds.items()
        ],
        _finding("outline_completion_rate", "法定大纲完整率", computed["outline_completion_rate"], "= 1.0", count >= 60 and outline_rate == 1.0),
        _finding("unsourced_number_count", "无来源数字", unsourced_numbers, "= 0", unsourced_numbers == 0),
        _finding("formula_lineage_rate", "公式血缘覆盖", computed["formula_lineage_rate"], "= 1.0", formulas_total > 0 and formulas_with_lineage == formulas_total),
    ]


def _claim_compiler_metrics(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    critical_total = max(0, int(payload.get("critical_claim_count") or 0))
    critical_cited = max(0, int(payload.get("critical_cited_count") or 0))
    conflicts = max(0, int(payload.get("critical_conflict_count") or 0))
    unaffected = max(0, int(payload.get("unaffected_section_count") or 0))
    reused = max(0, int(payload.get("unaffected_section_reused_count") or 0))
    citation_rate = _ratio(critical_cited, critical_total)
    reuse_rate = _ratio(reused, unaffected)
    computed = {
        "critical_claim_count": critical_total,
        "critical_citation_rate": round(citation_rate, 6),
        "critical_conflict_count": conflicts,
        "unaffected_section_count": unaffected,
        "unaffected_section_reuse_rate": round(reuse_rate, 6),
    }
    return computed, [
        _finding("critical_claim_count", "关键 Claim 样本", critical_total, ">= 100", critical_total >= 100),
        _finding("critical_citation_rate", "关键 Claim 引用覆盖", computed["critical_citation_rate"], "= 1.0", critical_total > 0 and critical_cited == critical_total),
        _finding("critical_conflict_count", "关键跨章冲突", conflicts, "= 0", conflicts == 0),
        _finding("unaffected_section_reuse_rate", "未受影响章节跳过重建", computed["unaffected_section_reuse_rate"], ">= 0.90", unaffected > 0 and reuse_rate >= 0.90),
    ]


def _report_quality_metrics(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases = _rows(payload, "reports")
    count = len(cases)
    reviewed = sum(row.get("independently_reviewed") is True for row in cases)
    low_quality = sum(row.get("low_quality") is True for row in cases)
    actual_undeliverable = [row for row in cases if row.get("actual_undeliverable") is True]
    detected = sum(row.get("predicted_undeliverable") is True for row in actual_undeliverable)
    rate = _ratio(low_quality, count)
    recall = _ratio(detected, len(actual_undeliverable))
    computed = {
        "report_count": count,
        "independently_reviewed_count": reviewed,
        "low_quality_rate": round(rate, 6),
        "actual_undeliverable_count": len(actual_undeliverable),
        "undeliverable_recall": round(recall, 6),
    }
    return computed, [
        _finding("report_count", "独立复核研报", count, ">= 100", count >= 100),
        _finding("independently_reviewed_count", "已独立复核", reviewed, "= report_count", count >= 100 and reviewed == count),
        _finding("low_quality_rate", "低质量率", computed["low_quality_rate"], "<= 0.10", count > 0 and rate <= 0.10),
        _finding("actual_undeliverable_count", "不可交付正样本", len(actual_undeliverable), ">= 10", len(actual_undeliverable) >= 10),
        _finding("undeliverable_recall", "不可交付召回率", computed["undeliverable_recall"], ">= 0.95", len(actual_undeliverable) >= 10 and recall >= 0.95),
    ]


def _entity_metrics(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases = _rows(payload, "entities")
    outputs = [row for row in cases if row.get("predicted_real") is True]
    false_entities = [row for row in outputs if row.get("actual_real") is not True]
    invalid_phrases = [row for row in cases if row.get("actual_real") is False]
    rejected_invalid = [row for row in invalid_phrases if row.get("predicted_real") is not True]
    noise_rate = _ratio(len(false_entities), len(outputs))
    invalid_recall = _ratio(len(rejected_invalid), len(invalid_phrases))
    computed = {
        "entity_case_count": len(cases),
        "output_entity_count": len(outputs),
        "noise_entity_count": len(false_entities),
        "noise_entity_rate": round(noise_rate, 6),
        "invalid_phrase_count": len(invalid_phrases),
        "invalid_phrase_recall": round(invalid_recall, 6),
    }
    return computed, [
        _finding("entity_case_count", "独立标注实体", len(cases), ">= 500", len(cases) >= 500),
        _finding("output_entity_count", "输出实体样本", len(outputs), ">= 100", len(outputs) >= 100),
        _finding("noise_entity_rate", "噪声实体率", computed["noise_entity_rate"], "<= 0.01", len(outputs) >= 100 and noise_rate <= 0.01),
        _finding("invalid_phrase_count", "无效词组正样本", len(invalid_phrases), ">= 50", len(invalid_phrases) >= 50),
        _finding("invalid_phrase_recall", "无效词组拦截召回", computed["invalid_phrase_recall"], ">= 0.95", len(invalid_phrases) >= 50 and invalid_recall >= 0.95),
    ]


def _permission_metrics(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases = _rows(payload)
    required = {"search", "chat", "cache", "export", "deep_link"}
    surfaces = {str(row.get("surface") or "") for row in cases}
    mismatches = sum(bool(row.get("expected_allowed")) != bool(row.get("observed_allowed")) for row in cases)
    leaks = sum(row.get("resource_leaked") is True for row in cases)
    credentials = sum(row.get("credential_exposed") is True for row in cases)
    computed = {
        "case_count": len(cases),
        "covered_surfaces": sorted(surfaces & required),
        "authorization_mismatch_count": mismatches,
        "resource_leak_count": leaks,
        "credential_exposure_count": credentials,
    }
    return computed, [
        _finding("case_count", "权限矩阵用例", len(cases), ">= 25", len(cases) >= 25),
        _finding("covered_surfaces", "跨面覆盖", sorted(surfaces & required), "search/chat/cache/export/deep_link", required.issubset(surfaces)),
        _finding("authorization_mismatch_count", "授权判定不一致", mismatches, "= 0", mismatches == 0),
        _finding("resource_leak_count", "资源泄漏", leaks, "= 0", leaks == 0),
        _finding("credential_exposure_count", "凭据暴露", credentials, "= 0", credentials == 0),
    ]


def _skill_metrics(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    skills = _rows(payload, "skills")
    compliant = sum(
        row.get("signature_valid") is True
        and bool(str(row.get("license_id") or "").strip())
        and row.get("approved") is True
        and float(row.get("benchmark_score") or 0) >= 0.90
        for row in skills
    )
    undeclared = sum(max(0, int(row.get("injection_undeclared_action_count") or 0)) for row in skills)
    privilege_violations = sum(max(0, int(row.get("least_privilege_violation_count") or 0)) for row in skills)
    computed = {
        "skill_count": len(skills),
        "compliant_skill_count": compliant,
        "injection_undeclared_action_count": undeclared,
        "least_privilege_violation_count": privilege_violations,
    }
    return computed, [
        _finding("skill_count", "首方 Skill", len(skills), ">= 5", len(skills) >= 5),
        _finding("compliant_skill_count", "签名/许可/基准合规", compliant, "= skill_count", len(skills) >= 5 and compliant == len(skills)),
        _finding("injection_undeclared_action_count", "注入导致未声明动作", undeclared, "= 0", undeclared == 0),
        _finding("least_privilege_violation_count", "最小权限违规", privilege_violations, "= 0", privilege_violations == 0),
    ]


def _artifact_metrics(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    required_types = {
        "executive_brief", "mind_map", "data_table", "slide_outline", "infographic_spec", "audio_script"
    }
    types = {str(value) for value in payload.get("artifact_types") or []}
    critical_total = max(0, int(payload.get("critical_fact_count") or 0))
    critical_consistent = max(0, int(payload.get("critical_consistent_count") or 0))
    ordinary_total = max(0, int(payload.get("ordinary_fact_count") or 0))
    ordinary_consistent = max(0, int(payload.get("ordinary_consistent_count") or 0))
    stale = max(0, int(payload.get("stale_artifact_count") or 0))
    critical_rate = _ratio(critical_consistent, critical_total)
    ordinary_rate = _ratio(ordinary_consistent, ordinary_total)
    computed = {
        "artifact_types": sorted(types),
        "critical_fact_count": critical_total,
        "critical_consistency_rate": round(critical_rate, 6),
        "ordinary_fact_count": ordinary_total,
        "ordinary_consistency_rate": round(ordinary_rate, 6),
        "stale_artifact_count": stale,
    }
    return computed, [
        _finding("artifact_types", "六类决策产物", sorted(types), "all 6 types", required_types.issubset(types)),
        _finding("critical_consistency_rate", "关键事实跨形态一致率", computed["critical_consistency_rate"], "= 1.0", critical_total > 0 and critical_consistent == critical_total),
        _finding("ordinary_consistency_rate", "普通事实跨形态一致率", computed["ordinary_consistency_rate"], ">= 0.98", ordinary_total > 0 and ordinary_rate >= 0.98),
        _finding("stale_artifact_count", "过期产物", stale, "= 0", stale == 0),
    ]


def _office_visual_metrics(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    cases = _rows(payload)
    formats = {str(row.get("format") or "").lower() for row in cases}
    themes = {str(row.get("theme") or "").lower() for row in cases}
    roundtrip_failures = sum(row.get("roundtrip_ok") is not True for row in cases)
    visual_failures = sum(row.get("visual_approved") is not True for row in cases)
    computed = {
        "case_count": len(cases),
        "formats": sorted(formats),
        "themes": sorted(themes),
        "roundtrip_failure_count": roundtrip_failures,
        "visual_failure_count": visual_failures,
    }
    return computed, [
        _finding("case_count", "Office/视觉用例", len(cases), ">= 6", len(cases) >= 6),
        _finding("formats", "Office 格式覆盖", sorted(formats), "docx/xlsx/pptx", {"docx", "xlsx", "pptx"}.issubset(formats)),
        _finding("themes", "Studio 主题覆盖", sorted(themes), "light/dark", {"light", "dark"}.issubset(themes)),
        _finding("roundtrip_failure_count", "Office roundtrip 失败", roundtrip_failures, "= 0", roundtrip_failures == 0),
        _finding("visual_failure_count", "人工视觉未确认", visual_failures, "= 0", visual_failures == 0),
    ]


def _performance_metrics(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    environment = str(payload.get("environment") or "").strip().lower()
    users = max(0, int(payload.get("concurrent_users") or 0))
    requests = max(0, int(payload.get("request_count") or 0))
    p95 = max(0.0, float(payload.get("p95_ms") or 0))
    errors = max(0.0, float(payload.get("error_rate") or 0))
    cold_start = max(0.0, float(payload.get("model_cold_start_seconds") or 0))
    cost = max(0.0, float(payload.get("long_report_cost_cny") or 0))
    computed = {
        "environment": environment,
        "concurrent_users": users,
        "request_count": requests,
        "p95_ms": round(p95, 3),
        "error_rate": round(errors, 6),
        "model_cold_start_seconds": round(cold_start, 3),
        "long_report_cost_cny": round(cost, 3),
    }
    return computed, [
        _finding("environment", "压测环境", environment or "missing", "= production", environment == "production"),
        _finding("concurrent_users", "并发用户", users, ">= 20", users >= 20),
        _finding("request_count", "压测请求", requests, ">= 500", requests >= 500),
        _finding("p95_ms", "交互 API P95", p95, "<= 2500 ms", 0 < p95 <= 2500),
        _finding("error_rate", "压测错误率", errors, "<= 0.01", errors <= 0.01),
        _finding("model_cold_start_seconds", "BGE-M3 冷启动", cold_start, "<= 120 s", 0 < cold_start <= 120),
        _finding("long_report_cost_cny", "长研报单次模型成本", cost, "<= 20 CNY", 0 < cost <= 20),
    ]


def _recovery_metrics(payload: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    environment = str(payload.get("environment") or "").strip().lower()
    scenarios = _rows(payload, "scenarios")
    required = {"queue_restart", "backup_restore", "audit_export", "external_model_volume_fail_closed"}
    names = {str(row.get("scenario") or "") for row in scenarios}
    failed = sum(row.get("passed") is not True for row in scenarios)
    data_loss = sum(max(0, int(row.get("data_loss_count") or 0)) for row in scenarios)
    max_rto = max((float(row.get("recovery_seconds") or 0) for row in scenarios), default=0.0)
    computed = {
        "environment": environment,
        "scenario_count": len(scenarios),
        "covered_scenarios": sorted(names & required),
        "failed_scenario_count": failed,
        "data_loss_count": data_loss,
        "max_recovery_seconds": round(max_rto, 3),
    }
    return computed, [
        _finding("environment", "恢复演练环境", environment or "missing", "= production", environment == "production"),
        _finding("covered_scenarios", "恢复场景覆盖", sorted(names & required), "all 4 scenarios", required.issubset(names)),
        _finding("failed_scenario_count", "恢复失败场景", failed, "= 0", failed == 0),
        _finding("data_loss_count", "恢复数据丢失", data_loss, "= 0", data_loss == 0),
        _finding("max_recovery_seconds", "最大恢复时间", max_rto, "<= 900 s", bool(scenarios) and 0 < max_rto <= 900),
    ]


SUITE_SPECS: dict[str, SuiteSpec] = {
    "real_data_activation": SuiteSpec("2.0.1", "现有知识/研报真实数据激活", "engineering", "至少一个真实来源完整激活且血缘覆盖 100%。", _activation_metrics),
    "retrieval_benchmark": SuiteSpec("2.0.1", "三行业语义检索基准", "independent_review", "300 条人工 qrels；每行业 100；nDCG@10>=0.78，Recall@20>=0.90，来源泄漏为 0。", _retrieval_metrics, True),
    "parser_benchmark": SuiteSpec("2.0.1", "真实文档解析基准", "independent_review", "100 份真实文档，顺序/表格/定位保真率均 >=98%。", _parser_metrics, True),
    "document_contract_calibration": SuiteSpec("2.0.2", "中国正式文档专家校准", "expert_review", "三类正式文档各 20 份；大纲、数字来源和公式血缘全部合格。", _document_metrics, True),
    "claim_compiler_quality": SuiteSpec("2.0.2", "Claim Graph 与差量编译", "engineering", "关键引用 100%，关键冲突 0，未受影响章节复用 >=90%。", _claim_compiler_metrics, True),
    "report_quality_independent_review": SuiteSpec("2.0.3", "100 条研报独立复核", "independent_review", "100/100 独立复核，低质量率 <=10%，不可交付召回 >=95%。", _report_quality_metrics, True),
    "entity_authenticity_benchmark": SuiteSpec("2.0.3", "机构实体真实性基准", "independent_review", "500 条独立标注实体，噪声实体率 <=1%，无效词组召回 >=95%。", _entity_metrics, True),
    "permission_leakage_matrix": SuiteSpec("2.0.4", "ACL 与连接器跨面权限矩阵", "security_review", "search/chat/cache/export/deep_link 全覆盖且资源/凭据泄漏为 0。", _permission_metrics, True),
    "skill_security_benchmark": SuiteSpec("2.0.4", "Skill 签名、沙箱与注入基准", "security_review", "至少 5 个首方 Skill 全部签名/许可/基准合格，未声明动作和越权均为 0。", _skill_metrics, True),
    "cross_artifact_consistency": SuiteSpec("2.0.5", "六类决策产物一致性", "engineering", "六类产物齐全；关键事实 100%、普通事实 >=98% 一致且无 stale 产物。", _artifact_metrics, True),
    "office_visual_acceptance": SuiteSpec("2.0.5", "Office roundtrip 与视觉确认", "visual_review", "DOCX/XLSX/PPTX roundtrip 和 Studio light/dark 人工视觉确认全部通过。", _office_visual_metrics, True),
    "performance_cost_benchmark": SuiteSpec("2.0.6", "并发、时延、冷启动与成本", "engineering", "production 环境 20 并发、500 请求、P95<=2.5s、错误率<=1%、冷启动<=120s、长研报成本<=20元。", _performance_metrics, True),
    "recovery_audit_reliability": SuiteSpec("2.0.6", "恢复、审计与外置模型盘可靠性", "engineering", "production 环境队列重启、备份恢复、审计导出、外置模型盘 fail-closed 全通过且数据零丢失。", _recovery_metrics, True),
}


def validation_specs_payload() -> dict[str, Any]:
    milestones = []
    for milestone in MILESTONE_ORDER:
        suites = [
            {
                "suite_key": key,
                "label": spec.label,
                "evidence_class": spec.evidence_class,
                "target": spec.target,
                "requires_artifact": spec.requires_artifact,
            }
            for key, spec in SUITE_SPECS.items()
            if spec.milestone == milestone
        ]
        milestones.append({"version": milestone, "implementation_status": "implemented", "suites": suites})
    return {"release_version": "2.0.7-development", "milestones": milestones}


def _canonical_digest(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _external_evidence_findings(
    *,
    spec: SuiteSpec,
    user_id: UUID | None,
    reviewer_id: str,
    reviewer_role: str,
    attestation: str,
    source_artifact_uri: str,
    reviewed_at: datetime | None,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    normalized_reviewed_at = None
    if reviewed_at is not None:
        normalized_reviewed_at = reviewed_at.replace(tzinfo=UTC) if reviewed_at.tzinfo is None else reviewed_at.astimezone(UTC)
    if spec.evidence_class != "engineering":
        findings.extend(
            [
                _finding("reviewer_id", "独立审阅者标识", bool(reviewer_id.strip()), "required", bool(reviewer_id.strip())),
                _finding("reviewer_role", "审阅者角色", bool(reviewer_role.strip()), "required", bool(reviewer_role.strip())),
                _finding("attestation", "审阅声明", len(attestation.strip()), ">= 20 chars", len(attestation.strip()) >= 20),
                _finding(
                    "reviewed_at",
                    "审阅时间",
                    normalized_reviewed_at.isoformat() if normalized_reviewed_at else None,
                    "required and not future",
                    normalized_reviewed_at is not None and normalized_reviewed_at <= datetime.now(UTC) + timedelta(minutes=5),
                ),
            ]
        )
        if user_id is not None and spec.evidence_class in {"independent_review", "expert_review"}:
            independent = bool(reviewer_id.strip()) and reviewer_id.strip() != str(user_id)
            findings.append(_finding("independent_actor", "审阅者与产物所有者分离", independent, "true", independent))
    if spec.requires_artifact:
        findings.append(
            _finding("source_artifact_uri", "原始证据 artifact", bool(source_artifact_uri.strip()), "required", bool(source_artifact_uri.strip()))
        )
    return findings


def preview_validation_run(
    *,
    suite_key: str,
    metrics: dict[str, Any],
    evidence: dict[str, Any] | None = None,
    user_id: UUID | None = None,
    reviewer_id: str = "",
    reviewer_role: str = "",
    attestation: str = "",
    source_artifact_uri: str = "",
    reviewed_at: datetime | None = None,
) -> dict[str, Any]:
    spec = SUITE_SPECS.get(suite_key)
    if spec is None:
        raise ValueError(f"Unknown validation suite: {suite_key}")
    computed, findings = spec.evaluator(metrics)
    findings.extend(
        _external_evidence_findings(
            spec=spec,
            user_id=user_id,
            reviewer_id=reviewer_id,
            reviewer_role=reviewer_role,
            attestation=attestation,
            source_artifact_uri=source_artifact_uri,
            reviewed_at=reviewed_at,
        )
    )
    passed = sum(row["status"] == "pass" for row in findings)
    score = round(100 * passed / len(findings)) if findings else 0
    status: ValidationStatus = "pass" if findings and passed == len(findings) else "blocked"
    digest = _canonical_digest(
        {
            "suite_key": suite_key,
            "metrics": metrics,
            "evidence": evidence or {},
            "reviewer_id": reviewer_id,
            "reviewer_role": reviewer_role,
            "attestation": attestation,
            "source_artifact_uri": source_artifact_uri,
            "reviewed_at": reviewed_at,
        }
    )
    return {
        "suite_key": suite_key,
        "milestone_version": spec.milestone,
        "label": spec.label,
        "evidence_class": spec.evidence_class,
        "status": status,
        "score": score,
        "target": spec.target,
        "computed_metrics": computed,
        "findings": findings,
        "input_digest": digest,
    }


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return normalized.isoformat().replace("+00:00", "Z")


def serialize_validation_run(run: DecisionValidationRun) -> dict[str, Any]:
    spec = SUITE_SPECS.get(run.suite_key)
    return {
        "id": str(run.id),
        "user_id": str(run.user_id),
        "milestone_version": run.milestone_version,
        "suite_key": run.suite_key,
        "label": spec.label if spec else run.suite_key,
        "evidence_class": run.evidence_class,
        "status": run.status,
        "score": round(100 * sum(row.get("status") == "pass" for row in run.findings_payload or []) / max(1, len(run.findings_payload or []))),
        "target": spec.target if spec else "",
        "computed_metrics": dict(run.metrics_payload or {}),
        "evidence": dict(run.evidence_payload or {}),
        "findings": list(run.findings_payload or []),
        "input_digest": run.input_digest,
        "reviewer_id": run.reviewer_id,
        "reviewer_role": run.reviewer_role,
        "attestation": run.attestation,
        "source_artifact_uri": run.source_artifact_uri,
        "reviewed_at": _iso(run.reviewed_at),
        "started_at": _iso(run.started_at),
        "completed_at": _iso(run.completed_at),
        "created_at": _iso(run.created_at),
    }


def record_validation_run(
    db: Session,
    *,
    user_id: UUID,
    suite_key: str,
    metrics: dict[str, Any],
    evidence: dict[str, Any] | None = None,
    reviewer_id: str = "",
    reviewer_role: str = "",
    attestation: str = "",
    source_artifact_uri: str = "",
    reviewed_at: datetime | None = None,
    started_at: datetime | None = None,
) -> DecisionValidationRun:
    started = started_at or datetime.now(UTC)
    result = preview_validation_run(
        suite_key=suite_key,
        metrics=metrics,
        evidence=evidence,
        user_id=user_id,
        reviewer_id=reviewer_id,
        reviewer_role=reviewer_role,
        attestation=attestation,
        source_artifact_uri=source_artifact_uri,
        reviewed_at=reviewed_at,
    )
    completed = datetime.now(UTC)
    run = DecisionValidationRun(
        user_id=user_id,
        milestone_version=result["milestone_version"],
        suite_key=suite_key,
        evidence_class=result["evidence_class"],
        status=result["status"],
        metrics_payload=result["computed_metrics"],
        evidence_payload=evidence or {},
        findings_payload=result["findings"],
        input_digest=result["input_digest"],
        reviewer_id=reviewer_id.strip(),
        reviewer_role=reviewer_role.strip(),
        attestation=attestation.strip(),
        source_artifact_uri=source_artifact_uri.strip(),
        reviewed_at=reviewed_at,
        started_at=started,
        completed_at=completed,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


def list_validation_runs(
    db: Session,
    *,
    user_id: UUID,
    suite_key: str | None = None,
    limit: int = 100,
) -> list[DecisionValidationRun]:
    query = select(DecisionValidationRun).where(DecisionValidationRun.user_id == user_id)
    if suite_key:
        query = query.where(DecisionValidationRun.suite_key == suite_key)
    query = query.order_by(
        DecisionValidationRun.completed_at.desc(),
        DecisionValidationRun.created_at.desc(),
        DecisionValidationRun.id.desc(),
    ).limit(max(1, min(limit, 1000)))
    return list(db.scalars(query).all())


def build_release_program_snapshot(db: Session, *, user_id: UUID) -> dict[str, Any]:
    latest: dict[str, DecisionValidationRun] = {}
    for run in list_validation_runs(db, user_id=user_id, limit=1000):
        latest.setdefault(run.suite_key, run)
    milestones: list[dict[str, Any]] = []
    for version in MILESTONE_ORDER:
        suites: list[dict[str, Any]] = []
        for key, spec in SUITE_SPECS.items():
            if spec.milestone != version:
                continue
            run = latest.get(key)
            if run is None:
                suites.append(
                    {
                        "suite_key": key,
                        "label": spec.label,
                        "evidence_class": spec.evidence_class,
                        "status": "blocked",
                        "score": 0,
                        "target": spec.target,
                        "latest_run": None,
                        "blockers": ["尚无不可变验证运行记录。"],
                    }
                )
                continue
            serialized = serialize_validation_run(run)
            blockers = [str(row.get("label") or row.get("key")) for row in run.findings_payload or [] if row.get("status") != "pass"]
            suites.append(
                {
                    "suite_key": key,
                    "label": spec.label,
                    "evidence_class": spec.evidence_class,
                    "status": run.status,
                    "score": serialized["score"],
                    "target": spec.target,
                    "latest_run": serialized,
                    "blockers": blockers,
                }
            )
        blocked = sum(row["status"] == "blocked" for row in suites)
        watch = sum(row["status"] == "watch" for row in suites)
        status: ValidationStatus = "blocked" if blocked else ("watch" if watch else "pass")
        milestones.append(
            {
                "version": version,
                "implementation_status": "implemented",
                "acceptance_status": status,
                "score": round(sum(int(row["score"]) for row in suites) / max(1, len(suites))),
                "suite_count": len(suites),
                "passed_suite_count": sum(row["status"] == "pass" for row in suites),
                "suites": suites,
            }
        )
    overall: ValidationStatus = "blocked" if any(row["acceptance_status"] == "blocked" for row in milestones) else "pass"
    return {
        "generated_at": _iso(datetime.now(UTC)),
        "release_version": "2.0.7-development",
        "implementation_status": "implemented",
        "overall_status": overall,
        "readiness_score": round(sum(int(row["score"]) for row in milestones) / len(milestones)),
        "milestones": milestones,
        "honesty_note": "工程能力完成不等于商业放行；缺少人工、专家、安全、视觉或客户证据时保持 blocked。",
    }


def build_validation_audit_export(db: Session, *, user_id: UUID, limit: int = 1000) -> dict[str, Any]:
    runs = list(reversed(list_validation_runs(db, user_id=user_id, limit=limit)))
    previous = "0" * 64
    records: list[dict[str, Any]] = []
    for run in runs:
        payload = serialize_validation_run(run)
        record_hash = _canonical_digest({"previous_hash": previous, "record": payload})
        records.append({"previous_hash": previous, "record_hash": record_hash, "record": payload})
        previous = record_hash
    return {
        "schema_version": "2.0.6",
        "generated_at": _iso(datetime.now(UTC)),
        "record_count": len(records),
        "chain_head": previous,
        "chain_valid": all(row["previous_hash"] == (records[index - 1]["record_hash"] if index else "0" * 64) for index, row in enumerate(records)),
        "records": records,
    }


def run_local_reliability_probe(db: Session, *, user_id: UUID, audit_sample_limit: int = 1000) -> dict[str, Any]:
    settings = get_settings()
    started = time.perf_counter()
    db.execute(text("SELECT 1")).scalar_one()
    database_latency_ms = (time.perf_counter() - started) * 1000
    audit = build_validation_audit_export(db, user_id=user_id, limit=audit_sample_limit)
    cache_value = str(settings.decision_embedding_cache_dir or "")
    cache_path = Path(cache_value).expanduser() if cache_value else None
    external = bool(cache_path and str(cache_path).startswith("/Volumes/"))
    mount_path = Path("/Volumes") / cache_path.parts[2] if external and cache_path and len(cache_path.parts) > 2 else None
    mount_ready = bool(mount_path and mount_path.exists() and mount_path.is_mount()) if external else True
    cache_ready = bool(cache_path and cache_path.exists() and cache_path.is_dir())
    blockers = [
        "仍需提交 production 环境 20 并发/500 请求原始压测 artifact，并补齐冷启动与模型成本。",
        "仍需在 production 环境执行真实队列重启与数据库备份恢复演练。",
    ]
    if external and not mount_ready:
        blockers.insert(0, "外置模型缓存卷未挂载；语义模型必须 fail-closed。")
    return {
        "status": "blocked",
        "database_latency_ms": round(database_latency_ms, 3),
        "audit_chain_valid": audit["chain_valid"],
        "audit_record_count": audit["record_count"],
        "embedding_cache_path": cache_value,
        "external_cache": external,
        "external_mount_ready": mount_ready,
        "cache_directory_ready": cache_ready,
        "blockers": blockers,
    }
