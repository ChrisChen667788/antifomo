import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CompetitiveIterationProgram } from "@/components/competitive-intelligence/competitive-iteration-program";
import type { ApiProductStrategyIterationProgramPreview } from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  getIterationProgramPreview: vi.fn(),
  getIterationProgram: vi.fn(),
  initializeIterationProgram: vi.fn(),
}));

vi.mock("@/lib/api", () => apiMock);

const diff = {
  from_revision: null,
  to_revision: 1,
  changed_fields: [{ field: "title", before: null, after: "来源变更复核", change_type: "added" as const }],
  auto_acceptance_forbidden: true as const,
  release_gate_mutated: false as const,
};

const fixture: ApiProductStrategyIterationProgramPreview = {
  iteration_program_version: "2.10.3-2.11.7",
  observed_at: "2026-08-31T00:00:00Z",
  expires_at: "2026-09-14T00:00:00Z",
  program_digest: "a".repeat(64),
  read_only: true,
  initialized: false,
  persistent_snapshot_digest: null,
  instruction_evidence: {
    kind: "user_instruction",
    actor_identity_status: "unverified",
    scope: "product_strategy_iteration_program_only",
    instruction: "完成后续15个版本",
    recorded_at: "2026-08-31T00:00:00Z",
    authorization_scope: "仅产品策略控制面",
    does_not_approve_artifact_acceptance: true,
    does_not_authorize_execution: true,
    does_not_approve_release: true,
    requires_human_evidence_review: true,
  },
  governance: {
    instruction_kind: "user_instruction",
    actor_identity_status: "unverified",
    scope: "product_strategy_iteration_program_only",
    iterations_require_explicit_initialization: true,
    vendor_claim_is_not_independent_verification: true,
    source_change_requires_human_review: true,
    office_and_visual_acceptance_remain_gated: true,
    can_auto_accept: false,
    can_auto_execute: false,
    can_auto_approve_release: false,
    release_gate_mutated: false,
    production_status: "not_authorized",
    note: "控制面不构成生产授权。",
  },
  agent_sources: [{
    catalog_key: "openai_codex:official-agent-source",
    product_key: "openai_codex",
    vendor: "OpenAI",
    product_name: "Codex",
    source_title: "Codex 官方产品页",
    source_url: "https://openai.com/codex/",
    source_kind: "official_product_or_documentation",
    source_digest: "b".repeat(64),
    observed_at: "2026-08-31T00:00:00Z",
    expires_at: "2026-09-14T00:00:00Z",
    evidence: {
      tier: "vendor_claim",
      status: "vendor_claim_unverified",
      recorded_status: "vendor_claim_unverified",
      vendor_claim_is_not_independent_verification: true,
    },
    vendor_claim: "官方产品页描述并行代理工作流。",
    claimed_capabilities: ["并行代理工作流"],
    current_model_signal: "GPT-5.6 Sol / GPT-5.3-Codex",
    lesson: "任务边界应可审查。",
    anti_fomo_decision: "整合上下文与变更证据，不复制代码执行。",
  }],
  iterations: [{
    id: null,
    iteration_key: "2.10.4:source-change-review",
    project_scope: "anti-fomo",
    version: "2.10.4",
    sequence: 2,
    title: "产品策略来源变更复核",
    workstream: "competitive_evidence",
    decision: "build",
    purpose: "将变化转为复核队列。",
    scope_boundary: "不自动改写路线图。",
    implementation_status: "planning_control_plane_implemented",
    feature_implementation_status: "gated_or_pending_evidence",
    external_evidence_status: "pending",
    acceptance_status: "hold",
    dependencies: ["2.10.0"],
    source_basis: ["官方来源"],
    delivery_artifacts: ["变更差异报告"],
    acceptance_criteria: ["变化只产生复核提示"],
    external_evidence_requirements: ["人工语义复核"],
    can_auto_accept: false,
    can_auto_execute: false,
    can_auto_approve_release: false,
    requires_human_evidence_review: true,
    production_status: "not_authorized",
    revision: 1,
    revision_digest: "c".repeat(64),
    seed_managed: true,
    created_at: null,
    updated_at: null,
    revisions: [],
    initial_field_level_diff: diff,
  }],
  initialization_audit: null,
};

describe("CompetitiveIterationProgram", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    apiMock.getIterationProgramPreview.mockReset();
    apiMock.getIterationProgram.mockReset();
    apiMock.initializeIterationProgram.mockReset();
    vi.stubGlobal("confirm", vi.fn(() => true));
  });

  it("renders vendor-claim boundaries and HOLD iteration status", async () => {
    apiMock.getIterationProgramPreview.mockResolvedValue(fixture);
    apiMock.getIterationProgram.mockResolvedValue(fixture);

    render(<CompetitiveIterationProgram />);

    expect(await screen.findByText("15 版本受治理迭代与 Agent 能力观察")).toBeInTheDocument();
    expect(screen.getByText("Codex")).toBeInTheDocument();
    expect(screen.getByText("产品策略来源变更复核")).toBeInTheDocument();
    expect(screen.getAllByText("HOLD").length).toBeGreaterThan(0);
    expect(screen.getByText(/不能自动执行、验收或发布/)).toBeInTheDocument();
  });

  it("requires confirmation before explicit initialization", async () => {
    apiMock.getIterationProgramPreview.mockResolvedValue(fixture);
    apiMock.getIterationProgram.mockResolvedValue(fixture);
    apiMock.initializeIterationProgram.mockResolvedValue({
      ...fixture,
      read_only: false,
      initialized: true,
      persistent_snapshot_digest: "d".repeat(64),
      initialization: {
        iterations: { created: 15 },
        revisions: { created: 15 },
        initialization_audit: { created: 1 },
      },
    });

    render(<CompetitiveIterationProgram />);
    fireEvent.click(await screen.findByRole("button", { name: "初始化 15 版本台账" }));

    expect(apiMock.initializeIterationProgram).toHaveBeenCalledOnce();
    expect(await screen.findByText("本地台账已初始化")).toBeInTheDocument();
  });
});
