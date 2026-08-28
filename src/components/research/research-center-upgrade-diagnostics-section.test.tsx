import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResearchCenterUpgradeDiagnosticsSection } from "@/components/research/research-center-upgrade-diagnostics-section";
import type { ApiResearchUpgradeDiagnostics } from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  getResearchUpgradeDiagnosticsPreview: vi.fn(),
}));

vi.mock("@/lib/api", async () => ({
  getResearchUpgradeDiagnosticsPreview: apiMock.getResearchUpgradeDiagnosticsPreview,
}));

const diagnosticsFixture: ApiResearchUpgradeDiagnostics = {
  generated_at: "2026-07-08T09:00:00Z",
  roadmap_version: "tencent-url-and-research-upgrade-plan-2026-06",
  status: "watch",
  readiness_score: 63,
  keyword: "上海医疗 AI",
  research_focus: "预算 采购 甲方",
  roadmap_rounds: [
    { index: 1, key: "wechat_url_path_profile", title: "微信 URL 路径 profile", status: "ready", summary: "strict paths 1/1" },
    { index: 2, key: "retrieval_evaluator", title: "Retrieval evaluator", status: "watch", summary: "accepted 1/2 sources." },
  ],
  url_first_diagnostics: {
    valid_url_count: 2,
    invalid_url_count: 0,
    wechat_url_count: 1,
    strict_wechat_path_count: 1,
    url_first_ratio: 1,
    browser_url_check_ready: true,
    clipboard_url_check_ready: true,
    ocr_fallback_required: false,
    warnings: [],
  },
  query_plan: [
    {
      key: "tender",
      intent: "采购/预算",
      query: "上海医疗 AI 招标 采购 预算",
      must_terms: ["上海医疗", "AI"],
      exclude_terms: ["转载"],
    },
  ],
  retrieval_evaluation: {
    source_count: 2,
    accepted_count: 1,
    ambiguous_count: 1,
    rejected_count: 0,
    filtered_old_source_count: 0,
    official_source_ratio: 0.5,
    average_relevance_score: 70,
    topic_relevance_passed: true,
    recency_cutoff_year: 2019,
    hits: [
      {
        title: "上海公共资源交易平台医疗数据治理项目采购意向",
        url: "https://www.shggzy.com/jyxx/20260512/medical-data-ai.html",
        source_tier: "official",
        source_type: "public_tender",
        relevance_score: 89,
        accepted: true,
        reason: "topic terms, source tier and recency pass",
        matched_terms: ["预算", "采购"],
      },
      {
        title: "医疗 AI 生态伙伴发布医院场景联合解决方案",
        url: "https://www.example.com/medical-ai-partner-case",
        source_tier: "media",
        source_type: "industry_media",
        relevance_score: 47,
        accepted: false,
        reason: "needs cross-check before generation",
        matched_terms: ["AI"],
      },
    ],
  },
  lightweight_graph: {
    nodes: [{ name: "上海公共资源交易平台", role: "budget", evidence_count: 1, source_tiers: { official: 1 } }],
    edges: [],
  },
  expert_panels: [
    { role: "buyer_value", label: "甲方价值专家", score: 76, findings: ["识别甲方/业主节点 1 个。"], next_actions: ["补采购人。"] },
    { role: "competitor_threat", label: "竞品威胁专家", score: 48, findings: ["竞品/供应商信号 0 个。"], next_actions: ["扩搜中标方。"] },
    { role: "partner_influence", label: "生态伙伴影响力专家", score: 72, findings: ["伙伴/生态信号 1 个。"], next_actions: ["确认伙伴。"] },
    { role: "tender_cadence", label: "招投标节奏专家", score: 80, findings: ["招采关键词命中 3 次。"], next_actions: ["建立跟踪节奏。"] },
  ],
  section_evidence_quotas: [
    {
      section_title: "预算与采购信号",
      required_evidence_count: 3,
      actual_evidence_count: 1,
      passed: false,
      gap: 2,
      note: "还需补 2 条可验证证据",
    },
  ],
  field_diffs: [
    {
      field: "budget_signal",
      before: "政策试点，预算待核验",
      after: "出现采购意向，金额仍待核验",
      status: "changed",
      summary: "字段发生变化，需检查版本差异和证据。",
    },
  ],
  fallback_actions: [
    {
      priority: "medium",
      action: "按章节补证据配额",
      reason: "关键章节仍缺少可验证 URL。",
      owner: "report-quality",
    },
  ],
  source_type_contributions: [
    {
      source_type: "public_tender",
      count: 1,
      accepted_count: 1,
      contribution_percent: 56,
      average_relevance_score: 89,
    },
  ],
  summary_lines: ["15 轮路线图诊断：ready 1/2, blocked 0/2。"],
};

describe("ResearchCenterUpgradeDiagnosticsSection", () => {
  beforeEach(() => {
    apiMock.getResearchUpgradeDiagnosticsPreview.mockReset();
  });

  it("surfaces actionable diagnostics beyond the roadmap summary", async () => {
    apiMock.getResearchUpgradeDiagnosticsPreview.mockResolvedValue(diagnosticsFixture);

    render(<ResearchCenterUpgradeDiagnosticsSection t={(_key, fallback) => fallback} />);

    expect(await screen.findByText("章节证据配额")).toBeInTheDocument();
    expect(screen.getByText("预算与采购信号")).toBeInTheDocument();
    expect(screen.getByText("还需补 2 条可验证证据")).toBeInTheDocument();
    expect(screen.getByText("字段变化复核")).toBeInTheDocument();
    expect(screen.getByText("budget_signal")).toBeInTheDocument();
    expect(screen.getByText("来源贡献")).toBeInTheDocument();

    const sourceContribution = screen.getByText("public_tender").closest("div");
    expect(sourceContribution).not.toBeNull();
    expect(within(sourceContribution as HTMLElement).getByText("56%")).toBeInTheDocument();

    expect(screen.getByText("检索命中复核")).toBeInTheDocument();
    expect(screen.getByText("上海公共资源交易平台医疗数据治理项目采购意向")).toBeInTheDocument();
  });
});
