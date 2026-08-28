from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, DivisionByZero, InvalidOperation
import hashlib
import json
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.decision_studio_entities import DecisionDocumentContract, DecisionPolicyPack


POLICY_RUNTIME_VERSION = "1.9.3-contract-v1"
ALLOWED_FIELD_STATES = {"evidence", "calculated", "assumption", "missing", "not_applicable"}


def _fields(section: str, rows: list[tuple[str, str, str]]) -> list[dict[str, object]]:
    return [
        {
            "key": key,
            "label": label,
            "section": section,
            "required": True,
            "data_type": data_type,
        }
        for key, label, data_type in rows
    ]


GOVERNMENT_FSR_FIELDS = [
    *_fields("概述", [("project_overview", "项目概况", "text"), ("project_unit", "项目单位概况", "text"), ("compilation_basis", "编制依据", "evidence_list"), ("main_conclusions", "主要结论与建议", "text")]),
    *_fields("项目建设背景和必要性", [("project_background", "建设背景", "text"), ("project_necessity", "建设必要性", "text")]),
    *_fields("需求分析与项目产出", [("demand_analysis", "需求分析", "text"), ("output_plan", "建设内容、规模及产出", "table")]),
    *_fields("项目选址与要素保障", [("site_selection", "项目选址", "text"), ("land_conditions", "用地条件", "text"), ("resource_environment", "资源环境要素", "text"), ("construction_conditions", "外部建设条件", "text")]),
    *_fields("项目建设方案", [("technical_scheme", "技术方案", "text"), ("equipment_scheme", "设备方案", "table"), ("civil_scheme", "工程方案", "text"), ("digital_scheme", "数字化方案", "text"), ("implementation_schedule", "建设工期与进度", "table"), ("procurement_scheme", "采购与招标方案", "text")]),
    *_fields("项目运营方案", [("operation_model", "运营模式", "text"), ("organization_plan", "组织机构", "text"), ("safety_plan", "安全与应急", "text"), ("performance_plan", "绩效管理", "table")]),
    *_fields("项目投融资与财务方案", [("investment_estimate", "投资估算", "calculation"), ("financing_plan", "资金筹措", "table"), ("financial_analysis", "财务可持续性", "calculation"), ("debt_analysis", "债务与偿债能力", "calculation")]),
    *_fields("项目影响效果分析", [("economic_impact", "经济影响", "text"), ("social_impact", "社会影响", "text"), ("ecological_impact", "生态环境影响", "text"), ("carbon_analysis", "碳排放与双碳影响", "calculation"), ("resource_efficiency", "资源能源利用", "calculation")]),
    *_fields("项目风险管控方案", [("risk_identification", "风险识别", "table"), ("risk_mitigation", "风险防范措施", "table"), ("contingency_plan", "重大风险应急预案", "text")]),
    *_fields("研究结论及建议", [("feasibility_conclusion", "可行性结论", "text"), ("implementation_recommendations", "实施建议", "text")]),
    *_fields("附表附图附件", [("required_tables", "必要附表", "artifact_list"), ("required_drawings", "必要附图", "artifact_list"), ("approval_attachments", "审批及支撑附件", "artifact_list")]),
]


BUILTIN_POLICY_PACKS: tuple[dict[str, object], ...] = (
    {
        "pack_key": "government_fsr_2023",
        "version": "2023.2",
        "title": "政府投资项目可行性研究报告编写通用大纲（2023年版）合同包",
        "authority": "国家发展和改革委员会",
        "source_uri": "https://www.gov.cn/zhengce/zhengceku/2023-04/11/5750844/files/5d4ac74386e84ead89684a6508368927.pdf",
        "document_kind": "government_feasibility_study",
        "sections": [
            "概述",
            "项目建设背景和必要性",
            "需求分析与项目产出",
            "项目选址与要素保障",
            "项目建设方案",
            "项目运营方案",
            "项目投融资与财务方案",
            "项目影响效果分析",
            "项目风险管控方案",
            "研究结论及建议",
            "附表附图附件",
        ],
        "fields": GOVERNMENT_FSR_FIELDS,
        "applicability": {"investment_nature": "government", "effective_from": "2023-05-01"},
    },
    {
        "pack_key": "enterprise_fsr_2023",
        "version": "2023.2",
        "title": "企业投资项目可行性研究报告参考合同包（2023年版）",
        "authority": "国家发展和改革委员会",
        "source_uri": "https://www.ndrc.gov.cn/xxgk/zcfb/ghxwj/202304/P020230407401908613786.pdf",
        "document_kind": "enterprise_feasibility_study",
        "sections": ["项目概况", "市场需求", "建设方案", "运营方案", "投融资", "财务分析", "影响效果", "风险管控", "结论"],
        "fields": [
            *_fields("项目概况", [("project_overview", "项目概况", "text"), ("decision_basis", "决策依据", "evidence_list")]),
            *_fields("市场需求", [("market_demand", "市场需求", "text"), ("competition", "竞争格局", "text")]),
            *_fields("建设方案", [("construction_plan", "建设方案", "text"), ("option_comparison", "多方案比选", "table")]),
            *_fields("运营方案", [("operation_model", "运营模式", "text"), ("organization_plan", "组织与人力", "text")]),
            *_fields("投融资", [("investment_estimate", "投资估算", "calculation"), ("financing_plan", "融资方案", "table")]),
            *_fields("财务分析", [("revenue_forecast", "收入预测", "calculation"), ("cashflow_analysis", "现金流分析", "calculation"), ("sensitivity_analysis", "敏感性分析", "calculation")]),
            *_fields("影响效果", [("economic_impact", "经济影响", "text"), ("environmental_impact", "环境影响", "text")]),
            *_fields("风险管控", [("risk_register", "风险登记册", "table"), ("risk_mitigation", "应对措施", "table")]),
            *_fields("结论", [("feasibility_conclusion", "可行性结论", "text")]),
        ],
        "applicability": {"investment_nature": "enterprise", "effective_from": "2023-05-01"},
    },
    {
        "pack_key": "project_proposal_cn",
        "version": "2026.1",
        "title": "中国项目建议书立项合同包",
        "authority": "Anti-FOMO first-party pack based on public investment guidance",
        "source_uri": "https://www.gov.cn/zhengce/zhengceku/2023-04/11/5750844/files/1f9fbc086883486f98433a945c32e50c.pdf",
        "document_kind": "project_proposal",
        "sections": ["项目概况", "建设背景", "必要性", "目标范围", "建设内容", "投资估算", "实施安排", "效益与风险", "结论建议"],
        "fields": [
            *_fields("项目概况", [("project_overview", "项目概况", "text")]),
            *_fields("建设背景", [("project_background", "建设背景", "text")]),
            *_fields("必要性", [("project_necessity", "建设必要性", "text")]),
            *_fields("目标范围", [("objectives", "建设目标", "text"), ("scope", "建设范围", "text")]),
            *_fields("建设内容", [("construction_content", "主要建设内容", "table")]),
            *_fields("投资估算", [("preliminary_investment", "初步投资估算", "calculation")]),
            *_fields("实施安排", [("implementation_plan", "实施计划", "table"), ("organization_plan", "组织保障", "text")]),
            *_fields("效益与风险", [("benefit_analysis", "效益分析", "text"), ("risk_register", "风险分析", "table")]),
            *_fields("结论建议", [("proposal_conclusion", "立项结论与下一阶段工作", "text")]),
        ],
        "applicability": {"phase": "project_initiation"},
    },
    {
        "pack_key": "solution_proposal_cn",
        "version": "2026.1",
        "title": "中国政企解决方案交付合同包",
        "authority": "Anti-FOMO first-party pack",
        "source_uri": "",
        "document_kind": "solution_proposal",
        "sections": ["客户现状", "目标与范围", "方案比选", "总体架构", "实施路径", "投资价值", "风险保障", "验收证据"],
        "fields": [
            *_fields("客户现状", [("customer_context", "客户现状与问题", "evidence_list")]),
            *_fields("目标与范围", [("solution_objectives", "方案目标", "text"), ("solution_scope", "范围边界", "text")]),
            *_fields("方案比选", [("option_comparison", "方案比选", "table")]),
            *_fields("总体架构", [("architecture", "总体架构", "artifact_list"), ("architecture_decisions", "ADR 与权衡", "artifact_list")]),
            *_fields("实施路径", [("implementation_plan", "实施路径", "table")]),
            *_fields("投资价值", [("investment_estimate", "投资估算", "calculation"), ("value_case", "价值与收益", "calculation")]),
            *_fields("风险保障", [("risk_register", "风险与保障", "table")]),
            *_fields("验收证据", [("acceptance_evidence", "验收与 PoA 证据", "artifact_list")]),
        ],
        "applicability": {"phase": "solution_design"},
    },
)


def _canonical_hash(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def ensure_builtin_policy_packs(db: Session) -> list[DecisionPolicyPack]:
    packs: list[DecisionPolicyPack] = []
    for definition in BUILTIN_POLICY_PACKS:
        pack = db.scalar(
            select(DecisionPolicyPack)
            .where(DecisionPolicyPack.pack_key == definition["pack_key"])
            .where(DecisionPolicyPack.version == definition["version"])
        )
        schema_payload = {
            "runtime_version": POLICY_RUNTIME_VERSION,
            "sections": definition["sections"],
            "fields": definition["fields"],
            "applicability": definition["applicability"],
        }
        content_hash = _canonical_hash({**definition, "schema_payload": schema_payload})
        if pack is None:
            pack = DecisionPolicyPack(
                pack_key=str(definition["pack_key"]),
                version=str(definition["version"]),
                title=str(definition["title"]),
                authority=str(definition["authority"]),
                source_uri=str(definition["source_uri"]),
                document_kind=str(definition["document_kind"]),
                schema_payload=schema_payload,
                content_hash=content_hash,
            )
            db.add(pack)
        elif pack.content_hash != content_hash:
            pack.status = "superseded"
        packs.append(pack)
    db.commit()
    for pack in packs:
        db.refresh(pack)
    return packs


def serialize_policy_pack(pack: DecisionPolicyPack) -> dict[str, object]:
    return {
        "id": str(pack.id),
        "pack_key": pack.pack_key,
        "version": pack.version,
        "title": pack.title,
        "authority": pack.authority,
        "source_uri": pack.source_uri,
        "document_kind": pack.document_kind,
        "status": pack.status,
        "schema": pack.schema_payload,
        "content_hash": pack.content_hash,
    }


def _initial_fields(pack: DecisionPolicyPack) -> dict[str, object]:
    return {
        str(field["key"]): {
            **field,
            "state": "missing",
            "value": None,
            "owner": "",
            "evidence_refs": [],
            "note": "",
        }
        for field in list(pack.schema_payload.get("fields") or [])
    }


def _gaps(fields: dict[str, object]) -> list[dict[str, object]]:
    gaps: list[dict[str, object]] = []
    for key, raw in fields.items():
        field = dict(raw) if isinstance(raw, dict) else {}
        if field.get("required") and field.get("state") == "missing":
            gaps.append(
                {
                    "field_key": key,
                    "label": field.get("label") or key,
                    "section": field.get("section") or "",
                    "owner": field.get("owner") or "",
                    "blocking": True,
                }
            )
    return gaps


def create_document_contract(
    db: Session,
    *,
    notebook_id: UUID,
    policy_pack_id: UUID,
    title: str,
) -> DecisionDocumentContract:
    pack = db.get(DecisionPolicyPack, policy_pack_id)
    if pack is None or pack.status != "active":
        raise ValueError("The selected policy pack is unavailable or superseded.")
    fields = _initial_fields(pack)
    contract = DecisionDocumentContract(
        notebook_id=notebook_id,
        policy_pack_id=pack.id,
        title=title.strip()[:240],
        document_kind=pack.document_kind,
        fields_payload=fields,
        gaps_payload=_gaps(fields),
        policy_snapshot=serialize_policy_pack(pack),
    )
    db.add(contract)
    db.commit()
    db.refresh(contract)
    return contract


def serialize_contract(contract: DecisionDocumentContract) -> dict[str, object]:
    fields = dict(contract.fields_payload or {})
    gap_count = len(contract.gaps_payload or [])
    return {
        "id": str(contract.id),
        "notebook_id": str(contract.notebook_id),
        "policy_pack_id": str(contract.policy_pack_id),
        "title": contract.title,
        "document_kind": contract.document_kind,
        "status": contract.status,
        "revision": contract.revision,
        "fields": fields,
        "assumptions": list(contract.assumptions_payload or []),
        "calculations": list(contract.calculations_payload or []),
        "gaps": list(contract.gaps_payload or []),
        "gap_count": gap_count,
        "completion_percent": round(100 * (len(fields) - gap_count) / max(1, len(fields))),
        "policy_snapshot": contract.policy_snapshot,
    }


def update_contract_field(
    db: Session,
    *,
    contract: DecisionDocumentContract,
    field_key: str,
    state: str,
    value: object,
    owner: str,
    evidence_refs: list[str],
    note: str,
) -> DecisionDocumentContract:
    if state not in ALLOWED_FIELD_STATES:
        raise ValueError(f"Unsupported field state: {state}")
    fields = dict(contract.fields_payload or {})
    if field_key not in fields or not isinstance(fields[field_key], dict):
        raise ValueError("Unknown contract field.")
    if state in {"evidence", "calculated"} and not evidence_refs:
        raise ValueError(f"{state} fields require evidence or calculation references.")
    if state == "assumption" and not note.strip():
        raise ValueError("Assumption fields require an explicit note.")
    if state == "not_applicable" and not note.strip():
        raise ValueError("Not-applicable fields require a reason.")
    fields[field_key] = {
        **dict(fields[field_key]),
        "state": state,
        "value": value,
        "owner": owner.strip()[:160],
        "evidence_refs": list(dict.fromkeys(value.strip() for value in evidence_refs if value.strip())),
        "note": note.strip(),
        "updated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    contract.fields_payload = fields
    contract.gaps_payload = _gaps(fields)
    contract.revision += 1
    contract.status = "ready_for_review" if not contract.gaps_payload else "draft"
    db.commit()
    db.refresh(contract)
    return contract


def add_contract_assumption(
    db: Session,
    *,
    contract: DecisionDocumentContract,
    assumption_key: str,
    statement: str,
    owner: str,
    validation_action: str,
) -> DecisionDocumentContract:
    assumptions = list(contract.assumptions_payload or [])
    if any(item.get("key") == assumption_key for item in assumptions if isinstance(item, dict)):
        raise ValueError("Assumption key already exists.")
    assumptions.append(
        {
            "key": assumption_key,
            "statement": statement.strip(),
            "owner": owner.strip(),
            "validation_action": validation_action.strip(),
            "status": "open",
        }
    )
    contract.assumptions_payload = assumptions
    contract.revision += 1
    db.commit()
    db.refresh(contract)
    return contract


def _decimal(value: object) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"Invalid calculation input: {value}") from exc


def _calculate(operation: str, values: list[Decimal]) -> Decimal:
    if not values:
        raise ValueError("A calculation requires at least one input.")
    if operation == "sum":
        return sum(values, Decimal("0"))
    if operation == "subtract":
        return values[0] - sum(values[1:], Decimal("0"))
    if operation == "multiply":
        result = Decimal("1")
        for value in values:
            result *= value
        return result
    if operation in {"divide", "ratio"}:
        if len(values) != 2:
            raise ValueError(f"{operation} requires exactly two inputs.")
        try:
            return values[0] / values[1]
        except DivisionByZero as exc:
            raise ValueError("Calculation denominator cannot be zero.") from exc
    raise ValueError(f"Unsupported deterministic operation: {operation}")


def add_contract_calculation(
    db: Session,
    *,
    contract: DecisionDocumentContract,
    calculation_key: str,
    label: str,
    operation: str,
    inputs: list[dict[str, object]],
    unit: str,
) -> DecisionDocumentContract:
    if not inputs:
        raise ValueError("Calculation inputs are required.")
    for item in inputs:
        if not list(item.get("source_refs") or []) and not str(item.get("assumption_ref") or "").strip():
            raise ValueError("Every calculation input requires source_refs or an assumption_ref.")
    values = [_decimal(item.get("value")) for item in inputs]
    result = _calculate(operation, values)
    calculations = [
        item for item in list(contract.calculations_payload or [])
        if not isinstance(item, dict) or item.get("key") != calculation_key
    ]
    calculation = {
        "key": calculation_key,
        "label": label.strip(),
        "operation": operation,
        "inputs": inputs,
        "result": format(result.normalize(), "f"),
        "unit": unit.strip(),
        "formula": f"{operation}({', '.join(str(item.get('key') or item.get('value')) for item in inputs)})",
        "calculated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
    }
    calculations.append(calculation)
    contract.calculations_payload = calculations
    contract.revision += 1
    db.commit()
    db.refresh(contract)
    return contract
