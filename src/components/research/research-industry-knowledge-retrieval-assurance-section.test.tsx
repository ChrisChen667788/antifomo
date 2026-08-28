import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResearchIndustryKnowledgeRetrievalAssuranceSection } from "@/components/research/research-industry-knowledge-retrieval-assurance-section";
import type { ApiResearchIndustryKnowledgeRetrievalAssuranceSnapshot } from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  getResearchIndustryKnowledgeRetrievalAssurance: vi.fn(),
  exportResearchIndustryKnowledgeRetrievalApprovalTemplate: vi.fn(),
  exportResearchIndustryKnowledgeRetrievalEvidenceTemplates: vi.fn(),
}));

vi.mock("@/lib/api", async () => ({
  getResearchIndustryKnowledgeRetrievalAssurance: apiMock.getResearchIndustryKnowledgeRetrievalAssurance,
  exportResearchIndustryKnowledgeRetrievalApprovalTemplate: apiMock.exportResearchIndustryKnowledgeRetrievalApprovalTemplate,
  exportResearchIndustryKnowledgeRetrievalEvidenceTemplates: apiMock.exportResearchIndustryKnowledgeRetrievalEvidenceTemplates,
}));

const fixture: ApiResearchIndustryKnowledgeRetrievalAssuranceSnapshot = {
  program_version: "2.8.0-retrieval-assurance",
  generated_at: "2026-08-13T00:00:00Z",
  status: "blocked",
  score: 48,
  current_default_strategy: "baseline_hybrid",
  candidate_strategy: "",
  promotion_decision: "hold",
  benchmark_id: "industry-knowledge-retrieval-ranking-ab-v1",
  dataset_sha256: "dataset",
  benchmark_digest: "fixture-benchmark-digest",
  knowledge_base_generation_id: "generation",
  case_count: 12,
  pass_count: 4,
  watch_count: 2,
  blocked_count: 9,
  rounds: [
    {
      index: 1,
      version: "2.6.6",
      key: "immutable_benchmark_snapshot",
      title: "固定评测快照",
      status: "pass",
      summary: "题集已锁定。",
      metrics: [{ key: "dataset", label: "题集", observed: "已绑定", target: "可追溯", status: "pass", note: "" }],
      next_actions: [],
      evidence: [],
    },
    {
      index: 2,
      version: "2.6.9",
      key: "full_report_review_integrity",
      title: "完整研报人工复核完整性",
      status: "blocked",
      summary: "待复核。",
      metrics: [{ key: "review", label: "评分对", observed: "0/36", target: "36/36", status: "blocked", note: "" }],
      next_actions: ["完成独立人工复核。"],
      evidence: [],
    },
  ],
  artifacts: [{ label: "完整研报人工复核", path: ".tmp/review.json", exists: false, status: "blocked", summary: "需要独立声明。" }],
  next_actions: ["完成独立人工复核。"],
  warnings: ["生产默认继续保持 baseline_hybrid。"],
};

describe("ResearchIndustryKnowledgeRetrievalAssuranceSection", () => {
  beforeEach(() => {
    apiMock.getResearchIndustryKnowledgeRetrievalAssurance.mockReset();
    apiMock.exportResearchIndustryKnowledgeRetrievalApprovalTemplate.mockReset();
    apiMock.exportResearchIndustryKnowledgeRetrievalEvidenceTemplates.mockReset();
  });

  it("shows fail-closed assurance state without exposing internal reasoning", async () => {
    apiMock.getResearchIndustryKnowledgeRetrievalAssurance.mockResolvedValue(fixture);

    render(<ResearchIndustryKnowledgeRetrievalAssuranceSection t={(_key, fallback) => fallback} />);

    expect(await screen.findByTestId("research-industry-knowledge-retrieval-assurance-section")).toBeInTheDocument();
    expect(screen.getByText("Retrieval Assurance")).toBeInTheDocument();
    expect(screen.getByText("生产默认")).toBeInTheDocument();
    expect(screen.getAllByText("baseline_hybrid").length).toBeGreaterThan(0);
    expect(screen.getByText("完整研报人工复核")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导出审批模板" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导出运行模板" })).toBeInTheDocument();
  });
});
