import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { DecisionStudioWorkspace } from "@/components/decision-studio/decision-studio-workspace";
import type {
  DecisionNotebookDetail,
  DecisionNotebookSummary,
  DecisionStudioOverview,
} from "@/lib/api/type-contracts/decision-studio";


const apiMock = vi.hoisted(() => ({
  addDecisionSource: vi.fn(),
  buildDecisionSemanticIndex: vi.fn(),
  compileDecisionSections: vi.fn(),
  createDecisionClaim: vi.fn(),
  createDecisionContract: vi.fn(),
  createDecisionNotebook: vi.fn(),
  generateDecisionArtifact: vi.fn(),
  getDecisionNotebook: vi.fn(),
  getDecisionReadiness: vi.fn(),
  getDecisionReleaseProgram: vi.fn(),
  getDecisionStudioOverview: vi.fn(),
  previewDecisionDataActivation: vi.fn(),
  runDecisionDataActivation: vi.fn(),
  searchDecisionNotebook: vi.fn(),
  upsertDecisionSection: vi.fn(),
  verifyDecisionSource: vi.fn(),
}));

vi.mock("@/lib/api/decision-studio", () => apiMock);

const notebook: DecisionNotebookSummary = {
  id: "11111111-1111-4111-8111-111111111111",
  user_id: "00000000-0000-0000-0000-000000000001",
  space_id: null,
  name: "文旅决策 Notebook",
  description: "",
  status: "active",
  source_count: 0,
  artifact_count: 0,
  stale_artifact_count: 0,
  created_at: "2026-07-16T00:00:00Z",
  updated_at: "2026-07-16T00:00:00Z",
};

const overview: DecisionStudioOverview = {
  version: "2.2.0-development",
  capabilities: ["1.9.2", "1.9.3", "1.9.4", "1.9.5", "1.9.6", "2.0.0", "2.0.1", "2.0.2", "2.0.3", "2.0.4", "2.0.5", "2.0.6", "2.0.7", "2.1.0", "2.1.1", "2.1.2", "2.1.3", "2.1.4", "2.1.5", "2.2.0"],
  embedding: {
    enabled: true,
    provider: "sentence_transformers",
    model: "BAAI/bge-m3",
    device: "mps",
    batch_size: 8,
    cache_dir: "/tmp/anti-fomo-test-hf/hub",
    xet_cache_dir: "/tmp/anti-fomo-test-hf/xet",
  },
  spaces: [],
  notebooks: [],
  policy_packs: [
    {
      id: "22222222-2222-4222-8222-222222222222",
      pack_key: "government_fsr_2023",
      version: "2023.1",
      title: "政府投资项目可行性研究报告合同包",
      authority: "国家发展和改革委员会",
      source_uri: "https://www.gov.cn/",
      document_kind: "government_feasibility_study",
      status: "active",
      schema: { sections: ["概述"], fields: [{ key: "project_overview" }] },
      content_hash: "hash",
    },
  ],
  skills: [],
};

const detail: DecisionNotebookDetail = {
  ...notebook,
  sources: [],
  contracts: [],
  claims: [],
  sections: [],
  artifacts: [],
};

describe("DecisionStudioWorkspace", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    Object.values(apiMock).forEach((mock) => mock.mockReset());
    apiMock.getDecisionStudioOverview.mockResolvedValue(overview);
    apiMock.createDecisionNotebook.mockResolvedValue(notebook);
    apiMock.getDecisionNotebook.mockResolvedValue(detail);
    apiMock.getDecisionReadiness.mockResolvedValue({
      generated_at: "2026-07-16T00:00:00Z",
      release_version: "2.2.0-development",
      overall_status: "blocked",
      readiness_score: 42,
      summary_lines: [],
      gates: [],
      next_actions: [],
    });
    apiMock.getDecisionReleaseProgram.mockResolvedValue({
      generated_at: "2026-07-16T00:00:00Z",
      release_version: "2.0.7-development",
      implementation_status: "implemented",
      overall_status: "blocked",
      readiness_score: 0,
      honesty_note: "缺少外部证据时保持 blocked。",
      milestones: [
        {
          version: "2.0.1",
          implementation_status: "implemented",
          acceptance_status: "blocked",
          score: 0,
          suite_count: 1,
          passed_suite_count: 0,
          suites: [
            {
              suite_key: "retrieval_benchmark",
              label: "三行业语义检索基准",
              evidence_class: "independent_review",
              status: "blocked",
              score: 0,
              target: "300 条人工 qrels",
              latest_run: null,
              blockers: ["尚无不可变验证运行记录。"],
            },
          ],
        },
      ],
    });
  });

  it("shows the real embedding route and creates a notebook", async () => {
    render(<DecisionStudioWorkspace />);

    expect(await screen.findByText("BAAI/bge-m3")).toBeInTheDocument();
    expect(screen.getByText("2.2.0-development")).toBeInTheDocument();
    expect(screen.getByText("暂无 Notebook")).toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("新 Notebook 名称"), {
      target: { value: "文旅决策 Notebook" },
    });
    const createButton = screen.getByRole("button", { name: "创建 Notebook" });
    await waitFor(() => expect(createButton).toBeEnabled());
    fireEvent.click(createButton);

    await waitFor(() => {
      expect(apiMock.createDecisionNotebook).toHaveBeenCalledWith({
        name: "文旅决策 Notebook",
        description: "Decision Studio 工作台",
      });
      expect(apiMock.getDecisionNotebook).toHaveBeenCalledWith(notebook.id);
    });
  });

  it("shows milestone blockers separately from implementation status", async () => {
    render(<DecisionStudioWorkspace />);
    await screen.findByText("BAAI/bge-m3");

    fireEvent.click(screen.getByRole("button", { name: "发布门禁" }));

    expect(await screen.findByText("三行业语义检索基准")).toBeInTheDocument();
    expect(screen.getByText("尚无不可变验证运行记录。")).toBeInTheDocument();
    expect(screen.getByText("工程已实现 · 验收 0/1")).toBeInTheDocument();
    expect(apiMock.getDecisionReleaseProgram).toHaveBeenCalledTimes(1);
  });

  it("previews existing data before activation", async () => {
    apiMock.previewDecisionDataActivation.mockResolvedValue({
      status: "ready",
      candidate_count: 2,
      state_counts: { new: 2 },
      source_type_counts: { knowledge_entry: 1, research_job: 1 },
      notebook_id: null,
      candidates: [],
      warnings: [],
    });
    render(<DecisionStudioWorkspace />);
    await screen.findByText("BAAI/bge-m3");

    fireEvent.click(screen.getByRole("button", { name: "扫描可激活数据" }));

    expect(await screen.findByText("知识 1 · 研报 1 · 重复 0")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "创建并激活" })).toBeInTheDocument();
    expect(apiMock.previewDecisionDataActivation).toHaveBeenCalledWith({
      notebook_name: "现有知识与研报",
      notebook_id: null,
    });
  });
});
