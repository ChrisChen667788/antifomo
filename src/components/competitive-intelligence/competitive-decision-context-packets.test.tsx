import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CompetitiveDecisionContextPackets } from "@/components/competitive-intelligence/competitive-decision-context-packets";
import type {
  ApiProductStrategyDecisionContextApprovalEvidence,
  ApiProductStrategyDecisionContextDecision,
  ApiProductStrategyDecisionContextPacket,
  ApiProductStrategyDecisionContextPackets,
} from "@/lib/api/type-contracts/competitive-intelligence";

const apiMock = vi.hoisted(() => ({
  getDecisionContextPacketsPreview: vi.fn(),
  getDecisionContextPackets: vi.fn(),
  initializeDecisionContextPackets: vi.fn(),
}));

vi.mock("@/lib/api/competitive-intelligence", () => ({
  getDecisionContextPacketsPreview: apiMock.getDecisionContextPacketsPreview,
  getDecisionContextPackets: apiMock.getDecisionContextPackets,
  initializeDecisionContextPackets: apiMock.initializeDecisionContextPackets,
}));

const approvalEvidence: ApiProductStrategyDecisionContextApprovalEvidence = {
  kind: "user_instruction",
  actor_identity_status: "unverified",
  scope: "product_strategy_only",
  approval_kind: "explicit_product_owner_user_instruction",
  owner: {
    kind: "unnamed_product_owner_user_instruction",
    named_individual: false,
    display_name: null,
  },
  instruction: "用户批准 build / integrate / defer 路线进入上下文包。",
  recorded_at: "2026-08-28T08:00:00Z",
  authorization_scope: "initialize_reviewable_decision_context_packets_only",
  does_not_approve_release: true,
  does_not_authorize_execution: true,
  requires_human_change_approval: true,
};

function makePacket(
  cardKey: string,
  title: string,
  decision: ApiProductStrategyDecisionContextDecision,
): ApiProductStrategyDecisionContextPacket {
  return {
    id: null,
    packet_key: `anti-fomo:2.10.1:${cardKey}:context`,
    project_scope: "anti-fomo",
    source_catalog_version: "2.10.0",
    packet_catalog_digest: "a".repeat(64),
    roadmap_card_key: cardKey,
    product_key: cardKey.split(":")[0],
    decision,
    decision_approval_status: "approved_by_explicit_product_owner_instruction",
    title,
    problem_statement: "保留可审查的产品决策上下文。",
    rationale: "竞品观察必须绑定来源、约束和人工变更门禁。",
    source_catalog_keys: ["workbuddy-official"],
    source_digests: ["b".repeat(64)],
    source_references: [
      {
        catalog_key: "workbuddy-official",
        source_digest: "b".repeat(64),
        observed_at: "2026-08-28T00:00:00Z",
        expires_at: "2026-10-12T00:00:00Z",
        evidence: {
          tier: "vendor_claim",
          status: "vendor_claim_unverified",
          recorded_status: "vendor_claim_unverified",
          vendor_claim_is_not_independent_verification: true,
        },
      },
    ],
    assumptions: ["只记录官方公开资料。"],
    constraints: ["不构成独立产品验证。"],
    module_targets: ["product_strategy"],
    approval_evidence: approvalEvidence,
    retention_until: "2027-08-28T00:00:00Z",
    revision: 1,
    revision_digest: "c".repeat(64),
    status: "approved_for_context",
    can_auto_execute: false,
    can_auto_approve_release: false,
    requires_human_change_approval: true,
    production_status: "not_authorized",
    release_impact: "none",
    seed_managed: true,
    created_at: null,
    updated_at: null,
    revisions: [],
  };
}

const previewFixture: ApiProductStrategyDecisionContextPackets = {
  context_packet_version: "2.10.1",
  source_catalog_version: "2.10.0",
  catalog_digest: "d".repeat(64),
  read_only: true,
  initialized: false,
  persistent_snapshot_digest: null,
  approval_evidence: approvalEvidence,
  governance: {
    approval_kind: "user_instruction",
    actor_identity_status: "unverified",
    scope: "product_strategy_only",
    context_packets_require_explicit_initialization: true,
    decision_authorization_is_not_execution_authorization: true,
    decision_authorization_is_not_release_approval: true,
    can_auto_execute: false,
    can_auto_approve_release: false,
    requires_human_change_approval: true,
    release_gate_mutated: false,
    production_status: "not_authorized",
    note: "用户指令仅用于建立可复核决策上下文。",
  },
  packets: [
    makePacket("workbuddy:integrate", "可审计的外部任务结果上下文", "integrate"),
    makePacket("qwen_work:build", "可编辑且可追溯的交付物", "build"),
    makePacket("langhub:build", "项目上下文和变更预览", "build"),
    makePacket("baidu_dumate:defer", "受控自动化暂缓", "defer"),
  ],
  excluded_cards: [
    {
      card_key: "trae:explicitly_not_copy",
      product_key: "trae",
      decision: "explicitly_not_copy",
      title: "不复制 AI IDE 自主改写能力",
      rationale: "AI IDE 的代码写入、终端执行与仓库代理超出 Anti-FOMO 的产品边界；竞品存在不构成扩展授权。",
      exclusion_reason: "只有 build、integrate 和 defer 决策被明确批准进入 2.10.1 上下文包。",
      can_auto_execute: false,
      can_auto_approve_release: false,
    },
    {
      card_key: "tencent_qclaw:explicitly_not_copy",
      product_key: "tencent_qclaw",
      decision: "explicitly_not_copy",
      title: "不复制即时通信远程设备执行",
      rationale: "远程消息触发本地设备动作具有高权限和提示注入风险；该能力与 Anti-FOMO 当前受控产品边界不相容。",
      exclusion_reason: "只有 build、integrate 和 defer 决策被明确批准进入 2.10.1 上下文包。",
      can_auto_execute: false,
      can_auto_approve_release: false,
    },
  ],
  initialization_audit: null,
};

describe("CompetitiveDecisionContextPackets", () => {
  beforeEach(() => {
    apiMock.getDecisionContextPacketsPreview.mockReset();
    apiMock.getDecisionContextPackets.mockReset();
    apiMock.initializeDecisionContextPackets.mockReset();
    vi.stubGlobal("confirm", vi.fn(() => true));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders four approved decision contexts and two explicitly-not-copy exclusions without inventing an approver", async () => {
    apiMock.getDecisionContextPacketsPreview.mockResolvedValue(previewFixture);
    apiMock.getDecisionContextPackets.mockResolvedValue(previewFixture);

    render(<CompetitiveDecisionContextPackets />);

    expect(await screen.findByTestId("competitive-decision-context-packets")).toBeInTheDocument();
    expect(screen.getByText("4 项")).toBeInTheDocument();
    expect(screen.getByText("2 项")).toBeInTheDocument();
    expect(screen.getAllByText(/未伪造具名审批人；仅记录用户指令作为上下文依据。/)).not.toHaveLength(0);
    expect(screen.getByText("不复制 AI IDE 自主改写能力")).toBeInTheDocument();
    expect(screen.getByText("不复制即时通信远程设备执行")).toBeInTheDocument();
    expect(screen.getAllByText(/不可自动执行/)).not.toHaveLength(0);
    expect(screen.getByRole("button", { name: "显式确认并初始化" })).toBeInTheDocument();
  });

  it("initializes only after explicit confirmation and still surfaces the non-execution boundary", async () => {
    apiMock.getDecisionContextPacketsPreview.mockResolvedValue(previewFixture);
    apiMock.getDecisionContextPackets.mockResolvedValue(previewFixture);
    apiMock.initializeDecisionContextPackets.mockResolvedValue({
      ...previewFixture,
      initialized: true,
      persistent_snapshot_digest: "6".repeat(64),
      initialization_audit: {
        id: "audit-1",
        event_key: "anti-fomo:2.10.1:explicit-product-owner-context-approval",
        project_scope: "anti-fomo",
        event_type: "explicit_user_instruction_context_packet_initialization",
        approval_evidence: approvalEvidence,
        allowed_decisions: ["build", "integrate", "defer"],
        excluded_card_keys: ["trae:explicitly_not_copy", "tencent_qclaw:explicitly_not_copy"],
        source_catalog_version: "2.10.0",
        packet_catalog_digest: "d".repeat(64),
        event_digest: "7".repeat(64),
        can_auto_execute: false,
        can_auto_approve_release: false,
        release_gate_mutated: false,
        created_at: "2026-08-28T08:00:00Z",
      },
      initialization: {
        packets: { created: 4, existing_seed_managed: 0, preserved_human: 0 },
        revisions: { created: 4, existing: 0, preserved_human: 0 },
        approval_audit: { created: 1, existing: 0 },
      },
    });

    render(<CompetitiveDecisionContextPackets />);
    fireEvent.click(await screen.findByRole("button", { name: "显式确认并初始化" }));

    expect(apiMock.initializeDecisionContextPackets).toHaveBeenCalledOnce();
    expect(await screen.findByText("已初始化本地上下文包")).toBeInTheDocument();
    expect(screen.getByText("初始化记录：新建 4 个上下文包，已存在 seed 管理包 0 个，保留人工包 0 个；新增 revision 4 条，审批审计新增 1 条。")).toBeInTheDocument();
    expect(screen.getAllByText(/不可自动批准发布/)).not.toHaveLength(0);
  });
});
