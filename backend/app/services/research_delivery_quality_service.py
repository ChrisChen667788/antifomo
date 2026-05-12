from __future__ import annotations

from collections.abc import Iterable, Sequence

from app.schemas.research import (
    ResearchDeliveryQualityMetricOut,
    ResearchDeliveryQualityProfileOut,
    ResearchDeliverySelfReviewOut,
    ResearchSolutionDeliveryPackOut,
    ResearchSolutionOutlineSectionOut,
)
from app.services.content_extractor import normalize_text

OutlineSection = ResearchSolutionOutlineSectionOut
FormalSection = tuple[str, list[str]]

_STATUS_PASS = 84
_STATUS_WATCH = 68

_AXIS_LABELS: dict[str, str] = {
    "basis": "立项背景与编制依据",
    "current_state": "现状差距与需求分析",
    "objectives": "建设目标与建设内容",
    "solution_architecture": "技术方案、系统边界与接口",
    "security_compliance": "网络安全、数据安全、信创/密码要求",
    "procurement_delivery": "采购方案、实施组织与交付边界",
    "budget_value": "投资测算、绩效目标与综合效益",
    "risk_validation": "风险控制、验收与待核验项",
}

_AXIS_TERMS: dict[str, tuple[str, ...]] = {
    "basis": ("背景", "依据", "政策", "规划", "项目概况", "立项"),
    "current_state": ("现状", "差距", "需求", "问题", "业务流程", "业务量"),
    "objectives": ("目标", "建设内容", "范围", "任务", "组件", "功能"),
    "solution_architecture": ("技术方案", "总体架构", "接口", "系统边界", "数据共享", "应用系统", "基础设施"),
    "security_compliance": ("安全", "信创", "密码", "等保", "数据安全", "网络安全", "合规"),
    "procurement_delivery": ("采购", "实施", "进度", "组织", "里程碑", "交付", "验收", "招标"),
    "budget_value": ("投资", "预算", "资金", "绩效", "效益", "投入产出", "估算"),
    "risk_validation": ("风险", "待核验", "边界", "审查", "验收", "限制", "结论"),
}

_REQUIRED_AXES: dict[str, tuple[str, ...]] = {
    "solution_delivery": (
        "current_state",
        "objectives",
        "solution_architecture",
        "security_compliance",
        "procurement_delivery",
        "budget_value",
        "risk_validation",
    ),
    "project_proposal": (
        "basis",
        "current_state",
        "objectives",
        "solution_architecture",
        "security_compliance",
        "procurement_delivery",
        "budget_value",
        "risk_validation",
    ),
    "feasibility_study": (
        "basis",
        "current_state",
        "objectives",
        "solution_architecture",
        "security_compliance",
        "procurement_delivery",
        "budget_value",
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


def _formal_text(sections: Sequence[FormalSection]) -> str:
    return normalize_text(" ".join([*[title for title, _rows in sections], *[row for _title, rows in sections for row in rows]]))


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
    ]
    overall = round(
        metrics[0].score * 0.34
        + metrics[1].score * 0.26
        + metrics[2].score * 0.22
        + metrics[3].score * 0.18
    )
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
    )


def build_solution_delivery_quality_profiles(
    pack: ResearchSolutionDeliveryPackOut,
) -> tuple[ResearchDeliveryQualityProfileOut, ResearchDeliveryQualityProfileOut]:
    solution_text = _outline_text(
        [
            *pack.feasibility_outline,
            *pack.project_proposal_outline,
            *pack.client_ppt_outline,
        ]
    )
    proposal_text = _outline_text(pack.project_proposal_outline)
    solution_profile = _quality_profile(
        review_target="solution_delivery",
        text=solution_text,
        source_support_score=pack.source_support_score,
        grounded_count=len(pack.grounding_checks),
        checklist_count=len(pack.review_checklist),
        advisory_count=len(pack.advisory_artifacts),
        next_step_count=len(pack.next_steps),
        evidence_note_count=len(pack.intelligence_summary),
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
) -> ResearchSolutionDeliveryPackOut:
    before_solution, before_proposal = build_solution_delivery_quality_profiles(pack)
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
    after_solution, after_proposal = build_solution_delivery_quality_profiles(revised)
    if actions:
        solution_self_review = ResearchDeliverySelfReviewOut(
            triggered=True,
            before_score=before_solution.overall_score,
            after_score=after_solution.overall_score,
            actions=_dedupe_strings(actions, limit=8),
            added_sections=_dedupe_strings(added_sections, limit=8),
            notes=_dedupe_strings(
                [
                    "已按中国科技项目常见申报/评审口径补齐缺失结构。",
                    "自审提升只补结构和边界，不会把弱证据升级成强结论。",
                ],
                limit=4,
            ),
        )
        proposal_self_review = ResearchDeliverySelfReviewOut(
            triggered=True,
            before_score=before_proposal.overall_score,
            after_score=after_proposal.overall_score,
            actions=_dedupe_strings(actions, limit=8),
            added_sections=_dedupe_strings(added_sections, limit=8),
            notes=_dedupe_strings(
                [
                    "项目建议书已执行结构完整性自审，并自动补入关键缺项。",
                    "涉及预算、安全、采购和绩效的正式承诺仍需人工复核。",
                ],
                limit=4,
            ),
        )
        after_solution = after_solution.model_copy(update={"self_review": solution_self_review})
        after_proposal = after_proposal.model_copy(update={"self_review": proposal_self_review})
    return revised.model_copy(
        update={
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
) -> ResearchDeliveryQualityProfileOut:
    return _quality_profile(
        review_target=review_target,
        text=_formal_text(sections),
        source_support_score=source_support_score,
        grounded_count=grounded_count,
        checklist_count=checklist_count,
        evidence_note_count=evidence_note_count,
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
) -> tuple[list[FormalSection], ResearchDeliveryQualityProfileOut]:
    before = evaluate_formal_document_sections(
        sections,
        review_target=review_target,
        source_support_score=source_support_score,
        grounded_count=grounded_count,
        checklist_count=checklist_count,
        evidence_note_count=evidence_note_count,
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

    revised.extend(additions)
    after = evaluate_formal_document_sections(
        revised,
        review_target=review_target,
        source_support_score=source_support_score,
        grounded_count=grounded_count,
        checklist_count=checklist_count,
        evidence_note_count=evidence_note_count,
    )
    self_review = ResearchDeliverySelfReviewOut(
        triggered=bool(actions),
        before_score=before.overall_score,
        after_score=after.overall_score,
        actions=_dedupe_strings(actions, limit=8),
        added_sections=_dedupe_strings([title for title, _rows in additions], limit=8),
        notes=_dedupe_strings(
            [
                "正式文档导出前已执行中国科技项目交付质量自审。",
                "自审仅补足结构、边界和风险口径，不替代人工复核与正式审批。",
            ],
            limit=4,
        ),
    )
    after = after.model_copy(update={"self_review": self_review})
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
