from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
import hashlib
import json
from typing import Any


CATALOG_VERSION = "2.10.0"
OBSERVED_AT = datetime(2026, 8, 28, tzinfo=UTC)
EXPIRES_AT = datetime(2026, 11, 26, tzinfo=UTC)


def canonical_digest(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def iso(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def effective_evidence_status(
    recorded_status: str,
    expires_at: datetime | str,
    *,
    now: datetime | None = None,
) -> str:
    if isinstance(expires_at, str):
        expiry = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
    else:
        expiry = expires_at
    expiry = expiry.replace(tzinfo=UTC) if expiry.tzinfo is None else expiry.astimezone(UTC)
    current = now or datetime.now(UTC)
    current = current.replace(tzinfo=UTC) if current.tzinfo is None else current.astimezone(UTC)
    return "stale" if current > expiry else recorded_status


def _source(
    *,
    product_key: str,
    vendor: str,
    product_name: str,
    source_title: str,
    source_url: str,
    vendor_claim: str,
    claimed_capabilities: list[str],
    local_implementation_status: str,
    local_implementation_notes: str,
) -> dict[str, Any]:
    catalog_key = f"{product_key}:official-product"
    evidence = {
        "catalog_key": catalog_key,
        "product_key": product_key,
        "vendor": vendor,
        "product_name": product_name,
        "source_title": source_title,
        "source_url": source_url,
        "source_kind": "official_product_page",
        "vendor_claim": vendor_claim,
        "claimed_capabilities": claimed_capabilities,
        "observed_at": iso(OBSERVED_AT),
        "expires_at": iso(EXPIRES_AT),
        "evidence_tier": "vendor_claim",
        "evidence_status": "vendor_claim_unverified",
    }
    return {
        **evidence,
        "source_digest": canonical_digest(evidence),
        "local_implementation": {
            "status": local_implementation_status,
            "notes": local_implementation_notes,
        },
        "local_release": {
            "status": "not_evaluated",
            "notes": "竞品公开材料不构成 Anti-FOMO 的实现、验收或发布证据，也不会改变现有发布门禁。",
        },
    }


CATALOG_SOURCES: tuple[dict[str, Any], ...] = (
    _source(
        product_key="workbuddy",
        vendor="腾讯",
        product_name="WorkBuddy",
        source_title="腾讯云 WorkBuddy 产品页",
        source_url="https://intl.cloud.tencent.com/zh/products/workbuddy",
        vendor_claim="厂商公开材料将 WorkBuddy 描述为面向办公场景的 AI Agent 工作台，提供任务编排与办公生态连接能力。",
        claimed_capabilities=["AI Agent 工作台", "任务编排", "办公工具连接", "结果交付"],
        local_implementation_status="partial_boundary_only",
        local_implementation_notes="本地已有 WorkBuddy-compatible bridge 边界；这不等同于已验证的官方集成或能力对等。",
    ),
    _source(
        product_key="trae",
        vendor="TRAE",
        product_name="TRAE",
        source_title="TRAE 官方文档",
        source_url="https://docs.trae.cn/",
        vendor_claim="厂商公开材料将 TRAE 描述为 AI 原生开发环境，可基于代码仓库上下文协助开发任务。",
        claimed_capabilities=["代码仓库上下文", "AI 编程协作", "开发工作流"],
        local_implementation_status="not_implemented",
        local_implementation_notes="Anti-FOMO 当前不提供 AI IDE 或自动写入用户代码工作区的能力。",
    ),
    _source(
        product_key="qwen_work",
        vendor="阿里巴巴",
        product_name="千问办公（QwenWork）",
        source_title="千问办公简介",
        source_url="https://qwenwork.cn/docs/product-introduction",
        vendor_claim="厂商公开材料将千问办公描述为一站式 AI 办公平台，可通过自然语言完成文档、数据和多类办公产物交付，并接入钉钉生态。",
        claimed_capabilities=["办公产物交付", "文件处理", "数据分析", "钉钉生态"],
        local_implementation_status="not_implemented",
        local_implementation_notes="该目录尚未验证千问办公连接器、钉钉权限模型或办公产物的能力对等。",
    ),
    _source(
        product_key="langhub",
        vendor="Langhub",
        product_name="Langhub",
        source_title="Langhub 官方产品页",
        source_url="https://www.langhub.cn/?locale=zh",
        vendor_claim="厂商公开材料将 Langhub 描述为持续学习工作方式的上下文工作区，强调上下文、工具链、意图与校验对齐。",
        claimed_capabilities=["持久上下文", "工具链对齐", "计划优先", "变更预览与回滚"],
        local_implementation_status="not_implemented",
        local_implementation_notes="该目录不会把上下文记忆主张视为本地的已实现、已同意或已验证能力。",
    ),
    _source(
        product_key="baidu_dumate",
        vendor="百度智能云",
        product_name="DuMate",
        source_title="百度 DuMate 产品文档",
        source_url="https://cloud.baidu.com/doc/Dumate/index.html",
        vendor_claim="厂商公开材料将 DuMate 描述为面向桌面办公的 AI 智能体，可在本地安全运行并处理文件、数据和办公自动化任务。",
        claimed_capabilities=["桌面智能体", "本地文件处理", "数据处理", "办公自动化"],
        local_implementation_status="not_implemented",
        local_implementation_notes="Anti-FOMO 当前没有由该目录批准的桌面控制、文件写入或自动化执行能力。",
    ),
    _source(
        product_key="tencent_qclaw",
        vendor="腾讯电脑管家 / 腾讯云",
        product_name="腾讯 QClaw（腾讯兔子）",
        source_title="腾讯云 QClaw 产品文档",
        source_url="https://intl.cloud.tencent.com/zh/document/product/1300/81043",
        vendor_claim="厂商公开材料将 QClaw 描述为基于 OpenClaw 生态的本地 AI Agent，可通过即时通信入口远程发起办公、创作和开发任务。",
        claimed_capabilities=["本地 AI Agent", "即时通信入口", "远程任务", "自定义模型"],
        local_implementation_status="not_implemented",
        local_implementation_notes="Anti-FOMO 当前不支持通过即时通信远程执行本地设备操作，也未验证 QClaw 的产品能力。",
    ),
)


def _card(
    *,
    product_key: str,
    title: str,
    decision: str,
    rationale: str,
    acceptance_criteria: list[str],
    module_targets: list[str],
) -> dict[str, Any]:
    source = next(row for row in CATALOG_SOURCES if row["product_key"] == product_key)
    return {
        "card_key": f"{product_key}:{decision}",
        "product_key": product_key,
        "title": title,
        "decision": decision,
        "status": "proposed",
        "rationale": rationale,
        "source_catalog_keys": [source["catalog_key"]],
        "source_digest": source["source_digest"],
        "observed_at": iso(OBSERVED_AT),
        "expires_at": iso(EXPIRES_AT),
        "evidence_tier": "vendor_claim",
        "evidence_status": "vendor_claim_unverified",
        "acceptance_criteria": acceptance_criteria,
        "module_targets": module_targets,
        "approval_status": "human_review_required",
        "release_impact": "none",
        "can_auto_approve_roadmap": False,
        "can_auto_approve_release": False,
    }


CATALOG_ROADMAP_CARDS: tuple[dict[str, Any], ...] = (
    _card(
        product_key="workbuddy",
        title="受控的外部结果回传边界",
        decision="integrate",
        rationale="借鉴任务结果回传的产品闭环，但仅以显式同意、可审计的集成边界推进，不能据厂商材料推导官方互通。",
        acceptance_criteria=[
            "回传目标必须来自显式 allowlist，且请求与结果均有可审计 digest。",
            "每个外部结果均保留来源、artifact lineage 与人工复核入口。",
            "任何回传失败均 fail closed，不自动执行后续外部动作。",
        ],
        module_targets=["focus_assistant", "workbuddy_adapter", "product_strategy"],
    ),
    _card(
        product_key="trae",
        title="不复制 AI IDE 自主改写能力",
        decision="explicitly_not_copy",
        rationale="AI IDE 的代码写入、终端执行与仓库代理超出 Anti-FOMO 的产品边界；竞品存在不构成扩展授权。",
        acceptance_criteria=[
            "2.10.0 不新增代码工作区自动写入或终端命令执行能力。",
            "任何未来开发者工具提案必须拥有独立威胁建模、权限设计和人工验收。",
        ],
        module_targets=["product_strategy", "out_of_scope:developer_ide"],
    ),
    _card(
        product_key="qwen_work",
        title="可编辑交付物与来源血缘",
        decision="build",
        rationale="把办公产物视作可继续编辑、可追溯的工作成果；不复制或声称接入千问办公和钉钉生态。",
        acceptance_criteria=[
            "每个生成交付物记录输入、版本、来源和人工修改历史。",
            "导出前显示不可验证主张、缺失来源和待人工确认项。",
            "不引入未经明确授权的第三方文件或企业协作数据读取。",
        ],
        module_targets=["session_artifact_service", "delivery/document_compilers", "product_strategy"],
    ),
    _card(
        product_key="langhub",
        title="经同意的项目上下文与变更预览",
        decision="build",
        rationale="借鉴上下文和变更可见性，但将记忆写入、权限与回滚明确置于用户同意和可审计控制之下。",
        acceptance_criteria=[
            "上下文写入需有项目范围、来源和保留期限。",
            "任何建议性变更先显示 preview，需人工确认后才可落库。",
            "支持按项目撤销，且撤销记录不被后续自动 seed 覆盖。",
        ],
        module_targets=["knowledge", "preferences", "product_strategy"],
    ),
    _card(
        product_key="baidu_dumate",
        title="桌面自动化能力暂缓",
        decision="defer",
        rationale="本地文件与桌面操作的价值需要先通过权限、沙箱、审计和回滚模型验证，不能由厂商能力主张直接进入路线图。",
        acceptance_criteria=[
            "在独立安全设计通过前，不新增桌面控制或任意文件写入。",
            "如重新评估，必须先完成最小权限、沙箱、操作日志和人工确认验收。",
        ],
        module_targets=["product_strategy", "future:desktop_agent_safety"],
    ),
    _card(
        product_key="tencent_qclaw",
        title="不复制即时通信远程设备执行",
        decision="explicitly_not_copy",
        rationale="远程消息触发本地设备动作具有高权限和提示注入风险；该能力与 Anti-FOMO 当前受控产品边界不相容。",
        acceptance_criteria=[
            "即时通信输入不得直接授权本地设备操作。",
            "任何未来远程控制提案必须在独立安全评审、权限分离和撤销演练后再讨论。",
        ],
        module_targets=["focus_assistant", "product_strategy", "future:remote_action_security"],
    ),
)


def catalog_digest() -> str:
    return canonical_digest(
        {
            "catalog_version": CATALOG_VERSION,
            "sources": CATALOG_SOURCES,
            "roadmap_cards": CATALOG_ROADMAP_CARDS,
        }
    )


def catalog_governance() -> dict[str, Any]:
    return {
        "evidence_tier": "vendor_claim",
        "evidence_status": "vendor_claim_unverified",
        "vendor_claim_is_not_independent_verification": True,
        "can_auto_approve_roadmap": False,
        "can_auto_approve_release": False,
        "release_gate_mutated": False,
        "note": "本目录是产品情报输入，不是独立验证、路线图批准或发布批准机制。",
    }


def _preview_source(definition: dict[str, Any]) -> dict[str, Any]:
    row = deepcopy(definition)
    row["evidence"] = {
        "tier": row["evidence_tier"],
        "status": effective_evidence_status(row["evidence_status"], row["expires_at"]),
        "recorded_status": row["evidence_status"],
        "vendor_claim_is_not_independent_verification": True,
    }
    return row


def _preview_roadmap_card(definition: dict[str, Any]) -> dict[str, Any]:
    row = deepcopy(definition)
    row["evidence"] = {
        "tier": row["evidence_tier"],
        "status": effective_evidence_status(row["evidence_status"], row["expires_at"]),
        "recorded_status": row["evidence_status"],
        "vendor_claim_is_not_independent_verification": True,
    }
    return row


def preview_competitive_landscape() -> dict[str, Any]:
    """Return a deterministic, database-free official-source catalog preview."""

    return {
        "catalog_version": CATALOG_VERSION,
        "catalog_digest": catalog_digest(),
        "observed_at": iso(OBSERVED_AT),
        "expires_at": iso(EXPIRES_AT),
        "read_only": True,
        "initialized": False,
        "persistent_snapshot_digest": None,
        "governance": catalog_governance(),
        "products": [_preview_source(row) for row in CATALOG_SOURCES],
        "roadmap_cards": [_preview_roadmap_card(row) for row in CATALOG_ROADMAP_CARDS],
    }


def catalog_sources() -> list[dict[str, Any]]:
    return deepcopy(list(CATALOG_SOURCES))


def catalog_roadmap_cards() -> list[dict[str, Any]]:
    return deepcopy(list(CATALOG_ROADMAP_CARDS))
