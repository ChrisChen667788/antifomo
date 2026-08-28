from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from app.services.product_strategy.catalog import (
    CATALOG_VERSION,
    canonical_digest,
    catalog_roadmap_cards,
    catalog_sources,
    effective_evidence_status,
    iso,
)


CONTEXT_PACKET_VERSION = "2.10.1"
PROJECT_SCOPE = "anti-fomo"
APPROVAL_RECORDED_AT = datetime(2026, 8, 28, tzinfo=UTC)
RETENTION_UNTIL = datetime(2027, 8, 28, tzinfo=UTC)
ALLOWED_DECISIONS = frozenset({"build", "integrate", "defer"})
INITIALIZATION_EVENT_KEY = "anti-fomo:2.10.1:explicit-product-owner-context-approval"


def approval_evidence() -> dict[str, Any]:
    """The explicit user instruction is authorization for this context only.

    This intentionally contains no named individual.  It must never be read as
    a release approval, a production authorization, or permission to execute a
    downstream integration.
    """

    return {
        "kind": "user_instruction",
        "actor_identity_status": "unverified",
        "scope": "product_strategy_only",
        "approval_kind": "explicit_product_owner_user_instruction",
        "owner": {
            "kind": "unnamed_product_owner_user_instruction",
            "named_individual": False,
            "display_name": None,
        },
        "instruction": "默认先通过台账中的 build / integrate / defer 决策，直接进入 2.10.1 的“可复核决策上下文包”。",
        "recorded_at": iso(APPROVAL_RECORDED_AT),
        "authorization_scope": "initialize_reviewable_decision_context_packets_only",
        "does_not_approve_release": True,
        "does_not_authorize_execution": True,
        "requires_human_change_approval": True,
    }


PACKET_CONTEXT_BY_CARD_KEY: dict[str, dict[str, Any]] = {
    "workbuddy:integrate": {
        "problem_statement": "在不扩大外部执行权限的前提下，让用户可以复核外部任务结果的来源、回传边界和后续人工动作。",
        "assumptions": [
            "外部结果只在用户已明确允许的回传目标和项目范围内被记录。",
            "本上下文包不表示已验证 WorkBuddy 官方集成，也不产生任何外部请求。",
        ],
        "constraints": [
            "仅记录可审计的结果上下文；不自动执行回传、发送或后续外部动作。",
            "任何连接器、身份、allowlist 与凭据都必须在独立的人类审批后配置。",
        ],
    },
    "qwen_work:build": {
        "problem_statement": "将生成成果转化为可继续编辑、可追溯且能被人工复核的交付物，而不把竞品生态接入误认为已完成。",
        "assumptions": [
            "交付物血缘应记录输入、版本、来源和人工修改，而非只保留生成文本。",
            "本上下文包不读取第三方办公数据，也不宣称接入千问办公或钉钉。",
        ],
        "constraints": [
            "缺失来源、不可验证主张和待确认项必须在导出前可见。",
            "任何第三方文件或企业协作数据读取均需独立授权与最小权限设计。",
        ],
    },
    "langhub:build": {
        "problem_statement": "在项目范围内记录经过同意的上下文与变更预览，同时保证撤销、保留期限和人工确认可被审计。",
        "assumptions": [
            "项目上下文必须具有明确来源、项目边界和保留期限。",
            "本上下文包不是自动记忆写入、自动变更或竞品能力等价声明。",
        ],
        "constraints": [
            "任何建议性变更必须先展示 preview，并在人工确认后才可落库。",
            "撤销记录和人工管理状态不得被后续初始化覆盖。",
        ],
    },
    "baidu_dumate:defer": {
        "problem_statement": "在尚未完成权限、沙箱、审计和回滚设计前，防止桌面自动化或任意文件写入被提前实施。",
        "assumptions": [
            "桌面操作的潜在价值不构成现阶段执行授权。",
            "竞品公开材料不证明 Anti-FOMO 已具备安全、验收或生产条件。",
        ],
        "constraints": [
            "不得新增桌面控制、任意文件写入或自动化执行。",
            "若重新评估，须先完成最小权限、沙箱、操作日志和人工确认的独立设计与验收。",
        ],
    },
}


def _source_reference(source: dict[str, Any]) -> dict[str, Any]:
    return {
        "catalog_key": source["catalog_key"],
        "source_digest": source["source_digest"],
        "observed_at": source["observed_at"],
        "expires_at": source["expires_at"],
        "evidence": {
            "tier": source["evidence_tier"],
            "status": effective_evidence_status(source["evidence_status"], source["expires_at"]),
            "recorded_status": source["evidence_status"],
            "vendor_claim_is_not_independent_verification": True,
        },
    }


def _packet_without_digest(card: dict[str, Any], source_by_key: dict[str, dict[str, Any]]) -> dict[str, Any]:
    detail = PACKET_CONTEXT_BY_CARD_KEY.get(card["card_key"])
    if detail is None:
        raise ValueError(f"No 2.10.1 context-packet detail exists for {card['card_key']}.")

    source_references = [_source_reference(source_by_key[key]) for key in card["source_catalog_keys"]]
    packet_key = f"{PROJECT_SCOPE}:2.10.1:{card['card_key']}:context"
    return {
        "packet_key": packet_key,
        "project_scope": PROJECT_SCOPE,
        "roadmap_card_key": card["card_key"],
        "product_key": card["product_key"],
        "decision": card["decision"],
        "decision_approval_status": "approved_by_explicit_product_owner_instruction",
        "title": card["title"],
        "problem_statement": detail["problem_statement"],
        "rationale": card["rationale"],
        "source_catalog_keys": list(card["source_catalog_keys"]),
        "source_digests": [reference["source_digest"] for reference in source_references],
        "source_references": source_references,
        "assumptions": list(detail["assumptions"]),
        "constraints": [*detail["constraints"], *card["acceptance_criteria"]],
        "module_targets": list(card["module_targets"]),
        "approval_evidence": approval_evidence(),
        "retention_until": iso(RETENTION_UNTIL),
        "revision": 1,
        "status": "approved_for_context",
        "can_auto_execute": False,
        "can_auto_approve_release": False,
        "requires_human_change_approval": True,
        "production_status": "not_authorized",
        "release_impact": "none",
        "seed_managed": True,
    }


def context_packet_definitions() -> list[dict[str, Any]]:
    """Build the four allowed packets from the existing 2.10.0 card catalog."""

    source_by_key = {source["catalog_key"]: source for source in catalog_sources()}
    packets: list[dict[str, Any]] = []
    for card in catalog_roadmap_cards():
        if card["decision"] not in ALLOWED_DECISIONS:
            continue
        packet = _packet_without_digest(card, source_by_key)
        packet["revision_digest"] = canonical_digest(packet)
        packets.append(packet)
    return packets


def excluded_card_definitions() -> list[dict[str, Any]]:
    """Expose excluded decisions so the omission is reviewable, not silent."""

    excluded: list[dict[str, Any]] = []
    for card in catalog_roadmap_cards():
        if card["decision"] in ALLOWED_DECISIONS:
            continue
        excluded.append(
            {
                "card_key": card["card_key"],
                "product_key": card["product_key"],
                "decision": card["decision"],
                "title": card["title"],
                "rationale": card["rationale"],
                "exclusion_reason": "Only build, integrate, and defer decisions were explicitly approved for 2.10.1 context packets.",
                "can_auto_execute": False,
                "can_auto_approve_release": False,
            }
        )
    return excluded


def context_packet_catalog_digest() -> str:
    return canonical_digest(
        {
            "context_packet_version": CONTEXT_PACKET_VERSION,
            "source_catalog_version": CATALOG_VERSION,
            "approval_evidence": approval_evidence(),
            "packets": context_packet_definitions(),
            "excluded_cards": excluded_card_definitions(),
        }
    )


def context_packet_governance() -> dict[str, Any]:
    return {
        "approval_kind": "user_instruction",
        "actor_identity_status": "unverified",
        "scope": "product_strategy_only",
        "context_packets_require_explicit_initialization": True,
        "decision_authorization_is_not_execution_authorization": True,
        "decision_authorization_is_not_release_approval": True,
        "can_auto_execute": False,
        "can_auto_approve_release": False,
        "requires_human_change_approval": True,
        "release_gate_mutated": False,
        "production_status": "not_authorized",
        "note": "2.10.1 只把用户明确批准的产品决策固化为可复核上下文；它不会执行集成、变更生产状态或改变现有发布门禁。",
    }


def preview_decision_context_packets() -> dict[str, Any]:
    """Return a deterministic, database-free 2.10.1 initialization preview."""

    digest = context_packet_catalog_digest()
    packets = deepcopy(context_packet_definitions())
    for packet in packets:
        packet["source_catalog_version"] = CATALOG_VERSION
        packet["packet_catalog_digest"] = digest
        packet["revisions"] = []
    return {
        "context_packet_version": CONTEXT_PACKET_VERSION,
        "source_catalog_version": CATALOG_VERSION,
        "catalog_digest": digest,
        "read_only": True,
        "initialized": False,
        "persistent_snapshot_digest": None,
        "approval_evidence": approval_evidence(),
        "governance": context_packet_governance(),
        "packets": packets,
        "excluded_cards": deepcopy(excluded_card_definitions()),
        "initialization_audit": None,
    }
