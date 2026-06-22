from __future__ import annotations

from collections.abc import Iterable, Sequence

from app.schemas.research import (
    ResearchDeliveryEvidenceLedgerOut,
    ResearchDeliveryQualityMetricOut,
    ResearchDeliveryQualityProfileOut,
    ResearchDeliverySelfReviewOut,
    ResearchEntityEvidenceOut,
    ResearchSolutionDeliveryPackOut,
    ResearchSolutionOutlineSectionOut,
)
from app.services.content_extractor import normalize_text
from app.services.research.delivery_evidence_ledger import build_delivery_evidence_ledger
from app.services.research.delivery_semantic_challenger import build_delivery_semantic_challenge
from app.services.research.delivery_semantic_quality import audit_delivery_semantics

OutlineSection = ResearchSolutionOutlineSectionOut
FormalSection = tuple[str, list[str]]

_STATUS_PASS = 84
_STATUS_WATCH = 68

_AXIS_LABELS: dict[str, str] = {
    "basis": "立项背景与编制依据",
    "current_state": "现状差距与需求分析",
    "objectives": "建设目标与建设内容",
    "alternatives": "方案比选与推荐理由",
    "solution_architecture": "技术方案、系统边界与接口",
    "security_compliance": "网络安全、数据安全、信创/密码要求",
    "operations": "运营方案、组织机制与持续改进",
    "procurement_delivery": "采购方案、实施组织与交付边界",
    "budget_value": "投资测算、绩效目标与综合效益",
    "effects": "经济、社会、生态与安全影响",
    "evidence_traceability": "证据矩阵、假设台账与可追溯性",
    "risk_validation": "风险控制、验收与待核验项",
}

_AXIS_TERMS: dict[str, tuple[str, ...]] = {
    "basis": ("背景", "依据", "政策", "规划", "项目概况", "立项"),
    "current_state": ("现状", "差距", "需求", "问题", "业务流程", "业务量"),
    "objectives": ("目标", "建设内容", "范围", "任务", "组件", "功能"),
    "alternatives": ("方案比选", "备选方案", "推荐方案", "不建设", "分期建设"),
    "solution_architecture": ("技术方案", "总体架构", "接口", "系统边界", "数据共享", "应用系统", "基础设施"),
    "security_compliance": ("安全", "信创", "密码", "等保", "数据安全", "网络安全", "合规"),
    "operations": ("运营", "运维", "组织机制", "持续改进", "服务保障"),
    "procurement_delivery": ("采购", "实施", "进度", "组织", "里程碑", "交付", "验收", "招标"),
    "budget_value": ("投资", "预算", "资金", "绩效", "效益", "投入产出", "估算"),
    "effects": ("经济影响", "社会影响", "生态", "资源能源", "安全影响", "综合效益"),
    "evidence_traceability": ("证据矩阵", "证据索引", "假设台账", "来源追溯", "可追溯"),
    "risk_validation": ("风险", "待核验", "边界", "审查", "验收", "限制", "结论"),
}

_REQUIRED_AXES: dict[str, tuple[str, ...]] = {
    "solution_delivery": (
        "current_state",
        "objectives",
        "alternatives",
        "solution_architecture",
        "security_compliance",
        "operations",
        "procurement_delivery",
        "budget_value",
        "effects",
        "evidence_traceability",
        "risk_validation",
    ),
    "project_proposal": (
        "basis",
        "current_state",
        "objectives",
        "alternatives",
        "solution_architecture",
        "security_compliance",
        "operations",
        "procurement_delivery",
        "budget_value",
        "effects",
        "evidence_traceability",
        "risk_validation",
    ),
    "feasibility_study": (
        "basis",
        "current_state",
        "objectives",
        "alternatives",
        "solution_architecture",
        "security_compliance",
        "operations",
        "procurement_delivery",
        "budget_value",
        "effects",
        "evidence_traceability",
        "risk_validation",
    ),
}


def _dedupe_strings(values: Iterable[object], limit: int = 10) -> list[str]:
    rows: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = normalize_text(str(value or ""))
        if not text or text in seen:
            continue
        rows.append(text)
        seen.add(text)
        if len(rows) >= limit:
            break
    return rows


def _status(score: int) -> str:
    if score >= _STATUS_PASS:
        return "pass"
    if score >= _STATUS_WATCH:
        return "watch"
    return "fail"


def _metric_status(score: int, *, threshold: int = 75) -> str:
    if score >= threshold:
        return "pass"
    if score >= max(0, threshold - 14):
        return "watch"
    return "fail"


def _outline_text(sections: Sequence[OutlineSection]) -> str:
    return normalize_text(
        " ".join(
            [
                *[section.title for section in sections],
                *[bullet for section in sections for bullet in section.bullets],
            ]
        )
    )


def _outline_rows(sections: Sequence[OutlineSection]) -> list[str]:
    return [
        row
        for section in sections
        for row in [section.title, *section.bullets]
        if normalize_text(row)
    ]


def _outline_claim_rows(sections: Sequence[OutlineSection]) -> list[tuple[str, str]]:
    return [
        (section.title, bullet)
        for section in sections
        for bullet in section.bullets
        if normalize_text(bullet)
    ]


def _formal_text(sections: Sequence[FormalSection]) -> str:
    return normalize_text(" ".join([*[title for title, _rows in sections], *[row for _title, rows in sections for row in rows]]))


def _formal_rows(sections: Sequence[FormalSection]) -> list[str]:
    return [
        row
        for title, rows in sections
        for row in [title, *rows]
        if normalize_text(row)
    ]


def _formal_claim_rows(sections: Sequence[FormalSection]) -> list[tuple[str, str]]:
    return [
        (title, row)
        for title, rows in sections
        for row in rows
        if normalize_text(row)
    ]


def _present_axes(text: str, required_axes: Sequence[str]) -> list[str]:
    lowered = text.lower()
    rows: list[str] = []
    for axis in required_axes:
        terms = _AXIS_TERMS[axis]
        if any(term.lower() in lowered for term in terms):
            rows.append(axis)
    return rows


def _axis_labels(axes: Iterable[str]) -> list[str]:
    return [_AXIS_LABELS.get(axis, axis) for axis in axes]


def _metric(
    *,
    key: str,
    label: str,
    score: int,
    summary: str,
    gaps: Iterable[object],
    actions: Iterable[object],
    threshold: int = 75,
) -> ResearchDeliveryQualityMetricOut:
    return ResearchDeliveryQualityMetricOut(
        key=key,
        label=label,
        score=max(0, min(int(score), 100)),
        threshold=threshold,
        status=_metric_status(score, threshold=threshold),  # type: ignore[arg-type]
        summary=summary,
        gaps=_dedupe_strings(gaps, limit=6),
        improvement_actions=_dedupe_strings(actions, limit=6),
    )


def _quality_profile(
    *,
    review_target: str,
    text: str,
    source_support_score: int,
    grounded_count: int,
    checklist_count: int,
    advisory_count: int = 0,
    next_step_count: int = 0,
    evidence_note_count: int = 0,
    semantic_rows: Sequence[str] | None = None,
    challenge_rows: Sequence[tuple[str, str]] | None = None,
    evidence_ledger: ResearchDeliveryEvidenceLedgerOut | None = None,
    expected_scope_terms: Sequence[str] = (),
    expected_entities: Sequence[str] = (),
) -> ResearchDeliveryQualityProfileOut:
    required_axes = list(_REQUIRED_AXES.get(review_target, _REQUIRED_AXES["solution_delivery"]))
    present_axes = _present_axes(text, required_axes)
    missing_axes = [axis for axis in required_axes if axis not in present_axes]
    structure_score = round(100 * len(present_axes) / max(len(required_axes), 1))
    evidence_score = min(
        100,
        max(0, int(source_support_score or 0))
        + min(18, grounded_count * 4)
        + min(12, evidence_note_count * 3),
    )
    execution_score = min(
        100,
        42 + min(18, checklist_count * 3) + min(18, next_step_count * 4) + min(22, advisory_count * 6),
    )
    review_control_score = min(
        100,
        40 + min(24, checklist_count * 4) + min(18, grounded_count * 4) + min(18, evidence_note_count * 4),
    )
    semantic_audit = audit_delivery_semantics(
        semantic_rows or [text],
        source_support_score=source_support_score,
        grounded_count=grounded_count,
        evidence_note_count=evidence_note_count,
    )
    resolved_ledger = evidence_ledger or ResearchDeliveryEvidenceLedgerOut()
    ledger_traceability_score = (
        round(
            resolved_ledger.claim_coverage_percent * 0.35
            + resolved_ledger.high_confidence_coverage_percent * 0.65
        )
        if resolved_ledger.claim_count
        else semantic_audit.traceability_score
    )
    consistency_score = min(
        int(resolved_ledger.entity_consistency_score or 0),
        int(resolved_ledger.numeric_consistency_score or 0),
    )
    semantic_challenge = build_delivery_semantic_challenge(
        challenge_rows
        or [(review_target, row) for row in (semantic_rows or [text]) if normalize_text(row)],
        evidence_ledger=resolved_ledger,
        expected_scope_terms=expected_scope_terms,
        expected_entities=expected_entities,
        document_kind=review_target,
    )
    metrics = [
        _metric(
            key="structure_completeness",
            label="结构完整度",
            score=structure_score,
            summary=f"已覆盖 {len(present_axes)}/{len(required_axes)} 个中国科技项目交付审查轴。",
            gaps=[f"缺少：{label}" for label in _axis_labels(missing_axes)],
            actions=["补齐缺失章节，尤其是安全合规、预算绩效、风险验收和采购实施口径。"],
        ),
        _metric(
            key="evidence_grounding",
            label="证据与依据",
            score=evidence_score,
            summary=f"来源支撑 {source_support_score}/100，生成前核验项 {grounded_count} 个。",
            gaps=["来源支撑不足时，确定性判断不得直接进入外发材料。"] if evidence_score < 75 else [],
            actions=["继续补官方文件、采购公告、预算/绩效依据和公开技术参数。"],
        ),
        _metric(
            key="delivery_actionability",
            label="交付可执行性",
            score=execution_score,
            summary=f"审阅清单 {checklist_count} 项、下一步 {next_step_count} 项、交付产物 {advisory_count} 类。",
            gaps=["缺少可下发的里程碑、材料清单或责任边界。"] if execution_score < 75 else [],
            actions=["把方案主张转成阶段目标、采购/实施边界、验收动作和责任拆解。"],
        ),
        _metric(
            key="review_governance",
            label="自审与风险治理",
            score=review_control_score,
            summary="检查材料是否主动暴露证据边界、风险和待核验项。",
            gaps=["需要明确哪些判断仅为内部假设，哪些可进入客户版。"] if review_control_score < 75 else [],
            actions=["保留审查结论、待核验项和降级说明，禁止用 polished wording 掩盖证据缺口。"],
        ),
        _metric(
            key="content_hygiene",
            label="内容卫生与正文纯度",
            score=semantic_audit.content_hygiene_score,
            summary=(
                f"发现 {len(semantic_audit.noise_rows)} 条疑似网页导航、来源转储或模板污染内容。"
                if semantic_audit.noise_rows
                else "未发现明显网页导航、来源转储或模板污染内容。"
            ),
            gaps=[f"疑似污染：{row}" for row in semantic_audit.noise_rows],
            actions=["在进入正式文档前移除网页导航、页脚、登录提示、来源转储和无关页面片段。"],
            threshold=90,
        ),
        _metric(
            key="claim_evidence_traceability",
            label="主张—证据可追溯性",
            score=ledger_traceability_score,
            summary=(
                f"稳定主张 {resolved_ledger.claim_count} 条，证据锚点 {resolved_ledger.evidence_count} 个；"
                f"总体覆盖 {resolved_ledger.claim_coverage_percent}%，"
                f"高置信主张覆盖 {resolved_ledger.high_confidence_coverage_percent}%。"
                if resolved_ledger.claim_count
                else (
                    f"识别强主张 {len(semantic_audit.strong_claim_rows)} 条，"
                    f"可追溯锚点 {semantic_audit.traceable_anchor_count} 个，"
                    f"未绑定证据的强主张 {len(semantic_audit.untraceable_claim_rows)} 条。"
                )
            ),
            gaps=[
                *[
                    f"强主张缺少来源锚点：{claim.text}"
                    for claim in resolved_ledger.claims
                    if claim.confidence == "high" and claim.verification_status != "supported"
                ][:4],
                *[f"强主张缺少来源锚点：{row}" for row in semantic_audit.untraceable_claim_rows][
                    : 0 if resolved_ledger.claim_count else 4
                ],
                "只有章节名称或“证据矩阵”占位，尚未形成逐主张来源绑定。"
                if (
                    resolved_ledger.evidence_count <= 0
                    if resolved_ledger.claim_count
                    else semantic_audit.traceable_anchor_count <= 0
                )
                else "",
            ],
            actions=[
                "为预算、金额、比例、工期、收益和推荐结论绑定 URL、文件名/文号、项目编号或稳定 chunk/source ID。",
                "证据不足的数字和结论必须降级为假设，并记录验证责任人与放行条件。",
            ],
            threshold=75,
        ),
        _metric(
            key="entity_numeric_consistency",
            label="实体与数字口径一致性",
            score=consistency_score,
            summary=(
                f"实体一致性 {resolved_ledger.entity_consistency_score}/100，"
                f"数字一致性 {resolved_ledger.numeric_consistency_score}/100，"
                f"发现 {len(resolved_ledger.consistency_issues)} 个一致性问题。"
            ),
            gaps=[
                f"{issue.summary} {'；'.join(issue.details[:2])}"
                for issue in resolved_ledger.consistency_issues[:5]
            ],
            actions=[
                "统一目标客户、采购人、建设单位和中标主体名称，冲突主体进入人工确认。",
                "金额统一换算为人民币元，周期统一换算为月，比例统一为 ratio 后再比较。",
            ],
            threshold=85,
        ),
        _metric(
            key="semantic_challenger",
            label="语义挑战者",
            score=semantic_challenge.overall_score,
            summary=(
                f"挑战者状态 {semantic_challenge.status}；问题 {semantic_challenge.issue_count} 个，"
                f"高严重度 {semantic_challenge.high_severity_count} 个，"
                f"范围漂移 {semantic_challenge.scope_drift_count} 个，"
                f"跨章节冲突 {semantic_challenge.cross_section_conflict_count} 个。"
            ),
            gaps=[
                f"{issue.severity} / {issue.issue_type}: {issue.summary}"
                for issue in semantic_challenge.issues[:6]
            ],
            actions=semantic_challenge.recommended_actions,
            threshold=84,
        ),
    ]
    overall = round(
        metrics[0].score * 0.16
        + metrics[1].score * 0.14
        + metrics[2].score * 0.12
        + metrics[3].score * 0.08
        + metrics[4].score * 0.13
        + metrics[5].score * 0.15
        + metrics[6].score * 0.10
        + metrics[7].score * 0.12
    )
    overall = min(overall, semantic_audit.hard_score_cap)
    if semantic_challenge.status == "fail":
        overall = min(overall, 67)
    elif semantic_challenge.status == "watch":
        overall = min(overall, 83)
    if resolved_ledger.claim_count and resolved_ledger.high_confidence_coverage_percent < 90:
        overall = min(overall, 83)
    if any(issue.severity == "high" for issue in resolved_ledger.consistency_issues):
        overall = min(overall, 67)
    strengths = _dedupe_strings(
        [
            "材料骨架已覆盖主要审查轴。" if not missing_axes else "",
            "来源支撑、核验动作和后续补证可以在交付前同步查看。" if evidence_score >= 75 else "",
            "交付物已从研究结论延伸到可执行材料链。" if advisory_count >= 3 else "",
        ],
        limit=5,
    )
    gaps = _dedupe_strings(
        [
            *[f"待补审查轴：{label}" for label in _axis_labels(missing_axes)],
            "当前证据支撑不宜直接形成强承诺。" if evidence_score < 75 else "",
            "实施、责任和验收动作仍需进一步显式化。" if execution_score < 75 else "",
            "检测到网页导航、来源转储或模板污染，正式交付必须阻断。"
            if semantic_audit.noise_rows
            else "",
            "主张—证据尚未逐条绑定，综合分被限制在 pass 阈值以下。"
            if ledger_traceability_score < 75
            else "",
            "实体或数字口径存在高严重度冲突，正式交付必须阻断。"
            if any(issue.severity == "high" for issue in resolved_ledger.consistency_issues)
            else "",
            "语义挑战者发现范围漂移、跨章节冲突或黄金样本对齐不足，正式交付必须先修订。"
            if semantic_challenge.status == "fail"
            else "",
        ],
        limit=8,
    )
    return ResearchDeliveryQualityProfileOut(
        review_target=review_target,  # type: ignore[arg-type]
        overall_score=overall,
        status=_status(overall),  # type: ignore[arg-type]
        metrics=metrics,
        strengths=strengths,
        gaps=gaps,
        required_axes=_axis_labels(required_axes),
        missing_axes=_axis_labels(missing_axes),
        evidence_ledger=resolved_ledger,
        semantic_challenge=semantic_challenge,
    )


def build_solution_delivery_quality_profiles(
    pack: ResearchSolutionDeliveryPackOut,
    *,
    evidence_links: Sequence[ResearchEntityEvidenceOut] = (),
    expected_entities: Sequence[str] = (),
) -> tuple[ResearchDeliveryQualityProfileOut, ResearchDeliveryQualityProfileOut]:
    solution_text = _outline_text(
        [
            *pack.feasibility_outline,
            *pack.project_proposal_outline,
            *pack.client_ppt_outline,
        ]
    )
    proposal_text = _outline_text(pack.project_proposal_outline)
    shared_semantic_rows = [
        *pack.intelligence_summary,
        *pack.grounding_checks,
        *[artifact.title for artifact in pack.advisory_artifacts],
        *[artifact.markdown for artifact in pack.advisory_artifacts],
    ]
    expected_scope_terms = _dedupe_strings(
        [
            pack.scenario,
            pack.target_customer,
            pack.vertical_scene,
            *expected_entities,
        ],
        limit=10,
    )
    full_challenge_rows = [
        *_outline_claim_rows(pack.feasibility_outline),
        *_outline_claim_rows(pack.project_proposal_outline),
        *_outline_claim_rows(pack.client_ppt_outline),
        *[("交付情报摘要", row) for row in shared_semantic_rows],
    ]
    proposal_challenge_rows = [
        *_outline_claim_rows(pack.project_proposal_outline),
        *[("交付情报摘要", row) for row in shared_semantic_rows],
    ]
    full_ledger = build_delivery_evidence_ledger(
        [
            *_outline_claim_rows(pack.feasibility_outline),
            *_outline_claim_rows(pack.project_proposal_outline),
            *_outline_claim_rows(pack.client_ppt_outline),
        ],
        evidence_links=evidence_links,
        expected_entities=expected_entities,
    )
    proposal_ledger = build_delivery_evidence_ledger(
        _outline_claim_rows(pack.project_proposal_outline),
        evidence_links=evidence_links,
        expected_entities=expected_entities,
    )
    solution_profile = _quality_profile(
        review_target="solution_delivery",
        text=solution_text,
        source_support_score=pack.source_support_score,
        grounded_count=len(pack.grounding_checks),
        checklist_count=len(pack.review_checklist),
        advisory_count=len(pack.advisory_artifacts),
        next_step_count=len(pack.next_steps),
        evidence_note_count=len(pack.intelligence_summary),
        semantic_rows=[
            *_outline_rows(pack.feasibility_outline),
            *_outline_rows(pack.project_proposal_outline),
            *_outline_rows(pack.client_ppt_outline),
            *shared_semantic_rows,
        ],
        challenge_rows=full_challenge_rows,
        evidence_ledger=full_ledger,
        expected_scope_terms=expected_scope_terms,
        expected_entities=expected_entities,
    )
    proposal_profile = _quality_profile(
        review_target="project_proposal",
        text=proposal_text,
        source_support_score=pack.source_support_score,
        grounded_count=len(pack.grounding_checks),
        checklist_count=len(pack.review_checklist),
        advisory_count=0,
        next_step_count=len(pack.next_steps),
        evidence_note_count=len(pack.intelligence_summary),
        semantic_rows=[
            *_outline_rows(pack.project_proposal_outline),
            *shared_semantic_rows,
        ],
        challenge_rows=proposal_challenge_rows,
        evidence_ledger=proposal_ledger,
        expected_scope_terms=expected_scope_terms,
        expected_entities=expected_entities,
    )
    return solution_profile, proposal_profile


def _append_outline_section(
    sections: list[OutlineSection],
    *,
    title: str,
    bullets: Iterable[object],
) -> tuple[list[OutlineSection], str | None]:
    normalized_title = normalize_text(title)
    if any(normalize_text(section.title) == normalized_title for section in sections):
        return sections, None
    return [*sections, OutlineSection(title=title, bullets=_dedupe_strings(bullets, limit=8))], normalized_title


def review_and_improve_solution_delivery_pack(
    pack: ResearchSolutionDeliveryPackOut,
    *,
    evidence_links: Sequence[ResearchEntityEvidenceOut] = (),
    expected_entities: Sequence[str] = (),
) -> ResearchSolutionDeliveryPackOut:
    before_solution, before_proposal = build_solution_delivery_quality_profiles(
        pack,
        evidence_links=evidence_links,
        expected_entities=expected_entities,
    )
    project_sections = list(pack.project_proposal_outline)
    feasibility_sections = list(pack.feasibility_outline)
    client_ppt_sections = list(pack.client_ppt_outline)
    added_sections: list[str] = []
    actions: list[str] = []

    if "现状差距与需求分析" in before_proposal.missing_axes:
        project_sections, added = _append_outline_section(
            project_sections,
            title="二、现状差距与需求分析",
            bullets=[
                "说明现有业务流程、系统存量、能力缺口和本次建设的必要性。",
                "把业务问题、数据问题、协同问题拆开描述，避免只写愿景口号。",
            ],
        )
        if added:
            added_sections.append(added)
            actions.append("补入项目建议书现状差距与需求分析。")
    if "技术方案、系统边界与接口" in before_proposal.missing_axes:
        project_sections, added = _append_outline_section(
            project_sections,
            title="四、技术路线、系统边界与接口方案",
            bullets=[
                "说明总体架构、关键模块、数据流、接口边界和既有系统复用关系。",
                "对模型、算力、数据、应用层分别给出建设口径，避免纯产品清单式表述。",
            ],
        )
        if added:
            added_sections.append(added)
            actions.append("补入技术路线、系统边界与接口方案。")
    if "方案比选与推荐理由" in before_proposal.missing_axes:
        project_sections, added = _append_outline_section(
            project_sections,
            title="四、备选方案比选与推荐路径",
            bullets=[
                "至少比较维持现状、分期试点、一次性建设三种路径，并说明成本、周期、风险和能力收益。",
                "推荐结论必须对应证据、约束和决策条件；证据不足时保留为条件性建议。",
            ],
        )
        if added:
            added_sections.append(added)
            actions.append("补入备选方案比选与推荐路径。")
    if "网络安全、数据安全、信创/密码要求" in before_proposal.missing_axes:
        project_sections, added = _append_outline_section(
            project_sections,
            title="五、安全合规、数据治理与信创要求",
            bullets=[
                "按项目属性说明网络安全、数据安全、密码应用、等保和信创适配关注点。",
                "若公开材料不足，先标注为待核验，不把安全合规结论写成既成事实。",
            ],
        )
        if added:
            added_sections.append(added)
            actions.append("补入安全合规、数据治理与信创要求。")
    if "采购方案、实施组织与交付边界" in before_proposal.missing_axes:
        project_sections, added = _append_outline_section(
            project_sections,
            title="六、采购实施、里程碑与交付边界",
            bullets=[
                "拆分采购范围、建设阶段、责任主体、里程碑、验收口径与后续运维。",
                "将招采前准备、试点验证、上线验收和推广复盘形成连续动作链。",
            ],
        )
        if added:
            added_sections.append(added)
            actions.append("补入采购实施、里程碑与交付边界。")
    if "运营方案、组织机制与持续改进" in before_proposal.missing_axes:
        project_sections, added = _append_outline_section(
            project_sections,
            title="七、运营机制、服务保障与持续改进",
            bullets=[
                "明确业务牵头、技术运维、数据治理、安全管理和供应商服务的责任边界。",
                "建立上线后的服务指标、问题闭环、模型/知识更新和阶段复盘机制。",
            ],
        )
        if added:
            added_sections.append(added)
            actions.append("补入运营机制、服务保障与持续改进。")
    if "投资测算、绩效目标与综合效益" in before_proposal.missing_axes:
        project_sections, added = _append_outline_section(
            project_sections,
            title="七、投资测算、绩效目标与综合效益",
            bullets=[
                "按软件平台、硬件/算力、集成实施、安全专项、运维培训拆分投资口径。",
                "绩效目标至少落到服务效率、业务覆盖、数据共享、用户体验或投入产出。",
            ],
        )
        if added:
            added_sections.append(added)
            actions.append("补入投资测算、绩效目标与综合效益。")
    if "风险控制、验收与待核验项" in before_proposal.missing_axes:
        project_sections, added = _append_outline_section(
            project_sections,
            title="八、风险控制、验收安排与待核验项",
            bullets=[
                "列出预算、数据、安全、采购周期、系统兼容和推广落地风险。",
                "明确哪些判断需以客户确认、官方批复、招标文件或评审意见为准。",
            ],
        )
        if added:
            added_sections.append(added)
            actions.append("补入风险控制、验收安排与待核验项。")
    if "经济、社会、生态与安全影响" in before_proposal.missing_axes:
        project_sections, added = _append_outline_section(
            project_sections,
            title="九、项目影响与综合效益分析",
            bullets=[
                "分别说明业务效率、公共服务或经营收益、资源能源利用、数据与系统安全影响。",
                "无法量化的效益需给出口径、基线、测量周期和责任部门，不以形容词代替指标。",
            ],
        )
        if added:
            added_sections.append(added)
            actions.append("补入项目影响与综合效益分析。")
    if "证据矩阵、假设台账与可追溯性" in before_proposal.missing_axes:
        project_sections, added = _append_outline_section(
            project_sections,
            title="附：证据矩阵、假设台账与待确认事项",
            bullets=[
                "将关键结论映射到公开来源、客户材料、测算依据或待核验假设。",
                "记录结论责任人、验证动作、截止时间和进入正式版本的放行条件。",
            ],
        )
        if added:
            added_sections.append(added)
            actions.append("补入证据矩阵、假设台账与待确认事项。")

    if "网络安全、数据安全、信创/密码要求" in before_solution.missing_axes:
        feasibility_sections, added = _append_outline_section(
            feasibility_sections,
            title="七、安全合规、信创适配与边界说明",
            bullets=[
                "在可研层面补充网络安全、数据安全、密码应用、信创适配和外部依赖边界。",
                "将无法从公开来源确认的合规判断保留为需客户/主管部门核验项。",
            ],
        )
        if added:
            added_sections.append(added)
            actions.append("在可研框架中补入安全合规与边界说明。")
    if "方案比选与推荐理由" in before_solution.missing_axes:
        feasibility_sections, added = _append_outline_section(
            feasibility_sections,
            title="五、备选方案比选与推荐方案",
            bullets=[
                "比较维持现状、分期试点、整体建设三种路径的投资、工期、收益、风险和扩展性。",
                "用决策标准解释推荐方案，不以单一产品清单替代可行性论证。",
            ],
        )
        if added:
            added_sections.append(added)
            actions.append("在可研框架中补入方案比选与推荐理由。")
    if "运营方案、组织机制与持续改进" in before_solution.missing_axes:
        feasibility_sections, added = _append_outline_section(
            feasibility_sections,
            title="八、运营方案、组织机制与持续改进",
            bullets=[
                "明确建设期和运营期组织、服务等级、知识/模型更新、数据治理和运维保障。",
                "将试点复盘、绩效监测和扩容决策纳入全生命周期机制。",
            ],
        )
        if added:
            added_sections.append(added)
            actions.append("在可研框架中补入运营方案和持续改进机制。")
    if "经济、社会、生态与安全影响" in before_solution.missing_axes:
        feasibility_sections, added = _append_outline_section(
            feasibility_sections,
            title="九、项目影响与综合效益评价",
            bullets=[
                "从经济、社会、资源能源、生态环境和安全影响维度说明项目效果。",
                "每项效益至少给出基线、目标、测量方法或待补数据。",
            ],
        )
        if added:
            added_sections.append(added)
            actions.append("在可研框架中补入项目影响与综合效益评价。")
    if "证据矩阵、假设台账与可追溯性" in before_solution.missing_axes:
        feasibility_sections, added = _append_outline_section(
            feasibility_sections,
            title="附：证据矩阵、假设台账与附件清单",
            bullets=[
                "逐项记录关键结论的来源、证据等级、适用范围和最近核验时间。",
                "将缺失的批复、预算、技术参数、客户确认和专题测算列入附件待办。",
            ],
        )
        if added:
            added_sections.append(added)
            actions.append("在可研框架中补入证据矩阵和附件清单。")
    if "采购方案、实施组织与交付边界" in before_solution.missing_axes:
        client_ppt_sections, added = _append_outline_section(
            client_ppt_sections,
            title="8. 采购实施与验收闭环",
            bullets=[
                "展示采购前置条件、实施里程碑、验收指标和运维交接。",
                "保留需客户确认的预算、采购方式和责任边界。",
            ],
        )
        if added:
            added_sections.append(added)
            actions.append("在对客页纲中补入采购实施与验收闭环。")

    review_checklist = _dedupe_strings(
        [
            *pack.review_checklist,
            "逐项核对项目建议书是否覆盖背景依据、需求分析、建设方案、安全合规、采购实施、投资绩效和风险验收。",
            "逐项核对关键结论是否进入证据矩阵，并明确事实、推断、假设和待核验项。",
            "至少完成维持现状、分期试点、整体建设三种路径的方案比选。",
            "正式外发前，将未经官方或客户确认的预算、绩效和安全合规判断显式降级。",
        ],
        limit=10,
    )
    next_steps = _dedupe_strings(
        [
            *pack.next_steps,
            "若建议书自审仍为 watch/fail，优先补官方依据、预算口径、采购方案和安全合规边界，再生成外发版。",
        ],
        limit=8,
    )
    revised = pack.model_copy(
        update={
            "project_proposal_outline": project_sections,
            "feasibility_outline": feasibility_sections,
            "client_ppt_outline": client_ppt_sections,
            "review_checklist": review_checklist,
            "next_steps": next_steps,
        }
    )
    after_solution, after_proposal = build_solution_delivery_quality_profiles(
        revised,
        evidence_links=evidence_links,
        expected_entities=expected_entities,
    )
    review_actions = _dedupe_strings(
        actions
        or [
            "完成结构完整性、方案比选、影响评价、证据可追溯性和风险边界复核。",
        ],
        limit=8,
    )
    solution_self_review = ResearchDeliverySelfReviewOut(
        triggered=True,
        before_score=before_solution.overall_score,
        after_score=after_solution.overall_score,
        actions=review_actions,
        added_sections=_dedupe_strings(added_sections, limit=8),
        notes=_dedupe_strings(
            [
                "已参照国家发展改革委 2023 年版投资项目可研大纲执行结构与证据自审。",
                "自审只补结构和边界，不会把弱证据升级成强结论。",
            ],
            limit=4,
        ),
    )
    proposal_self_review = ResearchDeliverySelfReviewOut(
        triggered=True,
        before_score=before_proposal.overall_score,
        after_score=after_proposal.overall_score,
        actions=review_actions,
        added_sections=_dedupe_strings(added_sections, limit=8),
        notes=_dedupe_strings(
            [
                "项目建议书已执行结构、方案比选和证据可追溯性自审。",
                "涉及预算、安全、采购和绩效的正式承诺仍需人工复核。",
            ],
            limit=4,
        ),
    )
    after_solution = after_solution.model_copy(update={"self_review": solution_self_review})
    after_proposal = after_proposal.model_copy(update={"self_review": proposal_self_review})
    return revised.model_copy(
        update={
            "evidence_ledger": after_solution.evidence_ledger,
            "semantic_challenge": after_solution.semantic_challenge,
            "solution_quality_profile": after_solution,
            "project_proposal_quality_profile": after_proposal,
        }
    )


def evaluate_formal_document_sections(
    sections: Sequence[FormalSection],
    *,
    review_target: str,
    source_support_score: int,
    grounded_count: int,
    checklist_count: int,
    evidence_note_count: int,
    evidence_links: Sequence[ResearchEntityEvidenceOut] = (),
    expected_entities: Sequence[str] = (),
    expected_scope_terms: Sequence[str] = (),
) -> ResearchDeliveryQualityProfileOut:
    ledger = build_delivery_evidence_ledger(
        _formal_claim_rows(sections),
        evidence_links=evidence_links,
        expected_entities=expected_entities,
    )
    return _quality_profile(
        review_target=review_target,
        text=_formal_text(sections),
        source_support_score=source_support_score,
        grounded_count=grounded_count,
        checklist_count=checklist_count,
        evidence_note_count=evidence_note_count,
        semantic_rows=_formal_rows(sections),
        challenge_rows=_formal_claim_rows(sections),
        evidence_ledger=ledger,
        expected_scope_terms=expected_scope_terms or expected_entities,
        expected_entities=expected_entities,
    )


def _formal_section(
    title: str,
    rows: Iterable[object],
) -> FormalSection:
    return title, _dedupe_strings(rows, limit=10)


def review_and_improve_formal_document_sections(
    sections: Sequence[FormalSection],
    *,
    review_target: str,
    source_support_score: int,
    grounded_count: int,
    checklist_count: int,
    evidence_note_count: int,
    evidence_links: Sequence[ResearchEntityEvidenceOut] = (),
    expected_entities: Sequence[str] = (),
    expected_scope_terms: Sequence[str] = (),
) -> tuple[list[FormalSection], ResearchDeliveryQualityProfileOut]:
    before = evaluate_formal_document_sections(
        sections,
        review_target=review_target,
        source_support_score=source_support_score,
        grounded_count=grounded_count,
        checklist_count=checklist_count,
        evidence_note_count=evidence_note_count,
        evidence_links=evidence_links,
        expected_entities=expected_entities,
        expected_scope_terms=expected_scope_terms,
    )
    revised = list(sections)
    additions: list[FormalSection] = []
    actions: list[str] = []
    if "现状差距与需求分析" in before.missing_axes:
        additions.append(
            _formal_section(
                "补充：现状差距与需求分析",
                [
                    "说明存量系统、现行流程、业务痛点和本次建设要解决的具体问题。",
                    "把需求拆成业务、数据、协同、安全和运营五类，避免泛化表述。",
                ],
            )
        )
        actions.append("补入现状差距与需求分析。")
    if "技术方案、系统边界与接口" in before.missing_axes:
        additions.append(
            _formal_section(
                "补充：技术路线、系统边界与接口",
                [
                    "说明总体架构、能力模块、数据流、接口复用和与既有平台的边界关系。",
                    "对模型、算力、数据和应用层分别给出建设边界。",
                ],
            )
        )
        actions.append("补入技术路线、系统边界与接口。")
    if "方案比选与推荐理由" in before.missing_axes:
        additions.append(
            _formal_section(
                "补充：备选方案比选与推荐理由",
                [
                    "比较维持现状、分期试点、整体建设三种路径的成本、周期、收益、风险和扩展性。",
                    "推荐方案需对应明确决策标准、证据依据和生效条件。",
                ],
            )
        )
        actions.append("补入备选方案比选与推荐理由。")
    if "网络安全、数据安全、信创/密码要求" in before.missing_axes:
        additions.append(
            _formal_section(
                "补充：安全合规、数据治理与信创说明",
                [
                    "说明网络安全、数据安全、密码应用、信创适配和等保关注点。",
                    "无法从公开材料确认的安全合规结论保留为待核验项。",
                ],
            )
        )
        actions.append("补入安全合规、数据治理与信创说明。")
    if "采购方案、实施组织与交付边界" in before.missing_axes:
        additions.append(
            _formal_section(
                "补充：采购实施、里程碑与交付边界",
                [
                    "说明采购范围、阶段安排、责任主体、验收口径与后续运维。",
                    "区分可立即执行事项与需客户/主管部门确认事项。",
                ],
            )
        )
        actions.append("补入采购实施、里程碑与交付边界。")
    if "运营方案、组织机制与持续改进" in before.missing_axes:
        additions.append(
            _formal_section(
                "补充：运营方案、组织机制与持续改进",
                [
                    "明确业务、技术、数据、安全和供应商服务责任，建立服务等级与问题闭环。",
                    "说明模型/知识更新、绩效监测、试点复盘和扩容决策机制。",
                ],
            )
        )
        actions.append("补入运营方案、组织机制与持续改进。")
    if "投资测算、绩效目标与综合效益" in before.missing_axes:
        additions.append(
            _formal_section(
                "补充：投资测算、绩效目标与综合效益",
                [
                    "按平台、硬件/算力、实施、安全专项、培训运维拆分投资口径。",
                    "绩效目标至少落到效率、覆盖、共享、体验或投入产出指标。",
                ],
            )
        )
        actions.append("补入投资测算、绩效目标与综合效益。")
    if "风险控制、验收与待核验项" in before.missing_axes:
        additions.append(
            _formal_section(
                "补充：风险控制、验收安排与待核验项",
                [
                    "列出预算、采购周期、数据、安全、接口兼容和推广应用风险。",
                    "明确哪些内容仍需官方文件、客户确认或评审意见支撑。",
                ],
            )
        )
        actions.append("补入风险控制、验收安排与待核验项。")
    if "经济、社会、生态与安全影响" in before.missing_axes:
        additions.append(
            _formal_section(
                "补充：项目影响与综合效益评价",
                [
                    "分别说明经济、社会、资源能源、生态环境和安全影响。",
                    "每项效益明确基线、目标值、测量周期、数据来源和责任部门。",
                ],
            )
        )
        actions.append("补入项目影响与综合效益评价。")
    if "证据矩阵、假设台账与可追溯性" in before.missing_axes:
        additions.append(
            _formal_section(
                "补充：证据矩阵、假设台账与附件清单",
                [
                    "将关键结论映射到公开来源、客户材料、测算依据或待核验假设。",
                    "为待核验项记录责任人、验证动作、截止时间和正式版本放行条件。",
                ],
            )
        )
        actions.append("补入证据矩阵、假设台账与附件清单。")

    revised.extend(additions)
    after = evaluate_formal_document_sections(
        revised,
        review_target=review_target,
        source_support_score=source_support_score,
        grounded_count=grounded_count,
        checklist_count=checklist_count,
        evidence_note_count=evidence_note_count,
        evidence_links=evidence_links,
        expected_entities=expected_entities,
        expected_scope_terms=expected_scope_terms,
    )
    self_review = ResearchDeliverySelfReviewOut(
        triggered=bool(actions),
        before_score=before.overall_score,
        after_score=after.overall_score,
        actions=_dedupe_strings(actions, limit=8),
        added_sections=_dedupe_strings([title for title, _rows in additions], limit=8),
        notes=_dedupe_strings(
            [
                "正式文档导出前已参照国家发展改革委 2023 年版投资项目可研大纲执行结构与证据自审。",
                "自审仅补足结构、边界和风险口径，不替代人工复核与正式审批。",
            ],
            limit=4,
        ),
    )
    after = after.model_copy(update={"self_review": self_review})
    ledger_rows = [
        f"账本状态：{after.evidence_ledger.status}；主张 {after.evidence_ledger.claim_count} 条；"
        f"证据 {after.evidence_ledger.evidence_count} 个；高置信覆盖 "
        f"{after.evidence_ledger.high_confidence_coverage_percent}%。"
    ]
    ledger_rows.extend(
        [
            f"{claim.claim_id} | {claim.verification_status} | {claim.text}"
            for claim in after.evidence_ledger.claims[:8]
        ]
    )
    ledger_rows.extend(
        [
            f"{issue.issue_id} | {issue.severity} | {issue.summary}"
            for issue in after.evidence_ledger.consistency_issues[:5]
        ]
    )
    revised.append(("附：主张—证据账本与一致性检查", _dedupe_strings(ledger_rows, limit=14)))
    challenge = after.semantic_challenge
    challenge_rows = [
        f"挑战者状态：{challenge.status}；评分 {challenge.overall_score}/100；问题 {challenge.issue_count} 个；高严重度 {challenge.high_severity_count} 个。",
        f"黄金样本：{challenge.golden_sample_title or '未匹配'}；对齐分 {challenge.golden_sample_alignment_score}/100。",
    ]
    challenge_rows.extend(
        [
            f"{issue.issue_id} | {issue.severity} | {issue.issue_type} | {issue.summary}"
            for issue in challenge.issues[:8]
        ]
    )
    challenge_rows.extend([f"修订动作：{action}" for action in challenge.recommended_actions[:4]])
    revised.append(("附：语义挑战者审查记录", _dedupe_strings(challenge_rows, limit=14)))
    audit_rows = _dedupe_strings(
        [
            f"审查框架：{after.framework_label}",
            f"自审对象：{after.review_target}",
            f"综合评分：{after.overall_score}/100，状态：{after.status}",
            f"已覆盖审查轴：{'；'.join(after.required_axes)}",
            f"仍需关注：{'；'.join(after.gaps[:3])}" if after.gaps else "仍需关注：正式外发前复核预算、采购、安全和绩效口径。",
            *after.self_review.actions[:4],
        ],
        limit=10,
    )
    revised.append(("附：交付前质量审查与自修订记录", audit_rows))
    return revised, after
