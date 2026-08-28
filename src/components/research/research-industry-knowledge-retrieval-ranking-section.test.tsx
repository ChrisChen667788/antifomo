import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResearchIndustryKnowledgeRetrievalRankingSection } from "@/components/research/research-industry-knowledge-retrieval-ranking-section";
import type { ApiResearchIndustryKnowledgeRetrievalBenchmark } from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  getResearchIndustryKnowledgeRetrievalBenchmark: vi.fn(),
  runResearchIndustryKnowledgeRetrievalBenchmark: vi.fn(),
}));

vi.mock("@/lib/api", async () => ({
  getResearchIndustryKnowledgeRetrievalBenchmark: apiMock.getResearchIndustryKnowledgeRetrievalBenchmark,
  runResearchIndustryKnowledgeRetrievalBenchmark: apiMock.runResearchIndustryKnowledgeRetrievalBenchmark,
}));

const fixture: ApiResearchIndustryKnowledgeRetrievalBenchmark = {
  benchmark_id: "industry-knowledge-retrieval-ranking-ab-v1",
  dataset_version: "v1",
  dataset_sha256: "fixture",
  benchmark_digest: "fixture-benchmark-digest",
  generated_at: "2026-08-12T00:00:00Z",
  knowledge_base_generated_at: "2026-08-12T00:00:00Z",
  knowledge_base_generation_id: "fixture-generation",
  status: "partial",
  case_count: 12,
  strategies: [
    {
      key: "baseline_hybrid",
      label: "当前基线：混合检索",
      description: "全库混合检索。",
      default: true,
      lexical_prefilter: false,
      title_bm25_weight: 1,
      rerank_enabled: false,
      rerank_top_k: 0,
    },
    {
      key: "prefilter_weighted_rerank",
      label: "候选 B：预过滤 + 标题加权 + 复排",
      description: "真实模型复排。",
      default: false,
      lexical_prefilter: true,
      title_bm25_weight: 3,
      rerank_enabled: true,
      rerank_top_k: 20,
    },
  ],
  arms: [
    {
      strategy: "baseline_hybrid",
      label: "当前基线：混合检索",
      role: "baseline",
      case_count: 12,
      rerank_applied_case_count: 0,
      rerank_backend: "disabled",
      rerank_model: "",
      cases: [],
      metrics: [
        { key: "recall_at_10", label: "Recall@10", value: 1, baseline_value: 1, delta: 0, available: true, note: "" },
        { key: "human_review_score", label: "报告人工评分", value: null, baseline_value: null, delta: null, available: false, note: "待评分" },
      ],
    },
    {
      strategy: "prefilter_weighted_rerank",
      label: "候选 B：预过滤 + 标题加权 + 复排",
      role: "candidate",
      case_count: 12,
      rerank_applied_case_count: 0,
      rerank_backend: "unavailable",
      rerank_model: "BAAI/bge-reranker-v2-m3",
      cases: [],
      metrics: [
        { key: "recall_at_10", label: "Recall@10", value: 1, baseline_value: 1, delta: 0, available: true, note: "" },
        { key: "human_review_score", label: "报告人工评分", value: null, baseline_value: null, delta: null, available: false, note: "待评分" },
      ],
    },
  ],
  promotion: {
    decision: "hold",
    candidate_strategy: "",
    reasons: ["固定题集的报告人工评分尚未全部完成。", "未在全部固定题目上取得真实 Cross Encoder 复排证据。"],
    required_human_review_case_count: 36,
    completed_human_review_case_count: 0,
  },
  artifact_path: ".tmp/benchmark.json",
  review_template_path: ".tmp/review.json",
  review_artifact_path: ".tmp/review.json",
  review_sample_directory: ".tmp/industry-knowledge-retrieval-ranking-ab-v1/review-samples",
  warnings: ["候选 B 未取得真实 Cross Encoder 复排证据。"],
};

describe("ResearchIndustryKnowledgeRetrievalRankingSection", () => {
  beforeEach(() => {
    apiMock.getResearchIndustryKnowledgeRetrievalBenchmark.mockReset();
    apiMock.runResearchIndustryKnowledgeRetrievalBenchmark.mockReset();
  });

  it("shows benchmark metrics and keeps the production decision on hold", async () => {
    apiMock.getResearchIndustryKnowledgeRetrievalBenchmark.mockResolvedValue(fixture);

    render(<ResearchIndustryKnowledgeRetrievalRankingSection t={(_key, fallback) => fallback} />);

    expect(await screen.findByText("Local Knowledge Retrieval")).toBeInTheDocument();
    expect(screen.getByText("保持现状")).toBeInTheDocument();
    expect(screen.getByText("固定题集")).toBeInTheDocument();
    expect(screen.getByText("12 题")).toBeInTheDocument();
    expect(screen.getAllByText("当前基线：混合检索").length).toBeGreaterThan(0);
    expect(screen.getAllByText("候选 B：预过滤 + 标题加权 + 复排").length).toBeGreaterThan(0);
    expect(screen.getByText("真实复排：0/12 · unavailable · BAAI/bge-reranker-v2-m3")).toBeInTheDocument();
    expect(screen.getByText("固定题集的报告人工评分尚未全部完成。")).toBeInTheDocument();
    expect(screen.getByText("候选 B 未取得真实 Cross Encoder 复排证据。")).toBeInTheDocument();
  });
});
