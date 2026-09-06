import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { CompetitiveOfficeEvidenceReceipts } from "@/components/competitive-intelligence/competitive-office-evidence-receipts";
import type {
  ApiProductStrategyArtifactAcceptance,
  ApiProductStrategyOfficeEvidenceLandscape,
} from "@/lib/api/type-contracts/competitive-intelligence";

const apiMock = vi.hoisted(() => ({
  getOfficeEvidenceReceipts: vi.fn(),
  getArtifactAcceptance: vi.fn(),
  createOfficeEvidenceReceipt: vi.fn(),
}));

vi.mock("@/lib/api/competitive-intelligence", () => ({
  getOfficeEvidenceReceipts: apiMock.getOfficeEvidenceReceipts,
  getArtifactAcceptance: apiMock.getArtifactAcceptance,
  createOfficeEvidenceReceipt: apiMock.createOfficeEvidenceReceipt,
}));

const artifactKey = "anti-fomo:2.10.2:qwen_work:build:artifact-acceptance";

const acceptance = {
  initialized: true,
  artifacts: [
    {
      artifact_key: artifactKey,
      title: "可编辑交付物与来源血缘验收草案",
      revision: 1,
      revision_digest: "a".repeat(64),
    },
  ],
} as unknown as ApiProductStrategyArtifactAcceptance;

const landscape: ApiProductStrategyOfficeEvidenceLandscape = {
  office_evidence_version: "2.10.5",
  receipts: [
    {
      id: "receipt-1",
      receipt_key: `${artifactKey}:office:1234`,
      artifact_key: artifactKey,
      artifact_revision: 1,
      artifact_revision_digest: "a".repeat(64),
      file_name: "anti-fomo-review.docx",
      media_type: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      file_size_bytes: 24576,
      file_sha256: "b".repeat(64),
      storage_ref: "office-evidence/b/source.docx",
      source_version: "2.10.5-local",
      validator_version: "anti-fomo-office-receipt-v1",
      structure_status: "pass",
      office_roundtrip_status: "passed",
      visual_evidence_status: "rendered_unreviewed",
      page_count: 3,
      rendered_pdf_sha256: "c".repeat(64),
      rendered_pages: [{ file_name: "page-1.png", size_bytes: 1024, sha256: "d".repeat(64) }],
      validation: {},
      receipt_digest: "e".repeat(64),
      evidence_level: "local_runtime_evidence",
      human_review_status: "missing",
      acceptance_status: "hold",
      blocking_status: "blocked",
      can_auto_accept: false,
      can_auto_approve_release: false,
      production_status: "not_authorized",
      release_impact: "none",
      created_at: "2026-09-06T00:00:00Z",
    },
  ],
  receipt_count: 1,
  local_roundtrip_passed_count: 1,
  rendered_unreviewed_count: 1,
  acceptance_status: "hold",
  blocking_status: "blocked",
  requires_named_human_review: true,
  can_auto_accept: false,
  can_auto_approve_release: false,
  production_status: "not_authorized",
  release_impact: "none",
  note: "本地渲染不能替代具名人工复核。",
};

describe("CompetitiveOfficeEvidenceReceipts", () => {
  beforeEach(() => {
    apiMock.getOfficeEvidenceReceipts.mockReset();
    apiMock.getArtifactAcceptance.mockReset();
    apiMock.createOfficeEvidenceReceipt.mockReset();
    apiMock.getOfficeEvidenceReceipts.mockResolvedValue(landscape);
    apiMock.getArtifactAcceptance.mockResolvedValue(acceptance);
  });

  afterEach(() => cleanup());

  it("shows local render proof separately from missing human acceptance", async () => {
    render(<CompetitiveOfficeEvidenceReceipts />);

    expect(await screen.findByTestId("competitive-office-evidence-receipts")).toBeInTheDocument();
    expect(screen.getByText("HOLD · blocked")).toBeInTheDocument();
    expect(screen.getByText("anti-fomo-review.docx")).toBeInTheDocument();
    expect(screen.getByText("结构 pass")).toBeInTheDocument();
    expect(screen.getByText("roundtrip passed")).toBeInTheDocument();
    expect(screen.getByText("人工验收缺失")).toBeInTheDocument();
    expect(screen.getByText(/本地渲染不能替代具名人工复核/)).toBeInTheDocument();
  });
});
