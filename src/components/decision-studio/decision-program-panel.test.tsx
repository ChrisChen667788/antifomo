import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DecisionProgramPanel } from "@/components/decision-studio/decision-program-panel";


const apiMock = vi.hoisted(() => ({
  freezeDecisionReleaseCandidate: vi.fn(),
  getDecisionProgramOverview: vi.fn(),
  getDecisionVerticalPacks: vi.fn(),
  previewDecisionReleaseCandidate: vi.fn(),
  seedDecisionVerticalPacks: vi.fn(),
}));

vi.mock("@/lib/api/decision-program", () => apiMock);

const overview = {
  version: "2.2.0-development",
  generated_at: "2026-07-18T00:00:00Z",
  engineering_status: "implemented" as const,
  overall_acceptance_status: "blocked" as const,
  honesty_note: "外部证据缺失时保持 blocked。",
  milestones: [
    {
      version: "2.0.7",
      label: "Release Evidence Closure",
      engineering_status: "implemented" as const,
      acceptance_status: "blocked" as const,
      evidence: { latest_candidate_id: null },
      blockers: ["冻结候选尚未绑定全部验证运行与真实外部验收 artifact。"],
    },
    {
      version: "2.2.0",
      label: "Commercial Team Decision OS",
      engineering_status: "implemented" as const,
      acceptance_status: "blocked" as const,
      evidence: { accepted_customer_pilots: 0 },
      blockers: ["尚无由客户签署的完整 Pilot。"],
    },
  ],
};

const packs = [
  {
    id: "pack-1",
    pack_key: "tourism-project-cn",
    version: "1.0.0",
    sector: "tourism" as const,
    title: "中国文旅项目策划与可研证据包",
    status: "validation_pending" as const,
    benchmark: { status: "blocked" },
    content_hash: "a".repeat(64),
  },
];

describe("DecisionProgramPanel", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    Object.values(apiMock).forEach((mock) => mock.mockReset());
    apiMock.getDecisionProgramOverview.mockResolvedValue(overview);
    apiMock.getDecisionVerticalPacks.mockResolvedValue(packs);
    apiMock.seedDecisionVerticalPacks.mockResolvedValue(packs);
    apiMock.previewDecisionReleaseCandidate.mockResolvedValue({
      version: "2.0.7",
      build_digest: "b".repeat(64),
      acceptance_status: "blocked",
      validation_run_ids: [],
      evidence_snapshot: {},
      blockers: ["缺少专家校准 artifact。"],
      persisted: false,
    });
    apiMock.freezeDecisionReleaseCandidate.mockResolvedValue({
      id: "candidate-1",
      version: "2.0.7",
      build_digest: "b".repeat(64),
      status: "frozen",
      acceptance_status: "blocked",
      manifest: { build_id: "abc123" },
      validation_run_ids: [],
      external_attestations: {},
      evidence_snapshot: {},
      blockers: ["缺少专家校准 artifact。"],
      frozen_at: "2026-07-18T00:00:00Z",
    });
  });

  it("separates implemented milestones from blocked external acceptance", async () => {
    render(<DecisionProgramPanel />);

    expect(await screen.findByText("Release Evidence Closure")).toBeInTheDocument();
    expect(screen.getByText("冻结候选尚未绑定全部验证运行与真实外部验收 artifact。")).toBeInTheDocument();
    expect(screen.getByText("中国文旅项目策划与可研证据包")).toBeInTheDocument();
    expect(screen.getByText("implemented · blocked")).toBeInTheDocument();
  });

  it("freezes a candidate without pretending missing attestations exist", async () => {
    render(<DecisionProgramPanel />);
    await screen.findByText("Release Evidence Closure");

    fireEvent.change(screen.getByPlaceholderText("Git commit / build id"), { target: { value: "abc123" } });
    fireEvent.click(screen.getByRole("button", { name: "预检 digest" }));

    await waitFor(() => {
      expect(apiMock.previewDecisionReleaseCandidate).toHaveBeenCalledTimes(1);
    });
    expect(await screen.findByText(/预检未落库/)).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "冻结候选" }));

    await waitFor(() => {
      expect(apiMock.freezeDecisionReleaseCandidate).toHaveBeenCalledWith({
        version: "2.0.7",
        manifest: {
          build_id: "abc123",
          source: "decision-studio-ui",
          target_version: "2.2.0-development",
        },
        validation_run_ids: [],
        external_attestations: {},
      });
    });
    expect(await screen.findByText("缺少专家校准 artifact。")).toBeInTheDocument();
  }, 30_000);
});
