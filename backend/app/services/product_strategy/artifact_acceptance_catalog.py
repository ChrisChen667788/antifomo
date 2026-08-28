from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from app.services.product_strategy.catalog import CATALOG_VERSION, canonical_digest, iso
from app.services.product_strategy.context_packet_catalog import (
    PROJECT_SCOPE,
    context_packet_catalog_digest,
    context_packet_definitions,
)


ARTIFACT_ACCEPTANCE_VERSION = "2.10.2"
INITIALIZATION_EVENT_KEY = "anti-fomo:2.10.2:reviewable-artifact-acceptance-initialization"
INSTRUCTION_RECORDED_AT = datetime(2026, 8, 28, tzinfo=UTC)


ARTIFACT_DETAIL_BY_CARD_KEY: dict[str, dict[str, Any]] = {
    "workbuddy:integrate": {
        "artifact_type": "controlled_external_result_return_review",
        "title": "受控外部结果回传边界验收草案",
        "artifact_summary": "用于人工复核允许回传目标、来源血缘、失败闭环与人工处理入口的验收草案；不触发外部回传。",
    },
    "qwen_work:build": {
        "artifact_type": "editable_deliverable_lineage_review",
        "title": "可编辑交付物与来源血缘验收草案",
        "artifact_summary": "用于人工复核交付物版本、来源血缘和待确认项展示的验收草案；不读取第三方办公数据。",
    },
    "langhub:build": {
        "artifact_type": "consented_context_change_preview_review",
        "title": "经同意的上下文与变更预览验收草案",
        "artifact_summary": "用于人工复核项目范围、保留期限、预览与撤销边界的验收草案；不写入项目上下文。",
    },
    "baidu_dumate:defer": {
        "artifact_type": "deferred_desktop_automation_safety_review",
        "title": "桌面自动化暂缓条件验收草案",
        "artifact_summary": "用于人工复核暂缓条件是否仍满足的验收草案；不新增桌面控制、文件写入或自动化执行。",
    },
}


def instruction_evidence() -> dict[str, Any]:
    """Development instruction only; it cannot mark an artifact accepted."""

    return {
        "kind": "user_instruction",
        "actor_identity_status": "unverified",
        "scope": "artifact_acceptance_definition_only",
        "instruction": "下一步应是受 Office/视觉证据门禁约束的 2.10.2 交付物验收与修订差异。",
        "recorded_at": iso(INSTRUCTION_RECORDED_AT),
        "authorization_scope": "initialize_hold_only_artifact_acceptance_definitions",
        "does_not_approve_artifact_acceptance": True,
        "does_not_approve_release": True,
        "does_not_authorize_execution": True,
        "requires_human_evidence_review": True,
    }


def _acceptance_checklist() -> list[dict[str, Any]]:
    """The two required evidence classes intentionally begin missing.

    No file bytes, Office metadata, screenshots, or render output are consumed
    here.  A future, separately authorized review may attach evidence; this
    release only records the fail-closed condition that exists today.
    """

    return [
        {
            "check_key": "office_delivery_evidence",
            "title": "Office 交付物可打开性与内容完整性证据",
            "required": True,
            "evidence_kind": "human_supplied_office_delivery_evidence",
            "evidence_status": "missing",
            "result": "hold",
            "blocks_acceptance": True,
            "note": "2.10.2 不上传、读取、解析、生成或验证 Office 文件；缺少人工提供的可复核证据。",
        },
        {
            "check_key": "visual_render_evidence",
            "title": "视觉渲染、版式与可读性证据",
            "required": True,
            "evidence_kind": "human_supplied_visual_render_evidence",
            "evidence_status": "missing",
            "result": "hold",
            "blocks_acceptance": True,
            "note": "2.10.2 不捕获、渲染或评估视觉产物；缺少人工提供的截图、渲染或视觉复核证据。",
        },
        {
            "check_key": "human_acceptance_decision",
            "title": "人工验收结论",
            "required": True,
            "evidence_kind": "human_review_record",
            "evidence_status": "not_recorded",
            "result": "hold",
            "blocks_acceptance": True,
            "note": "没有人工验收结论时，验收状态必须维持 HOLD。",
        },
    ]


def _source_bundle(packet: dict[str, Any]) -> dict[str, Any]:
    return {
        "bundle_kind": "decision_context_packet_binding",
        "decision_context_packet": {
            "packet_key": packet["packet_key"],
            "roadmap_card_key": packet["roadmap_card_key"],
            "decision": packet["decision"],
            "revision": packet["revision"],
            "revision_digest": packet["revision_digest"],
            "source_catalog_version": CATALOG_VERSION,
            "source_catalog_keys": list(packet["source_catalog_keys"]),
            "source_digests": list(packet["source_digests"]),
            "source_references": deepcopy(packet["source_references"]),
        },
        "evidence_collection": {
            "office_file_processing_performed": False,
            "visual_render_processing_performed": False,
            "office_evidence_status": "missing",
            "visual_evidence_status": "missing",
            "note": "该 bundle 仅引用 2.10.1 已记录的上下文和来源摘要，未收集 Office 或视觉证据。",
        },
    }


def evidence_source_bundle_from_context_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Build an evidence bundle from a serialized 2.10.1 packet shape."""

    return _source_bundle(packet)


def _artifact_without_digest(packet: dict[str, Any]) -> dict[str, Any]:
    detail = ARTIFACT_DETAIL_BY_CARD_KEY.get(packet["roadmap_card_key"])
    if detail is None:
        raise ValueError(f"No 2.10.2 artifact acceptance definition exists for {packet['roadmap_card_key']}.")

    bundle = _source_bundle(packet)
    return {
        "artifact_key": f"{PROJECT_SCOPE}:2.10.2:{packet['roadmap_card_key']}:artifact-acceptance",
        "project_scope": PROJECT_SCOPE,
        "decision_context_packet_key": packet["packet_key"],
        "roadmap_card_key": packet["roadmap_card_key"],
        "decision": packet["decision"],
        "artifact_type": detail["artifact_type"],
        "title": detail["title"],
        "artifact_summary": detail["artifact_summary"],
        "acceptance_status": "hold",
        "acceptance_label": "HOLD",
        "blocking_status": "blocked",
        "office_evidence_status": "missing",
        "visual_evidence_status": "missing",
        "acceptance_checklist": _acceptance_checklist(),
        "evidence_source_bundle": bundle,
        "evidence_source_bundle_digest": canonical_digest(bundle),
        "revision": 1,
        "can_auto_accept": False,
        "can_auto_execute": False,
        "can_auto_approve_release": False,
        "requires_human_evidence_review": True,
        "production_status": "not_authorized",
        "release_impact": "none",
        "seed_managed": True,
    }


def artifact_acceptance_definitions() -> list[dict[str, Any]]:
    """Build exactly four HOLD-only review templates from 2.10.1 packets."""

    definitions: list[dict[str, Any]] = []
    for packet in context_packet_definitions():
        definition = _artifact_without_digest(packet)
        definition["revision_digest"] = canonical_digest(definition)
        definitions.append(definition)
    return definitions


def artifact_acceptance_catalog_digest() -> str:
    return canonical_digest(
        {
            "artifact_acceptance_version": ARTIFACT_ACCEPTANCE_VERSION,
            "source_catalog_version": CATALOG_VERSION,
            "context_packet_catalog_digest": context_packet_catalog_digest(),
            "instruction_evidence": instruction_evidence(),
            "artifacts": artifact_acceptance_definitions(),
        }
    )


def artifact_acceptance_governance() -> dict[str, Any]:
    return {
        "instruction_kind": "user_instruction",
        "actor_identity_status": "unverified",
        "scope": "artifact_acceptance_definition_only",
        "artifact_definitions_require_explicit_initialization": True,
        "requires_persisted_decision_context_packets": True,
        "missing_office_or_visual_evidence_results_in_hold": True,
        "no_external_office_file_processing": True,
        "no_visual_render_validation_claim": True,
        "can_auto_accept": False,
        "can_auto_execute": False,
        "can_auto_approve_release": False,
        "requires_human_evidence_review": True,
        "release_gate_mutated": False,
        "production_status": "not_authorized",
        "note": "2.10.2 只固化可复核的验收草案和修订差异。Office 或视觉证据缺失时必须保持 HOLD/blocked，且不会自动验收、执行或改变发布门禁。",
    }


def _initial_revision_snapshot(definition: dict[str, Any]) -> dict[str, Any]:
    return {
        key: deepcopy(value)
        for key, value in definition.items()
        if key not in {"revision_digest", "acceptance_label"}
    }


def _flatten(payload: Any, prefix: str = "") -> dict[str, Any]:
    """Make a deterministic leaf map for a field-level review diff."""

    if isinstance(payload, dict):
        flattened: dict[str, Any] = {}
        for key in sorted(payload):
            child_prefix = f"{prefix}.{key}" if prefix else key
            flattened.update(_flatten(payload[key], child_prefix))
        return flattened
    if isinstance(payload, list):
        flattened = {}
        for index, value in enumerate(payload):
            flattened.update(_flatten(value, f"{prefix}[{index}]"))
        return flattened
    return {prefix: deepcopy(payload)}


def field_level_revision_diff(previous: dict[str, Any] | None, current: dict[str, Any]) -> dict[str, Any]:
    """Return values, rather than a prose claim, for reviewer comparison."""

    previous_flat = _flatten(previous or {})
    current_flat = _flatten(current)
    changed_fields: list[dict[str, Any]] = []
    for field in sorted(set(previous_flat) | set(current_flat)):
        before = previous_flat.get(field)
        after = current_flat.get(field)
        if before == after:
            continue
        changed_fields.append(
            {
                "field": field,
                "before": before,
                "after": after,
                "change_type": "added" if field not in previous_flat else "removed" if field not in current_flat else "modified",
            }
        )
    return {
        "from_revision": (previous or {}).get("revision") if previous else None,
        "to_revision": current.get("revision"),
        "changed_fields": changed_fields,
        "auto_acceptance_forbidden": True,
        "release_gate_mutated": False,
    }


def preview_artifact_acceptance() -> dict[str, Any]:
    """Return deterministic HOLD-only templates without a database operation."""

    catalog_digest = artifact_acceptance_catalog_digest()
    artifacts = deepcopy(artifact_acceptance_definitions())
    for artifact in artifacts:
        snapshot = _initial_revision_snapshot(artifact)
        artifact["artifact_acceptance_catalog_digest"] = catalog_digest
        artifact["revisions"] = []
        artifact["initial_field_level_diff"] = field_level_revision_diff(None, snapshot)
    return {
        "artifact_acceptance_version": ARTIFACT_ACCEPTANCE_VERSION,
        "source_catalog_version": CATALOG_VERSION,
        "catalog_digest": catalog_digest,
        "context_packet_catalog_digest": context_packet_catalog_digest(),
        "read_only": True,
        "initialized": False,
        "persistent_snapshot_digest": None,
        "instruction_evidence": instruction_evidence(),
        "governance": artifact_acceptance_governance(),
        "artifacts": artifacts,
        "initialization_audit": None,
    }
