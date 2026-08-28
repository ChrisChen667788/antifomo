import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CompetitiveIntelligenceWorkspace } from "@/components/competitive-intelligence/competitive-intelligence-workspace";
import type { ApiProductStrategyCompetitiveLandscapePreview } from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  getCompetitiveLandscapePreview: vi.fn(),
  getCompetitiveLandscape: vi.fn(),
  seedCompetitiveLandscape: vi.fn(),
}));

vi.mock("@/lib/api", async () => ({
  getCompetitiveLandscapePreview: apiMock.getCompetitiveLandscapePreview,
  getCompetitiveLandscape: apiMock.getCompetitiveLandscape,
  seedCompetitiveLandscape: apiMock.seedCompetitiveLandscape,
}));

vi.mock("@/components/competitive-intelligence/competitive-decision-context-packets", () => ({
  CompetitiveDecisionContextPackets: () => <div data-testid="competitive-decision-context-packets" />,
}));

vi.mock("@/components/competitive-intelligence/competitive-artifact-acceptance", () => ({
  CompetitiveArtifactAcceptance: () => <div data-testid="competitive-artifact-acceptance" />,
}));

const previewFixture: ApiProductStrategyCompetitiveLandscapePreview = {
  catalog_version: "2.10.0",
  catalog_digest: "a".repeat(64),
  observed_at: "2026-08-28T00:00:00Z",
  expires_at: "2026-10-12T00:00:00Z",
  read_only: true,
  initialized: false,
  persistent_snapshot_digest: null,
  governance: {
    evidence_tier: "vendor_claim",
    evidence_status: "vendor_claim_unverified",
    vendor_claim_is_not_independent_verification: true,
    can_auto_approve_roadmap: false,
    can_auto_approve_release: false,
    release_gate_mutated: false,
    note: "厂商声明不是独立验证。",
  },
  products: [
    {
      catalog_key: "workbuddy-official",
      product_key: "workbuddy",
      vendor: "腾讯",
      product_name: "WorkBuddy",
      source_title: "WorkBuddy 官方产品页",
      source_url: "https://example.com/workbuddy",
      source_kind: "official_product_page",
      source_digest: "b".repeat(64),
      observed_at: "2026-08-28T00:00:00Z",
      expires_at: "2026-10-12T00:00:00Z",
      evidence: {
        tier: "vendor_claim",
        status: "vendor_claim_unverified",
        recorded_status: "vendor_claim_unverified",
        vendor_claim_is_not_independent_verification: true,
      },
      vendor_claim: "公开产品页说明任务规划、工具执行与成果交付。",
      claimed_capabilities: ["任务规划", "成果交付"],
      local_implementation: { status: "implemented", notes: "本地策略台账会隔离实现。" },
      local_release: { status: "not_evaluated", notes: "竞品声明不构成发布证据。" },
      seed_managed: true,
      created_at: null,
      updated_at: null,
    },
  ],
  roadmap_cards: [
    {
      card_key: "competitive-observatory",
      product_key: "workbuddy",
      title: "竞品能力证据台账",
      decision: "build",
      status: "proposed",
      rationale: "竞品观察不可追溯，应保留来源和审批边界。",
      source_catalog_keys: ["workbuddy:official-product"],
      source_digest: "b".repeat(64),
      observed_at: "2026-08-28T00:00:00Z",
      expires_at: "2026-10-12T00:00:00Z",
      evidence: {
        tier: "vendor_claim",
        status: "vendor_claim_unverified",
        recorded_status: "vendor_claim_unverified",
        vendor_claim_is_not_independent_verification: true,
      },
      acceptance_criteria: ["每个主张有官方来源。"],
      module_targets: ["product_strategy"],
      approval_status: "proposed",
      release_impact: "不改变 release gate。",
      can_auto_approve_roadmap: false,
      can_auto_approve_release: false,
      seed_managed: true,
      created_at: null,
      updated_at: null,
    },
  ],
};

describe("CompetitiveIntelligenceWorkspace", () => {
  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  beforeEach(() => {
    apiMock.getCompetitiveLandscapePreview.mockReset();
    apiMock.getCompetitiveLandscape.mockReset();
    apiMock.seedCompetitiveLandscape.mockReset();
    vi.stubGlobal("confirm", vi.fn(() => true));
  });

  it("renders source boundaries and proposed roadmap cards from the read-only preview", async () => {
    apiMock.getCompetitiveLandscapePreview.mockResolvedValue(previewFixture);
    apiMock.getCompetitiveLandscape.mockResolvedValue(previewFixture);

    render(<CompetitiveIntelligenceWorkspace />);

    expect(await screen.findByText("竞品能力证据台账")).toBeInTheDocument();
    expect(screen.getByTestId("competitive-intelligence-workspace")).toBeInTheDocument();
    expect(screen.getByText("WorkBuddy")).toBeInTheDocument();
    expect(screen.getByText("厂商公开声明不等于独立验证。来源过期会标为已过期，不可读或缺失时会标为未知；路线图卡不能自动批准，也不会改变既有 `baseline_hybrid` 或 release-readiness 的 `blocked` 状态。")).toBeInTheDocument();
    expect(screen.getByText("竞品能力证据台账", { selector: "h4" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "初始化台账" })).toBeInTheDocument();
  });

  it("initializes the persisted ledger only after explicit confirmation", async () => {
    apiMock.getCompetitiveLandscapePreview.mockResolvedValue(previewFixture);
    apiMock.getCompetitiveLandscape.mockResolvedValue(previewFixture);
    apiMock.seedCompetitiveLandscape.mockResolvedValue({
      ...previewFixture,
      initialized: true,
      persistent_snapshot_digest: "c".repeat(64),
      seed: {
        sources: { created: 1, updated: 0, preserved_human: 0 },
        roadmap_cards: { created: 1, updated: 0, preserved_human: 0 },
      },
    });

    render(<CompetitiveIntelligenceWorkspace />);
    fireEvent.click(await screen.findByRole("button", { name: "初始化台账" }));

    expect(apiMock.seedCompetitiveLandscape).toHaveBeenCalledOnce();
    expect(await screen.findByText("已初始化本地台账")).toBeInTheDocument();
  });
});
