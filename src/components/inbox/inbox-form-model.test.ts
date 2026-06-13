import { describe, expect, it } from "vitest";
import type { ApiResearchReport } from "@/lib/api";
import {
  buildResearchDeliverySupplement,
  buildResearchKeywordGroups,
  buildResearchModeConfig,
  classifyResearchSourceTier,
  mapResearchStageToPipelineKey,
} from "@/components/inbox/inbox-form-model";

describe("inbox form model", () => {
  it("deduplicates and limits research keyword groups", () => {
    expect(buildResearchKeywordGroups("政务云", "上海，预算 / 政务云；招标 交付")).toEqual([
      "政务云",
      "上海",
      "预算",
      "招标",
    ]);
  });

  it("keeps fast and deep provider budgets explicit", () => {
    expect(buildResearchModeConfig("fast")).toEqual({
      research_mode: "fast",
      deep_research: false,
      max_sources: 8,
      estimatedMinutes: 3,
    });
    expect(buildResearchModeConfig("deep")).toEqual({
      research_mode: "deep",
      deep_research: true,
      max_sources: 18,
      estimatedMinutes: 6,
    });
  });

  it("classifies explicit, official, aggregate, and media sources", () => {
    expect(classifyResearchSourceTier({ source_tier: "official" } as ApiResearchReport["sources"][number])).toBe(
      "official",
    );
    expect(classifyResearchSourceTier({ domain: "example.gov.cn" } as ApiResearchReport["sources"][number])).toBe(
      "official",
    );
    expect(classifyResearchSourceTier({ source_type: "tender_feed" } as ApiResearchReport["sources"][number])).toBe(
      "aggregate",
    );
    expect(classifyResearchSourceTier({ domain: "news.example.com" } as ApiResearchReport["sources"][number])).toBe(
      "media",
    );
  });

  it("maps runtime stages to the three stable presentation phases", () => {
    expect(mapResearchStageToPipelineKey("fetching")).toBe("fetch");
    expect(mapResearchStageToPipelineKey("corrective")).toBe("clean");
    expect(mapResearchStageToPipelineKey("packaging")).toBe("analyze");
  });

  it("builds delivery defaults from the highest-confidence report fields", () => {
    const report = {
      keyword: "上海政务云",
      report_title: "上海政务云机会研究",
      research_focus: "政府云迁移",
      top_target_accounts: [{ name: "上海市大数据中心" }],
      target_accounts: ["备选客户"],
      solution_delivery_pack: {
        scenario: "政务云迁移",
        target_customer: "市级政务部门",
        vertical_scene: "政务云",
      },
      source_diagnostics: { scope_regions: ["上海", "长三角"] },
      tender_timeline: ["2026 Q3"],
      budget_signals: ["预算待核验"],
      strategic_directions: ["先验证迁移窗口"],
      five_year_outlook: ["形成持续服务收入"],
      followup_context: {
        supplemental_context: "客户补充背景",
        supplemental_evidence: "客户补充证据",
        supplemental_requirements: "必须覆盖信创适配",
      },
    } as ApiResearchReport;

    expect(buildResearchDeliverySupplement(report)).toMatchObject({
      project_name: "上海政务云机会研究",
      project_owner: "上海市大数据中心",
      solution_scenario: "政务云迁移",
      target_customer: "市级政务部门",
      vertical_scene: "政务云",
      project_region: "上海 / 长三角",
      implementation_window: "2026 Q3",
      supplemental_requirements: "必须覆盖信创适配",
    });
  });
});
