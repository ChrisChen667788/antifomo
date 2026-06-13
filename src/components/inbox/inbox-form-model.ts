import type { ApiResearchReport } from "@/lib/api";

export type ResearchMode = "fast" | "deep";
export type ResearchPipelineKey = "fetch" | "clean" | "analyze";
export type ResearchPipelineStatus = "done" | "active" | "pending";
export type ResearchFormalExportFormat =
  | ""
  | "feasibility_word"
  | "feasibility_pdf"
  | "proposal_word"
  | "proposal_pdf";

export type ResearchDeliverySupplement = {
  project_name: string;
  project_owner: string;
  solution_scenario: string;
  target_customer: string;
  vertical_scene: string;
  project_region: string;
  implementation_window: string;
  investment_estimate: string;
  construction_basis: string;
  scope_statement: string;
  expected_benefits: string;
  cross_validation_notes: string;
  supplemental_context: string;
  supplemental_evidence: string;
  supplemental_requirements: string;
};

export function buildResearchDeliverySupplement(report: ApiResearchReport): ResearchDeliverySupplement {
  return {
    project_name: report.report_title || report.keyword,
    project_owner: report.top_target_accounts?.[0]?.name || report.target_accounts?.[0] || "",
    solution_scenario: report.solution_delivery_pack?.scenario || report.keyword,
    target_customer:
      report.solution_delivery_pack?.target_customer ||
      report.top_target_accounts?.[0]?.name ||
      report.target_accounts?.[0] ||
      "",
    vertical_scene:
      report.solution_delivery_pack?.vertical_scene ||
      report.research_focus ||
      report.market_intelligence?.tender_projects?.[0]?.industry_or_scene ||
      "",
    project_region: report.source_diagnostics?.scope_regions?.join(" / ") || "",
    implementation_window: report.tender_timeline?.[0] || "",
    investment_estimate: report.budget_signals?.[0] || "",
    construction_basis: "",
    scope_statement: report.strategic_directions?.[0] || report.project_distribution?.[0] || "",
    expected_benefits: report.five_year_outlook?.[0] || report.competition_analysis?.[0] || "",
    cross_validation_notes: report.followup_context?.supplemental_evidence || "",
    supplemental_context: report.followup_context?.supplemental_context || "",
    supplemental_evidence: report.followup_context?.supplemental_evidence || "",
    supplemental_requirements: report.followup_context?.supplemental_requirements || report.research_focus || "",
  };
}

export function buildResearchKeywordGroups(keyword: string, researchFocus?: string | null): string[] {
  const groups = [String(keyword || "").trim()]
    .concat(
      String(researchFocus || "")
        .split(/[，,、/｜|；;\n\s]+/)
        .map((item) => item.trim())
        .filter(Boolean),
    )
    .filter(Boolean);
  return Array.from(new Set(groups)).slice(0, 4);
}

export function buildResearchModeConfig(mode: ResearchMode) {
  if (mode === "fast") {
    return {
      research_mode: "fast" as const,
      deep_research: false,
      max_sources: 8,
      estimatedMinutes: 3,
    };
  }
  return {
    research_mode: "deep" as const,
    deep_research: true,
    max_sources: 18,
    estimatedMinutes: 6,
  };
}

export function qualityLabel(value: string) {
  if (value === "high") return "高";
  if (value === "medium") return "中";
  return "低";
}

export function classifyResearchSourceTier(
  source: ApiResearchReport["sources"][number],
): "official" | "media" | "aggregate" {
  const domain = String(source.domain || "").toLowerCase();
  const sourceType = String(source.source_type || "").toLowerCase();
  const sourceTier = String(source.source_tier || "").toLowerCase();
  if (sourceTier === "official" || sourceTier === "media" || sourceTier === "aggregate") {
    return sourceTier;
  }
  if (
    sourceType === "policy" ||
    sourceType === "procurement" ||
    sourceType === "filing" ||
    domain.endsWith(".gov.cn") ||
    domain.includes("gov.cn") ||
    domain.includes("ggzy.gov.cn") ||
    domain.includes("cninfo.com.cn") ||
    domain.includes("sec.gov") ||
    domain.includes("hkexnews.hk")
  ) {
    return "official";
  }
  if (
    sourceType === "tender_feed" ||
    domain.includes("jianyu") ||
    domain.includes("cecbid") ||
    domain.includes("cebpubservice") ||
    domain.includes("china-cpp") ||
    domain.includes("chinabidding")
  ) {
    return "aggregate";
  }
  return "media";
}

export function sourceTierLabel(value: string) {
  if (value === "official") return "官方源";
  if (value === "aggregate") return "聚合源";
  return "媒体源";
}

export function mapResearchStageToPipelineKey(stageKey?: string | null): ResearchPipelineKey {
  const normalized = String(stageKey || "").toLowerCase();
  if (
    normalized === "extracting" ||
    normalized === "scoping" ||
    normalized === "company_contacts" ||
    normalized === "expanding" ||
    normalized === "corrective"
  ) {
    return "clean";
  }
  if (
    normalized === "synthesizing" ||
    normalized === "ranking" ||
    normalized === "packaging" ||
    normalized === "completed"
  ) {
    return "analyze";
  }
  return "fetch";
}

export function defaultResearchPipelineSummary(key: ResearchPipelineKey) {
  if (key === "fetch") {
    return "汇总定向源、公开网页和公众号候选结果。";
  }
  if (key === "clean") {
    return "抽取正文、去重，并筛掉不匹配的来源。";
  }
  return "综合依据、排序公司与伙伴，并整理结构化结论。";
}
