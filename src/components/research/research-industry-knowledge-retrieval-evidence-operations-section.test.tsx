import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResearchIndustryKnowledgeRetrievalEvidenceOperationsSection } from "@/components/research/research-industry-knowledge-retrieval-evidence-operations-section";
import type { ApiResearchIndustryKnowledgeRetrievalEvidenceOperationsSnapshot } from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  getResearchIndustryKnowledgeRetrievalEvidenceOperations: vi.fn(),
  exportResearchIndustryKnowledgeRetrievalEvidenceOperationsTemplates: vi.fn(),
}));

vi.mock("@/lib/api", async () => ({
  getResearchIndustryKnowledgeRetrievalEvidenceOperations: apiMock.getResearchIndustryKnowledgeRetrievalEvidenceOperations,
  exportResearchIndustryKnowledgeRetrievalEvidenceOperationsTemplates: apiMock.exportResearchIndustryKnowledgeRetrievalEvidenceOperationsTemplates,
}));

const fixture: ApiResearchIndustryKnowledgeRetrievalEvidenceOperationsSnapshot = {
  program_version: "2.9.5-retrieval-evidence-operations",
  generated_at: "2026-08-14T00:00:00Z",
  status: "blocked",
  score: 12,
  parent_program_version: "2.8.0-retrieval-assurance",
  parent_status: "blocked",
  current_default_strategy: "baseline_hybrid",
  candidate_strategy: "",
  benchmark_digest: "fixture-benchmark-digest",
  evidence_chain_digest: "fixture-evidence-chain-digest",
  case_count: 12,
  pass_count: 2,
  watch_count: 1,
  blocked_count: 12,
  rounds: [
    {
      index: 1,
      version: "2.8.1",
      key: "evidence_envelope",
      title: "证据封套与摘要完整性",
      status: "pass",
      summary: "固定摘要已绑定。",
      metrics: [{ key: "digest", label: "评测摘要", observed: "已绑定", target: "可重算", status: "pass", note: "" }],
      next_actions: [],
      evidence: [],
    },
    {
      index: 10,
      version: "2.9.0",
      key: "incident_register",
      title: "异常与豁免登记",
      status: "blocked",
      summary: "登记册待负责人完成。",
      metrics: [{ key: "incident", label: "事件登记", observed: "pending", target: "complete", status: "blocked", note: "" }],
      next_actions: ["导出事件登记模板。"],
      evidence: [],
    },
  ],
  artifacts: [{ label: "事件登记册", path: ".tmp/incidents.json", exists: false, status: "blocked", summary: "待负责人完成。" }],
  next_actions: ["导出事件登记模板。"],
  warnings: ["模板不构成外部完成证据。"],
};

describe("ResearchIndustryKnowledgeRetrievalEvidenceOperationsSection", () => {
  beforeEach(() => {
    apiMock.getResearchIndustryKnowledgeRetrievalEvidenceOperations.mockReset();
    apiMock.exportResearchIndustryKnowledgeRetrievalEvidenceOperationsTemplates.mockReset();
  });

  it("shows a concise fail-closed operations state without internal reasoning", async () => {
    apiMock.getResearchIndustryKnowledgeRetrievalEvidenceOperations.mockResolvedValue(fixture);

    render(<ResearchIndustryKnowledgeRetrievalEvidenceOperationsSection t={(_key, fallback) => fallback} />);

    expect(await screen.findByTestId("research-industry-knowledge-retrieval-evidence-operations-section")).toBeInTheDocument();
    expect(screen.getByText("Evidence Operations")).toBeInTheDocument();
    expect(screen.getByText("生产默认")).toBeInTheDocument();
    expect(screen.getByText("受控运营状态")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "导出运营模板" })).toBeInTheDocument();
    expect(screen.queryByText(/hidden prompt|chain of thought/i)).not.toBeInTheDocument();
  });
});
