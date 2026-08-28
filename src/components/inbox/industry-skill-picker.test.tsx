import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { IndustrySkillPicker } from "@/components/inbox/industry-skill-picker";

describe("IndustrySkillPicker", () => {
  it("shows local skill coverage and lets the user change an explicit selection", () => {
    const onEnabledChange = vi.fn();
    const onSelectionChange = vi.fn();
    render(
      <IndustrySkillPicker
        loading={false}
        enabled
        selectedSkillIds={["industry.tourism_hospitality.local_reference"]}
        onEnabledChange={onEnabledChange}
        onSelectionChange={onSelectionChange}
        library={{
          status: "available",
          catalog_version: "industry-skill-library-v1-2026-08-12",
          document_count: 709,
          skill_count: 12,
          available_industries: ["文旅与酒店"],
          knowledge_base: {
            status: "ready",
            document_count: 709,
            full_text_document_count: 709,
            ocr_document_count: 57,
            ocr_pending_count: 0,
            unsupported_count: 1,
            passage_count: 12000,
            keyword_index_status: "ready",
            vector_index_status: "ready",
            vector_model: "BAAI/bge-large-zh",
            requested_vector_model: "BAAI/bge-m3",
            vector_fallback_reason: "",
            hybrid_search_enabled: true,
            warnings: [],
          },
          warnings: [],
          suggested_skills: [
            {
              skill_id: "industry.tourism_hospitality.local_reference",
              name: "文旅与酒店资料技能",
              industry: "tourism_hospitality",
              industry_label: "文旅与酒店",
              description: "本地参考资料。",
              document_count: 34,
              full_content_document_count: 34,
              document_type_counts: { 白皮书: 12, 行业报告: 22 },
              selection_reason: "与当前行业/场景关键词匹配",
              guidance: [],
              quality_checklist: [],
              learned_outline: [],
              reference_highlights: [],
              references: [],
            },
          ],
        }}
      />,
    );

    expect(screen.getByText("已索引 709 份资料，沉淀 12 个行业技能。最多选择 3 个技能。")).toBeInTheDocument();
    const skillButton = screen.getByRole("button", { name: /文旅与酒店资料技能/ });
    expect(skillButton).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(skillButton);
    expect(onSelectionChange).toHaveBeenCalledWith([]);

    fireEvent.click(screen.getByLabelText("启用"));
    expect(onEnabledChange).toHaveBeenCalledWith(false);
  });
});
