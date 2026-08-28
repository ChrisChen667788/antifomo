import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ResearchReportInsightsSection } from "@/components/inbox/research-report-insights-section";
import type { ApiResearchReport } from "@/lib/api/types";

const sections = [
  {
    title: "市场判断",
    items: ["已有公开政策和采购线索支持继续核验。"],
    status: "needs_evidence",
    confidence_tone: "medium",
    evidence_density: "medium",
    source_quality: "high",
  },
  {
    title: "候选证据复核清单",
    items: ["rejected | 媒体标题 | 未命中目标行业"],
    status: "needs_evidence",
    confidence_tone: "low",
    evidence_density: "low",
    source_quality: "low",
  },
] as ApiResearchReport["sections"];

describe("ResearchReportInsightsSection", () => {
  it("keeps internal source-admission diagnostics out of the default result layer", () => {
    render(
      <ResearchReportInsightsSection
        sections={sections}
        insightsTitle="深度洞察"
        insightsDesc="按主题查看判断"
        confidenceToneMeta={() => ({ panel: "", badge: "", item: "", excerpt: "" })}
        sectionStatusMeta={() => ({ label: "待核验", className: "" })}
        qualityTone={() => ""}
        qualityLabel={(value) => value}
        sourceTierLabel={(value) => value}
      />,
    );

    expect(screen.getByText("市场判断")).toBeInTheDocument();
    expect(screen.queryByText("候选证据复核清单")).not.toBeInTheDocument();
    expect(screen.queryByText(/rejected \|/i)).not.toBeInTheDocument();
  });
});
