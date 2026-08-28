import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CompetitiveArtifactAcceptance } from "@/components/competitive-intelligence/competitive-artifact-acceptance";
import type {
  ApiProductStrategyArtifactAcceptance,
  ApiProductStrategyArtifactAcceptanceArtifact,
  ApiProductStrategyArtifactAcceptanceInstructionEvidence,
  ApiProductStrategyArtifactSourceBundle,
} from "@/lib/api/type-contracts/competitive-intelligence";

const apiMock = vi.hoisted(() => ({
  getArtifactAcceptancePreview: vi.fn(),
  getArtifactAcceptance: vi.fn(),
  initializeArtifactAcceptance: vi.fn(),
}));

vi.mock("@/lib/api/competitive-intelligence", () => ({
  getArtifactAcceptancePreview: apiMock.getArtifactAcceptancePreview,
  getArtifactAcceptance: apiMock.getArtifactAcceptance,
  initializeArtifactAcceptance: apiMock.initializeArtifactAcceptance,
}));

const instructionEvidence: ApiProductStrategyArtifactAcceptanceInstructionEvidence = {
  kind: "user_instruction",
  actor_identity_status: "unverified",
  scope: "artifact_acceptance_definition_only",
  instruction: "下一步应是受 Office/视觉证据门禁约束的 2.10.2 交付物验收与修订差异。",
  recorded_at: "2026-08-28T00:00:00Z",
  authorization_scope: "initialize_hold_only_artifact_acceptance_definitions",
  does_not_approve_artifact_acceptance: true,
  does_not_approve_release: true,
  does_not_authorize_execution: true,
  requires_human_evidence_review: true,
};

const sourceBundle: ApiProductStrategyArtifactSourceBundle = {
  bundle_kind: "decision_context_packet_binding",
  decision_context_packet: {
    packet_key: "anti-fomo:2.10.1:qwen_work:build:context",
    roadmap_card_key: "qwen_work:build",
    decision: "build",
    revision: 1,
    revision_digest: "b".repeat(64),
    source_catalog_version: "2.10.0",
    source_catalog_keys: ["qwen_work:official-product"],
    source_digests: ["a".repeat(64)],
    source_references: [
      {
        catalog_key: "qwen_work:official-product",
        source_digest: "a".repeat(64),
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
  },
  evidence_collection: {
    office_file_processing_performed: false,
    visual_render_processing_performed: false,
    office_evidence_status: "missing",
    visual_evidence_status: "missing",
    note: "该 bundle 仅引用 2.10.1 已记录的上下文和来源摘要，未收集 Office 或视觉证据。",
  },
};

const artifactFixture: ApiProductStrategyArtifactAcceptanceArtifact = {
  id: null,
  artifact_key: "anti-fomo:2.10.2:qwen_work:build:artifact-acceptance",
  project_scope: "anti-fomo",
  artifact_acceptance_catalog_digest: "e".repeat(64),
  decision_context_packet_key: "anti-fomo:2.10.1:qwen_work:build:context",
  roadmap_card_key: "qwen_work:build",
  decision: "build",
  artifact_type: "editable_deliverable_lineage_review",
  title: "可编辑交付物与来源血缘验收草案",
  artifact_summary: "仅供人工复核的验收草案。",
  acceptance_status: "hold",
  acceptance_label: "HOLD",
  blocking_status: "blocked",
  office_evidence_status: "missing",
  visual_evidence_status: "missing",
  acceptance_checklist: [
    {
      check_key: "office_delivery_evidence",
      title: "Office 交付物可打开性与内容完整性证据",
      required: true,
      evidence_kind: "human_supplied_office_delivery_evidence",
      evidence_status: "missing",
      result: "hold",
      blocks_acceptance: true,
      note: "未提供可复核的 Office 证据。",
    },
    {
      check_key: "visual_render_evidence",
      title: "视觉渲染、版式与可读性证据",
      required: true,
      evidence_kind: "human_supplied_visual_render_evidence",
      evidence_status: "missing",
      result: "hold",
      blocks_acceptance: true,
      note: "未提供可复核的视觉证据。",
    },
    {
      check_key: "human_acceptance_decision",
      title: "人工验收结论",
      required: true,
      evidence_kind: "human_review_record",
      evidence_status: "not_recorded",
      result: "hold",
      blocks_acceptance: true,
      note: "未记录人工验收结论。",
    },
  ],
  evidence_source_bundle: sourceBundle,
  evidence_source_bundle_digest: "c".repeat(64),
  revision: 1,
  revision_digest: "d".repeat(64),
  can_auto_accept: false,
  can_auto_execute: false,
  can_auto_approve_release: false,
  requires_human_evidence_review: true,
  production_status: "not_authorized",
  release_impact: "none",
  seed_managed: true,
  created_at: null,
  updated_at: null,
  revisions: [
    {
      id: null,
      artifact_key: "anti-fomo:2.10.2:qwen_work:build:artifact-acceptance",
      revision: 1,
      previous_revision_digest: null,
      revision_digest: "d".repeat(64),
      event_type: "explicit_hold_only_initialization",
      snapshot: { revision: 1, acceptance_status: "hold" },
      evidence_source_bundle: sourceBundle,
      evidence_source_bundle_digest: "c".repeat(64),
      field_level_diff: {
        from_revision: null,
        to_revision: 1,
        auto_acceptance_forbidden: true,
        release_gate_mutated: false,
        changed_fields: [
          {
            field: "acceptance_status",
            before: null,
            after: "hold",
            change_type: "added",
          },
        ],
      },
      is_immutable: true,
      seed_managed: true,
      created_at: "2026-08-28T08:00:00Z",
    },
  ],
  initial_field_level_diff: null,
};

const previewFixture: ApiProductStrategyArtifactAcceptance = {
  artifact_acceptance_version: "2.10.2",
  source_catalog_version: "2.10.0",
  catalog_digest: "e".repeat(64),
  context_packet_catalog_digest: "f".repeat(64),
  read_only: true,
  initialized: false,
  persistent_snapshot_digest: null,
  instruction_evidence: instructionEvidence,
  governance: {
    instruction_kind: "user_instruction",
    actor_identity_status: "unverified",
    scope: "artifact_acceptance_definition_only",
    artifact_definitions_require_explicit_initialization: true,
    requires_persisted_decision_context_packets: true,
    missing_office_or_visual_evidence_results_in_hold: true,
    no_external_office_file_processing: true,
    no_visual_render_validation_claim: true,
    can_auto_accept: false,
    can_auto_execute: false,
    can_auto_approve_release: false,
    requires_human_evidence_review: true,
    release_gate_mutated: false,
    production_status: "not_authorized",
    note: "2.10.2 只登记缺失的验收证据和差异，不接受工件。",
  },
  context_packet_readiness: null,
  artifacts: [artifactFixture],
  initialization_audit: null,
};

describe("CompetitiveArtifactAcceptance", () => {
  beforeEach(() => {
    apiMock.getArtifactAcceptancePreview.mockReset();
    apiMock.getArtifactAcceptance.mockReset();
    apiMock.initializeArtifactAcceptance.mockReset();
    vi.stubGlobal("confirm", vi.fn(() => true));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it("renders source/revision diffs while keeping missing Office and visual evidence on HOLD", async () => {
    apiMock.getArtifactAcceptancePreview.mockResolvedValue(previewFixture);
    apiMock.getArtifactAcceptance.mockResolvedValue(previewFixture);

    render(<CompetitiveArtifactAcceptance />);

    expect(await screen.findByTestId("competitive-artifact-acceptance")).toBeInTheDocument();
    expect(screen.getByText("HOLD · blocked")).toBeInTheDocument();
    expect(screen.getByText("Office 交付物可打开性与内容完整性证据 · missing / hold")).toBeInTheDocument();
    expect(screen.getByText("视觉渲染、版式与可读性证据 · missing / hold")).toBeInTheDocument();
    expect(screen.getByText("来源与字段级修订差异")).toBeInTheDocument();
    expect(screen.getByText(/acceptance_status/)).toBeInTheDocument();
    expect(screen.getAllByText(/禁止自动接受/)).not.toHaveLength(0);
    expect(screen.getByRole("button", { name: "显式确认并初始化" })).toBeInTheDocument();
  });

  it("does not initialize an acceptance ledger when the explicit confirmation is declined", async () => {
    apiMock.getArtifactAcceptancePreview.mockResolvedValue(previewFixture);
    apiMock.getArtifactAcceptance.mockResolvedValue(previewFixture);
    vi.stubGlobal("confirm", vi.fn(() => false));

    render(<CompetitiveArtifactAcceptance />);
    fireEvent.click(await screen.findByRole("button", { name: "显式确认并初始化" }));

    expect(apiMock.initializeArtifactAcceptance).not.toHaveBeenCalled();
  });

  it("initializes a review ledger only after confirmation and keeps the HOLD boundary", async () => {
    apiMock.getArtifactAcceptancePreview.mockResolvedValue(previewFixture);
    apiMock.getArtifactAcceptance.mockResolvedValue(previewFixture);
    apiMock.initializeArtifactAcceptance.mockResolvedValue({
      ...previewFixture,
      initialized: true,
      read_only: false,
      persistent_snapshot_digest: "9".repeat(64),
      initialization_audit: {
        id: "audit-1",
        event_key: "anti-fomo:2.10.2:reviewable-artifact-acceptance-initialization",
        project_scope: "anti-fomo",
        event_type: "explicit_user_instruction_hold_only_artifact_acceptance_initialization",
        instruction_evidence: instructionEvidence,
        required_context_packet_keys: [artifactFixture.decision_context_packet_key],
        artifact_catalog_digest: "e".repeat(64),
        context_packet_catalog_digest: "f".repeat(64),
        event_digest: "8".repeat(64),
        can_auto_accept: false,
        can_auto_execute: false,
        can_auto_approve_release: false,
        release_gate_mutated: false,
        created_at: "2026-08-28T08:00:00Z",
      },
      initialization: {
        drafts: { created: 1, existing_seed_managed: 0, preserved_human: 0 },
        revisions: { created: 1, existing: 0, preserved_human: 0 },
        initialization_audit: { created: 1, existing: 0 },
      },
    });

    render(<CompetitiveArtifactAcceptance />);
    fireEvent.click(await screen.findByRole("button", { name: "显式确认并初始化" }));

    expect(apiMock.initializeArtifactAcceptance).toHaveBeenCalledOnce();
    expect(await screen.findByText("已初始化审查台账")).toBeInTheDocument();
    expect(screen.getByText("初始化记录：新建 1 个工件台账，已存在 seed 管理项 0 个，保留人工项 0 个；新增 revision 1 条，初始化审计新增 1 条。")).toBeInTheDocument();
    expect(screen.getAllByText(/HOLD/)).not.toHaveLength(0);
  });
});
