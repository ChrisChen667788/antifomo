from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.entities import KnowledgeEntry
from app.schemas.research import (
    ResearchCommercialSummaryOut,
    ResearchDeliveryQualityProfileOut,
    ResearchGoldenEvaluationCaseOut,
    ResearchGoldenEvaluationOut,
    ResearchOfflineEvaluationMetricOut,
    ResearchOfflineEvaluationOut,
    ResearchOfflineEvaluationWeakReportOut,
    ResearchReportReadinessOut,
    ResearchReportResponse,
    ResearchReportSectionOut,
    ResearchScenarioOut,
    ResearchSourceDiagnosticsOut,
    ResearchSourceOut,
    ResearchTechnicalAppendixOut,
)
from app.services.content_extractor import normalize_text
from app.services.research_quality_service import build_research_quality_profile
from app.services.research_rag_quality_service import rerank_sources_cross_encoder
from app.services.research_solution_intelligence_service import build_solution_delivery_pack

_METRIC_BENCHMARKS: dict[str, float] = {
    "retrieval_hit_rate": 0.72,
    "target_support_rate": 0.68,
    "section_quota_pass_rate": 0.74,
    "official_source_recall_at_5": 0.62,
    "unsupported_target_rate": 0.18,
    "reranker_official_recall_at_5": 0.68,
    "solution_delivery_quality_pass_rate": 0.70,
    "project_proposal_quality_pass_rate": 0.68,
    "delivery_self_review_gain_rate": 0.80,
}


def _metric_status(rate: float, *, benchmark: float) -> str:
    if rate >= benchmark:
        return "good"
    if rate >= max(0.0, benchmark - 0.12):
        return "watch"
    return "bad"


def _inverse_metric_status(rate: float, *, benchmark: float) -> str:
    if rate <= benchmark:
        return "good"
    if rate <= min(1.0, benchmark + 0.12):
        return "watch"
    return "bad"


def _safe_rate(numerator: int, denominator: int) -> float:
    if denominator <= 0:
        return 0.0
    return max(0.0, min(float(numerator) / float(denominator), 1.0))


def _percent(rate: float) -> int:
    return int(round(rate * 100))


def _parse_stored_report(entry: KnowledgeEntry) -> ResearchReportResponse | None:
    payload = entry.metadata_payload if isinstance(entry.metadata_payload, dict) else None
    report_payload = payload.get("report") if isinstance(payload, dict) else None
    if not isinstance(report_payload, dict):
        return None
    try:
        return ResearchReportResponse.model_validate(report_payload)
    except Exception:
        return None


def _ranked_entity_names(values: Any) -> list[str]:
    names: list[str] = []
    if not isinstance(values, list):
        return names
    for item in values:
        if isinstance(item, dict):
            candidate = normalize_text(str(item.get("name") or ""))
        else:
            candidate = normalize_text(str(getattr(item, "name", "") or ""))
        if candidate and candidate not in names:
            names.append(candidate)
    return names


def _declared_target_accounts(report: ResearchReportResponse) -> list[str]:
    names: list[str] = []
    for value in [*report.target_accounts, *_ranked_entity_names(report.top_target_accounts)]:
        normalized = normalize_text(value)
        if normalized and normalized not in names:
            names.append(normalized)
    return names


def _supported_target_accounts(report: ResearchReportResponse) -> list[str]:
    names: list[str] = []
    for value in report.source_diagnostics.supported_target_accounts:
        normalized = normalize_text(value)
        if normalized and normalized not in names:
            names.append(normalized)
    return names


def _unsupported_target_accounts(report: ResearchReportResponse) -> list[str]:
    supported = set(_supported_target_accounts(report))
    names: list[str] = []
    for value in report.source_diagnostics.unsupported_target_accounts:
        normalized = normalize_text(value)
        if normalized and normalized not in supported and normalized not in names:
            names.append(normalized)
    if names:
        return names
    for value in _declared_target_accounts(report):
        if value not in supported and value not in names:
            names.append(value)
    return names


def _quota_sections(report: ResearchReportResponse) -> list[Any]:
    return [section for section in report.sections if int(getattr(section, "evidence_quota", 0) or 0) > 0]


def _source_is_official(source: ResearchSourceOut) -> bool:
    tier = normalize_text(str(getattr(source, "source_tier", "") or "")).lower()
    if tier == "official":
        return True
    text = normalize_text(
        " ".join(
            [
                str(getattr(source, "title", "") or ""),
                str(getattr(source, "url", "") or ""),
                str(getattr(source, "snippet", "") or ""),
                str(getattr(source, "source_label", "") or ""),
            ]
        )
    ).lower()
    return any(token in text for token in ("gov.cn", ".gov", "ccgp", "ggzy", "cecbid", "官网", "官方"))


def _has_official_source_at_k(sources: list[ResearchSourceOut], *, k: int) -> bool:
    return any(_source_is_official(source) for source in sources[: max(1, k)])


def _report_retrieval_hit(report: ResearchReportResponse) -> bool:
    diagnostics = report.source_diagnostics
    if int(diagnostics.strict_topic_source_count or 0) <= 0:
        return False
    if float(diagnostics.strict_match_ratio or 0.0) >= 0.34:
        return True
    if diagnostics.retrieval_quality in {"medium", "high"} and report.source_count >= 4:
        return True
    return report.evidence_density != "low" and report.source_quality != "low"


def _delivery_profiles_for_evaluation(
    report: ResearchReportResponse,
) -> tuple[ResearchDeliveryQualityProfileOut, ResearchDeliveryQualityProfileOut]:
    pack = report.solution_delivery_pack
    solution_profile = pack.solution_quality_profile
    proposal_profile = pack.project_proposal_quality_profile
    if int(solution_profile.overall_score or 0) > 0 and int(proposal_profile.overall_score or 0) > 0:
        return solution_profile, proposal_profile
    rebuilt_pack = build_solution_delivery_pack(
        report,
        scenario=pack.scenario,
        target_customer=pack.target_customer,
        vertical_scene=pack.vertical_scene,
    )
    return rebuilt_pack.solution_quality_profile, rebuilt_pack.project_proposal_quality_profile


def _delivery_status_rank(value: str) -> int:
    return {"pass": 0, "watch": 1, "fail": 2}.get(normalize_text(value).lower(), 1)


def _worst_delivery_status(
    solution_profile: ResearchDeliveryQualityProfileOut,
    proposal_profile: ResearchDeliveryQualityProfileOut,
) -> str:
    statuses = [solution_profile.status, proposal_profile.status]
    return max(statuses, key=_delivery_status_rank)


def _weakness_score(
    report: ResearchReportResponse,
    *,
    solution_profile: ResearchDeliveryQualityProfileOut | None = None,
    proposal_profile: ResearchDeliveryQualityProfileOut | None = None,
) -> int:
    diagnostics = report.source_diagnostics
    supported_targets = _supported_target_accounts(report)
    unsupported_targets = _unsupported_target_accounts(report)
    quota_sections = _quota_sections(report)
    failing_sections = [section for section in quota_sections if not bool(getattr(section, "meets_evidence_quota", False))]
    score = 0
    if not _report_retrieval_hit(report):
        score += 34
    score += len(unsupported_targets) * 12
    score += sum(max(int(getattr(section, "quota_gap", 0) or 0), 1) * 8 for section in failing_sections)
    if diagnostics.official_source_ratio < 0.25:
        score += 8
    if report.report_readiness.status != "ready":
        score += 6
    if not supported_targets and _declared_target_accounts(report):
        score += 8
    resolved_solution = solution_profile
    resolved_proposal = proposal_profile
    if resolved_solution is not None and resolved_solution.status != "pass":
        score += 10 if resolved_solution.status == "watch" else 18
    if resolved_proposal is not None and resolved_proposal.status != "pass":
        score += 12 if resolved_proposal.status == "watch" else 22
        score += min(12, len(resolved_proposal.missing_axes) * 3)
    return score


def _golden_source(title: str, url: str, snippet: str, *, tier: str = "official") -> ResearchSourceOut:
    return ResearchSourceOut(
        title=title,
        url=url,
        domain=url.split("/")[2] if "://" in url else "",
        snippet=snippet,
        search_query=title,
        source_type="policy" if tier == "official" else "news",
        content_status="fetched",
        source_tier=tier,  # type: ignore[arg-type]
    )


def _golden_section(
    title: str,
    items: list[str],
    *,
    official_count: int = 1,
    quota: int = 2,
    passed: bool = True,
) -> ResearchReportSectionOut:
    evidence_count = quota if passed else max(0, quota - 1)
    return ResearchReportSectionOut(
        title=title,
        items=items,
        status="ready" if passed else "degraded",
        evidence_density="high" if passed else "medium",
        source_quality="high" if official_count > 0 else "medium",
        evidence_count=evidence_count,
        evidence_quota=quota,
        meets_evidence_quota=passed,
        quota_gap=0 if passed else 1,
        source_tier_counts={"official": official_count, "media": max(0, evidence_count - official_count)},
    )


def _golden_base_report(
    *,
    keyword: str,
    title: str,
    focus: str,
    summary: str,
    angle: str,
    target_accounts: list[str],
    supported_targets: list[str],
    unsupported_targets: list[str],
    sections: list[ResearchReportSectionOut],
    sources: list[ResearchSourceOut],
    budget_signals: list[str],
    departments: list[str],
    competitors: list[str],
    partners: list[str],
    readiness_status: str = "ready",
) -> ResearchReportResponse:
    source_tiers: dict[str, int] = {}
    for source in sources:
        source_tiers[source.source_tier] = source_tiers.get(source.source_tier, 0) + 1
    official_ratio = source_tiers.get("official", 0) / max(len(sources), 1)
    readiness = ResearchReportReadinessOut(
        status=readiness_status,  # type: ignore[arg-type]
        score=86 if readiness_status == "ready" else 64,
        actionable=readiness_status in {"ready", "degraded"},
        evidence_gate_passed=official_ratio >= 0.25 and bool(supported_targets),
        reasons=[],
        missing_axes=[] if readiness_status == "ready" else ["官方证据或账户支撑不足"],
    )
    return ResearchReportResponse(
        keyword=keyword,
        research_focus=focus,
        output_language="zh-CN",
        research_mode="deep",
        report_title=title,
        executive_summary=summary,
        consulting_angle=angle,
        sections=sections,
        target_accounts=target_accounts,
        target_departments=departments,
        public_contact_channels=["官网公开联系入口"] if departments else [],
        account_team_signals=["建议由行业客户经理联合售前准备会前材料"] if departments else [],
        budget_signals=budget_signals,
        project_distribution=["围绕重点账户建立 30/60/90 天推进清单"],
        strategic_directions=["先补官方证据，再形成一页纸账户作战图"],
        tender_timeline=["预算复核后进入方案比选"] if budget_signals else [],
        ecosystem_partners=partners,
        competitor_profiles=competitors,
        benchmark_cases=["同区域同类平台扩容案例"],
        competition_analysis=["对比既有供应商、集成商和可替代方案的进入壁垒"],
        source_count=len(sources),
        evidence_density="high" if len(sources) >= 4 else "medium",
        source_quality="high" if official_ratio >= 0.4 else "medium",
        sources=sources,
        source_diagnostics=ResearchSourceDiagnosticsOut(
            supported_target_accounts=supported_targets,
            unsupported_target_accounts=unsupported_targets,
            source_tier_counts=source_tiers,
            retained_source_count=len(sources),
            strict_topic_source_count=max(1, len(sources) - len(unsupported_targets)),
            retrieval_quality="high" if len(sources) >= 4 and official_ratio >= 0.4 else "medium",
            evidence_mode="strong" if official_ratio >= 0.4 and supported_targets else "provisional",
            evidence_mode_label="强证据" if official_ratio >= 0.4 and supported_targets else "候选证据",
            strict_match_ratio=0.78 if supported_targets else 0.24,
            official_source_ratio=official_ratio,
            unique_domain_count=max(3, len({source.domain for source in sources if source.domain})),
        ),
        report_readiness=readiness,
        commercial_summary=ResearchCommercialSummaryOut(
            account_focus=target_accounts[:3],
            budget_signal="；".join(budget_signals[:2]),
            entry_window="预算复核至方案比选前",
            competition_or_partner="；".join([*competitors[:1], *partners[:1]]),
            next_action="补齐官方证据后组织售前、客户经理和生态伙伴做会前推演。",
        ),
        technical_appendix=ResearchTechnicalAppendixOut(
            key_assumptions=["预算窗口真实存在", "业务部门具备方案比选需求"],
            scenario_comparison=[
                ResearchScenarioOut(name="保守情景", summary="先做低成本验证", implication="适合信息不足时推进。"),
                ResearchScenarioOut(name="进攻情景", summary="直接准备方案比选材料", implication="适合官方证据充足时推进。"),
            ],
            limitations=["公开证据仍需持续跟踪更新"],
        ),
        generated_at=datetime.now(timezone.utc),
    )


def _golden_reports() -> list[tuple[str, str, ResearchReportResponse]]:
    return [
        (
            "gov-cloud-budget",
            "government_cloud",
            _golden_base_report(
                keyword="上海数据集团政务云预算",
                title="上海数据集团政务云预算窗口研判",
                focus="解决方案设计和针对性打单的战略参考。",
                summary="上海数据集团政务云扩容出现预算复核、采购中心确认和方案比选窗口。",
                angle="按政策牵引、预算招采、组织入口、方案切口、生态竞合和交付风险六段式推进。",
                target_accounts=["上海数据集团"],
                supported_targets=["上海数据集团"],
                unsupported_targets=[],
                sections=[
                    _golden_section("政策与领导信号", ["数字政府规划牵引政务云扩容。"]),
                    _golden_section("项目与商机判断", ["7 月预算复核，8 月进入方案比选。"]),
                    _golden_section("解决方案设计建议", ["准备安全合规、信创适配和云平台扩容路线。"]),
                ],
                sources=[
                    _golden_source("上海数据集团公告", "https://example.gov.cn/shanghai-data-budget", "预算复核和采购意向。"),
                    _golden_source("上海公共资源交易公告", "https://ggzy.example.gov.cn/cloud", "政务云扩容采购意向。"),
                    _golden_source("数字政府规划", "https://example.gov.cn/digital-government", "数字政府政策牵引。"),
                    _golden_source("行业媒体跟踪", "https://media.example.cn/cloud", "方案比选动态。", tier="media"),
                ],
                budget_signals=["7 月预算复核", "8 月方案比选"],
                departments=["采购中心", "数字化办公室"],
                competitors=["既有集成商"],
                partners=["本地运营商"],
            ),
        ),
        (
            "compute-llm-capacity",
            "compute_llm",
            _golden_base_report(
                keyword="华东智算中心大模型推理算力",
                title="华东智算中心推理算力需求研判",
                focus="评估算力供给、行业应用需求和商业闭环。",
                summary="目标账户存在推理算力扩容和行业模型应用落地需求，但预算模式仍需补证。",
                angle="按供给、需求场景、成本预算、数据安全、生态合作和商业闭环验证。",
                target_accounts=["华东智算中心", "省属能源集团"],
                supported_targets=["华东智算中心"],
                unsupported_targets=["省属能源集团"],
                sections=[
                    _golden_section("行业资讯判断", ["智算资源供给紧张，推理负载增加。"]),
                    _golden_section("项目与商机判断", ["存在租赁和采购两种预算路径。"], passed=False),
                    _golden_section("解决方案设计建议", ["优先验证 GPU 资源、推理服务和数据安全边界。"]),
                ],
                sources=[
                    _golden_source("智算中心建设公告", "https://example.gov.cn/compute", "GPU 集群和机房建设。"),
                    _golden_source("行业应用报道", "https://media.example.cn/llm", "大模型推理需求提升。", tier="media"),
                    _golden_source("生态合作新闻", "https://media.example.cn/partner", "模型和云厂商联合方案。", tier="media"),
                ],
                budget_signals=["推理算力租赁预算待确认"],
                departments=["技术平台部"],
                competitors=["云厂商 A"],
                partners=["模型厂商"],
                readiness_status="degraded",
            ),
        ),
        (
            "weak-generic",
            "generic",
            _golden_base_report(
                keyword="某行业平台机会",
                title="某行业平台机会初筛",
                focus="泛泛判断行业机会。",
                summary="行业可能有机会，但缺少账户、预算和官方来源支撑。",
                angle="先作为线索池待补证。",
                target_accounts=["某客户"],
                supported_targets=[],
                unsupported_targets=["某客户"],
                sections=[
                    _golden_section("行业资讯判断", ["市场可能增长。"], official_count=0, passed=False),
                    _golden_section("项目与商机判断", ["可能有项目。"], official_count=0, passed=False),
                ],
                sources=[
                    _golden_source("行业观点文章", "https://media.example.cn/market", "泛行业趋势。", tier="media"),
                ],
                budget_signals=[],
                departments=[],
                competitors=[],
                partners=[],
                readiness_status="needs_evidence",
            ),
        ),
    ]


def _case_rates(report: ResearchReportResponse) -> tuple[float, float]:
    supported = len(report.source_diagnostics.supported_target_accounts)
    unsupported = len(report.source_diagnostics.unsupported_target_accounts)
    target_support_rate = _safe_rate(supported, supported + unsupported)
    quota_sections = _quota_sections(report)
    section_quota_pass_rate = _safe_rate(
        sum(1 for section in quota_sections if bool(getattr(section, "meets_evidence_quota", False))),
        len(quota_sections),
    )
    return target_support_rate, section_quota_pass_rate


def build_golden_research_evaluation() -> ResearchGoldenEvaluationOut:
    cases: list[ResearchGoldenEvaluationCaseOut] = []
    for case_id, expected_methodology, report in _golden_reports():
        profile = build_research_quality_profile(report)
        target_support_rate, section_quota_pass_rate = _case_rates(report)
        issues: list[str] = []
        if profile.methodology.industry_key != expected_methodology:
            issues.append(f"方法论识别偏离：期望 {expected_methodology}，实际 {profile.methodology.industry_key}")
        if profile.professional_score < 70:
            issues.append("专业度低于 70 分")
        if profile.intelligence_value_score < 62:
            issues.append("情报价值低于 62 分")
        if target_support_rate < 0.5:
            issues.append("目标账户支撑率低于 50%")
        if section_quota_pass_rate < 0.5:
            issues.append("章节证据配额通过率低于 50%")
        if case_id == "weak-generic":
            passed = bool(issues)
            if not issues:
                issues.append("弱样本未被识别为失败样本")
        else:
            passed = not issues
        cases.append(
            ResearchGoldenEvaluationCaseOut(
                case_id=case_id,
                title=report.report_title,
                expected_methodology=expected_methodology,
                professional_score=profile.professional_score,
                intelligence_value_score=profile.intelligence_value_score,
                target_support_rate=target_support_rate,
                section_quota_pass_rate=section_quota_pass_rate,
                passed=passed,
                issues=issues,
            )
        )
    passed_cases = sum(1 for case in cases if case.passed)
    avg_professional = round(sum(case.professional_score for case in cases) / max(len(cases), 1))
    avg_intelligence = round(sum(case.intelligence_value_score for case in cases) / max(len(cases), 1))
    avg_target_support = sum(case.target_support_rate for case in cases) / max(len(cases), 1)
    avg_quota = sum(case.section_quota_pass_rate for case in cases) / max(len(cases), 1)
    return ResearchGoldenEvaluationOut(
        generated_at=datetime.now(timezone.utc),
        total_cases=len(cases),
        passed_cases=passed_cases,
        average_professional_score=avg_professional,
        average_intelligence_value_score=avg_intelligence,
        average_target_support_rate=round(avg_target_support, 4),
        average_section_quota_pass_rate=round(avg_quota, 4),
        cases=cases,
        summary_lines=[
            f"Golden 样本 {passed_cases}/{len(cases)} 通过。",
            f"平均专业度 {avg_professional}，平均情报价值 {avg_intelligence}。",
            f"平均目标账户支撑率 {round(avg_target_support * 100)}%，章节证据配额通过率 {round(avg_quota * 100)}%。",
        ],
    )


def build_offline_research_evaluation(
    db: Session,
    *,
    weakest_limit: int = 6,
) -> ResearchOfflineEvaluationOut:
    settings = get_settings()
    entries = db.scalars(
        select(KnowledgeEntry)
        .where(KnowledgeEntry.user_id == settings.single_user_id)
        .where(KnowledgeEntry.source_domain == "research.report")
        .order_by(desc(KnowledgeEntry.updated_at), desc(KnowledgeEntry.created_at))
    ).all()

    reports: list[tuple[KnowledgeEntry, ResearchReportResponse]] = []
    invalid_payloads = 0
    for entry in entries:
        report = _parse_stored_report(entry)
        if report is None:
            invalid_payloads += 1
            continue
        reports.append((entry, report))

    retrieval_hits = 0
    supported_target_total = 0
    total_target_total = 0
    passed_quota_sections = 0
    total_quota_sections = 0
    official_recall_hits = 0
    official_recall_total = 0
    reranker_official_recall_hits = 0
    reranker_official_recall_total = 0
    unsupported_target_total = 0
    solution_delivery_quality_passed = 0
    project_proposal_quality_passed = 0
    delivery_quality_total = 0
    delivery_self_review_triggered = 0
    delivery_self_review_gained = 0
    weak_reports: list[ResearchOfflineEvaluationWeakReportOut] = []
    settings = get_settings()

    for entry, report in reports:
        retrieval_hit = _report_retrieval_hit(report)
        if retrieval_hit:
            retrieval_hits += 1

        supported_targets = _supported_target_accounts(report)
        unsupported_targets = _unsupported_target_accounts(report)
        supported_target_total += len(supported_targets)
        total_target_total += len(supported_targets) + len(unsupported_targets)
        unsupported_target_total += len(unsupported_targets)
        solution_profile, proposal_profile = _delivery_profiles_for_evaluation(report)
        delivery_quality_total += 1
        if solution_profile.status == "pass":
            solution_delivery_quality_passed += 1
        if proposal_profile.status == "pass":
            project_proposal_quality_passed += 1
        self_reviews = [solution_profile.self_review, proposal_profile.self_review]
        if any(review.triggered for review in self_reviews):
            delivery_self_review_triggered += 1
            if any(review.triggered and review.after_score >= review.before_score for review in self_reviews):
                delivery_self_review_gained += 1
        if any(_source_is_official(source) for source in report.sources):
            official_recall_total += 1
            if _has_official_source_at_k(report.sources, k=5):
                official_recall_hits += 1
            if len(report.sources) > 1:
                reranked_sources, _profile = rerank_sources_cross_encoder(
                    report.sources,
                    query=" ".join(
                        item
                        for item in [report.keyword, report.research_focus or "", *report.target_accounts[:3]]
                        if normalize_text(item)
                    ),
                    model_name=settings.research_cross_encoder_model,
                    top_k=min(settings.research_cross_encoder_top_k, 20),
                    backend="local",
                )
                reranker_official_recall_total += 1
                if _has_official_source_at_k(reranked_sources, k=5):  # type: ignore[arg-type]
                    reranker_official_recall_hits += 1

        quota_sections = _quota_sections(report)
        total_quota_sections += len(quota_sections)
        quota_passed_count = sum(1 for section in quota_sections if bool(getattr(section, "meets_evidence_quota", False)))
        passed_quota_sections += quota_passed_count
        failing_sections = [
            normalize_text(str(getattr(section, "title", "") or "")) or "关键章节"
            for section in quota_sections
            if not bool(getattr(section, "meets_evidence_quota", False))
        ]

        weakness_score = _weakness_score(
            report,
            solution_profile=solution_profile,
            proposal_profile=proposal_profile,
        )
        if weakness_score <= 0:
            continue
        weak_reports.append(
            ResearchOfflineEvaluationWeakReportOut(
                entry_id=str(entry.id),
                entry_title=normalize_text(entry.title or "") or normalize_text(report.report_title or "") or "知识卡片",
                report_title=normalize_text(report.report_title or ""),
                keyword=normalize_text(report.keyword or ""),
                weakness_score=weakness_score,
                retrieval_hit=retrieval_hit,
                supported_target_accounts=len(supported_targets),
                unsupported_target_accounts=len(unsupported_targets),
                unsupported_targets=unsupported_targets[:3],
                quota_passed_section_count=quota_passed_count,
                quota_total_section_count=len(quota_sections),
                failing_sections=failing_sections[:3],
                official_source_ratio=float(report.source_diagnostics.official_source_ratio or 0.0),
                strict_match_ratio=float(report.source_diagnostics.strict_match_ratio or 0.0),
                retrieval_quality=report.source_diagnostics.retrieval_quality,
                solution_delivery_quality_score=int(solution_profile.overall_score or 0),
                project_proposal_quality_score=int(proposal_profile.overall_score or 0),
                delivery_quality_status=_worst_delivery_status(solution_profile, proposal_profile),  # type: ignore[arg-type]
                delivery_missing_axes=list(proposal_profile.missing_axes[:4]),
            )
        )

    retrieval_hit_rate = _safe_rate(retrieval_hits, len(reports))
    target_support_rate = _safe_rate(supported_target_total, total_target_total)
    section_quota_pass_rate = _safe_rate(passed_quota_sections, total_quota_sections)
    official_source_recall_at_5 = _safe_rate(official_recall_hits, official_recall_total)
    reranker_official_recall_at_5 = _safe_rate(reranker_official_recall_hits, reranker_official_recall_total)
    unsupported_target_rate = _safe_rate(unsupported_target_total, total_target_total)
    solution_delivery_quality_pass_rate = _safe_rate(solution_delivery_quality_passed, delivery_quality_total)
    project_proposal_quality_pass_rate = _safe_rate(project_proposal_quality_passed, delivery_quality_total)
    delivery_self_review_gain_rate = _safe_rate(delivery_self_review_gained, delivery_self_review_triggered)
    delivery_self_review_gain_status = (
        "watch"
        if delivery_self_review_triggered <= 0
        else _metric_status(
            delivery_self_review_gain_rate,
            benchmark=_METRIC_BENCHMARKS["delivery_self_review_gain_rate"],
        )
    )

    metrics = [
        ResearchOfflineEvaluationMetricOut(
            key="retrieval_hit_rate",
            label="检索命中率",
            numerator=retrieval_hits,
            denominator=len(reports),
            rate=retrieval_hit_rate,
            percent=_percent(retrieval_hit_rate),
            benchmark=_METRIC_BENCHMARKS["retrieval_hit_rate"],
            status=_metric_status(retrieval_hit_rate, benchmark=_METRIC_BENCHMARKS["retrieval_hit_rate"]),
            summary="按研报口径统计：严格主题命中且检索质量不低于中档的比例。",
        ),
        ResearchOfflineEvaluationMetricOut(
            key="target_support_rate",
            label="目标账户支撑率",
            numerator=supported_target_total,
            denominator=total_target_total,
            rate=target_support_rate,
            percent=_percent(target_support_rate),
            benchmark=_METRIC_BENCHMARKS["target_support_rate"],
            status=_metric_status(target_support_rate, benchmark=_METRIC_BENCHMARKS["target_support_rate"]),
            summary="按账户口径统计：研报中被保留的目标账户里，有来源直接支撑的占比。",
        ),
        ResearchOfflineEvaluationMetricOut(
            key="section_quota_pass_rate",
            label="章节证据配额通过率",
            numerator=passed_quota_sections,
            denominator=total_quota_sections,
            rate=section_quota_pass_rate,
            percent=_percent(section_quota_pass_rate),
            benchmark=_METRIC_BENCHMARKS["section_quota_pass_rate"],
            status=_metric_status(section_quota_pass_rate, benchmark=_METRIC_BENCHMARKS["section_quota_pass_rate"]),
            summary="按章节口径统计：带 evidence_quota 的章节中，已满足配额的比例。",
        ),
        ResearchOfflineEvaluationMetricOut(
            key="official_source_recall_at_5",
            label="官方源 Recall@5",
            numerator=official_recall_hits,
            denominator=official_recall_total,
            rate=official_source_recall_at_5,
            percent=_percent(official_source_recall_at_5),
            benchmark=_METRIC_BENCHMARKS["official_source_recall_at_5"],
            status=_metric_status(
                official_source_recall_at_5,
                benchmark=_METRIC_BENCHMARKS["official_source_recall_at_5"],
            ),
            summary="按研报口径统计：存在官方源的样本里，前 5 个来源能召回至少一个官方源的比例。",
        ),
        ResearchOfflineEvaluationMetricOut(
            key="unsupported_target_rate",
            label="未支撑目标账户率",
            numerator=unsupported_target_total,
            denominator=total_target_total,
            rate=unsupported_target_rate,
            percent=_percent(unsupported_target_rate),
            benchmark=_METRIC_BENCHMARKS["unsupported_target_rate"],
            status=_inverse_metric_status(
                unsupported_target_rate,
                benchmark=_METRIC_BENCHMARKS["unsupported_target_rate"],
            ),
            summary="按账户口径统计：目标账户中仍缺少来源直接支撑的占比，数值越低越好。",
        ),
        ResearchOfflineEvaluationMetricOut(
            key="reranker_official_recall_at_5",
            label="Reranker 官方源 Recall@5",
            numerator=reranker_official_recall_hits,
            denominator=reranker_official_recall_total,
            rate=reranker_official_recall_at_5,
            percent=_percent(reranker_official_recall_at_5),
            benchmark=_METRIC_BENCHMARKS["reranker_official_recall_at_5"],
            status=_metric_status(
                reranker_official_recall_at_5,
                benchmark=_METRIC_BENCHMARKS["reranker_official_recall_at_5"],
            ),
            summary="按研报口径统计：离线样本经 reranker 复排后，前 5 个来源召回至少一个官方源的比例。",
        ),
        ResearchOfflineEvaluationMetricOut(
            key="solution_delivery_quality_pass_rate",
            label="解决方案交付质量通过率",
            numerator=solution_delivery_quality_passed,
            denominator=delivery_quality_total,
            rate=solution_delivery_quality_pass_rate,
            percent=_percent(solution_delivery_quality_pass_rate),
            benchmark=_METRIC_BENCHMARKS["solution_delivery_quality_pass_rate"],
            status=_metric_status(
                solution_delivery_quality_pass_rate,
                benchmark=_METRIC_BENCHMARKS["solution_delivery_quality_pass_rate"],
            ),
            summary="按研报口径统计：解决方案交付包完成中国科技项目交付质量自审并达到 pass 的比例。",
        ),
        ResearchOfflineEvaluationMetricOut(
            key="project_proposal_quality_pass_rate",
            label="项目建议书质量通过率",
            numerator=project_proposal_quality_passed,
            denominator=delivery_quality_total,
            rate=project_proposal_quality_pass_rate,
            percent=_percent(project_proposal_quality_pass_rate),
            benchmark=_METRIC_BENCHMARKS["project_proposal_quality_pass_rate"],
            status=_metric_status(
                project_proposal_quality_pass_rate,
                benchmark=_METRIC_BENCHMARKS["project_proposal_quality_pass_rate"],
            ),
            summary="按研报口径统计：项目建议书交付质量画像达到 pass 的比例。",
        ),
        ResearchOfflineEvaluationMetricOut(
            key="delivery_self_review_gain_rate",
            label="交付自修订增益率",
            numerator=delivery_self_review_gained,
            denominator=delivery_self_review_triggered,
            rate=delivery_self_review_gain_rate,
            percent=_percent(delivery_self_review_gain_rate),
            benchmark=_METRIC_BENCHMARKS["delivery_self_review_gain_rate"],
            status=delivery_self_review_gain_status,  # type: ignore[arg-type]
            summary=(
                "当前暂无触发交付自修订的存量样本；该指标将在 watch/fail 交付件补缺后累计。"
                if delivery_self_review_triggered <= 0
                else "按触发自修订的样本统计：结构化补缺后质量分数不回退的比例。"
            ),
        ),
    ]

    weak_reports.sort(
        key=lambda item: (
            item.weakness_score,
            item.unsupported_target_accounts,
            item.quota_total_section_count - item.quota_passed_section_count,
            1.0 - item.official_source_ratio,
        ),
        reverse=True,
    )

    summary_lines = [
        f"已扫描 {len(entries)} 份存量研报，其中可评估 {len(reports)} 份。",
        (
            f"当前检索命中率 {_percent(retrieval_hit_rate)}%，目标账户支撑率 {_percent(target_support_rate)}%，"
            f"章节证据配额通过率 {_percent(section_quota_pass_rate)}%，官方源 Recall@5 {_percent(official_source_recall_at_5)}%，"
            f"Reranker 官方源 Recall@5 {_percent(reranker_official_recall_at_5)}%。"
        ),
        (
            f"解决方案交付质量通过率 {_percent(solution_delivery_quality_pass_rate)}%，"
            f"项目建议书质量通过率 {_percent(project_proposal_quality_pass_rate)}%，"
            f"交付自修订增益率 {_percent(delivery_self_review_gain_rate)}%。"
        ),
    ]
    if weak_reports:
        sample = weak_reports[0]
        summary_lines.append(
            f"当前最需要优先回归的样本是《{sample.report_title or sample.entry_title}》，主要问题集中在"
            f"{'检索命中' if not sample.retrieval_hit else '目标账户支撑/章节配额'}。"
        )

    return ResearchOfflineEvaluationOut(
        generated_at=datetime.now(timezone.utc),
        total_reports=len(entries),
        evaluated_reports=len(reports),
        invalid_payloads=invalid_payloads,
        metrics=metrics,
        weakest_reports=weak_reports[: max(1, min(weakest_limit, 12))],
        summary_lines=summary_lines,
    )
