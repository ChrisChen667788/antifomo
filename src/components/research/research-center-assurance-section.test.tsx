import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResearchCenterAssuranceSection } from "@/components/research/research-center-assurance-section";
import type { ApiResearchAssuranceSnapshot } from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  getResearchAssurancePreview: vi.fn(),
}));

vi.mock("@/lib/api", async () => ({
  getResearchAssurancePreview: apiMock.getResearchAssurancePreview,
}));

const snapshotFixture: ApiResearchAssuranceSnapshot = {
  generated_at: "2026-08-10T00:00:00Z",
  program_version: "2.6.5",
  status: "blocked",
  score: 49,
  report_sample_size: 2,
  valid_report_count: 1,
  invalid_report_count: 1,
  summary_lines: [
    "2.5.1-2.6.5 质量保障计划：4 通过 / 4 关注 / 7 阻断。",
    "可解析研报 1/2；低质量队列 1/2。",
  ],
  next_actions: ["先迁移或隔离无法通过当前结构校验的历史研报。", "完成真实独立复核并归档复核工件。"],
  rounds: [
    {
      index: 1,
      version: "2.5.1",
      key: "payload_compatibility",
      label: "历史 payload 兼容性",
      status: "blocked",
      score: 25,
      summary: "已完成研报必须能被当前 schema 解析。",
      metrics: [
        {
          key: "report_schema",
          label: "可解析研报",
          observed: "1/2",
          target: "invalid payload = 0",
          status: "blocked",
          summary: "无法解析的历史数据不能进入质量判断。",
        },
      ],
      next_actions: ["迁移历史 payload"],
    },
    {
      index: 12,
      version: "2.6.2",
      key: "independent_review_packet",
      label: "独立复核工件",
      status: "blocked",
      score: 25,
      summary: "独立复核必须绑定锁定数据集和评审元数据。",
      metrics: [
        {
          key: "approved_cases",
          label: "独立复核批准",
          observed: "0/100",
          target: "100/100 已批准",
          status: "blocked",
          summary: "模板文件不等于完成的独立复核。",
        },
      ],
      next_actions: ["完成真实独立复核"],
    },
    {
      index: 15,
      version: "2.6.5",
      key: "assurance_command_center",
      label: "统一质量保障控制台",
      status: "blocked",
      score: 25,
      summary: "工程实现和外部验收状态统一在只读控制面呈现。",
      metrics: [
        {
          key: "round_completion",
          label: "通过轮次",
          observed: "4/14",
          target: "所有本地与外部门禁均通过",
          status: "blocked",
          summary: "不能用本地代码替代外部结论。",
        },
      ],
      next_actions: ["按阻断轮次补齐真实证据"],
    },
  ],
};

describe("ResearchCenterAssuranceSection", () => {
  beforeEach(() => {
    apiMock.getResearchAssurancePreview.mockReset();
  });

  it("renders assurance rounds, observed evidence, and next actions", async () => {
    apiMock.getResearchAssurancePreview.mockResolvedValue(snapshotFixture);

    render(<ResearchCenterAssuranceSection t={(_key, fallback) => fallback} />);

    expect(await screen.findByText("质量保障")).toBeInTheDocument();
    expect(screen.getByTestId("research-assurance-section")).toBeInTheDocument();
    expect(screen.getByText("2.6.5 · 49/100 · 阻断")).toBeInTheDocument();
    expect(screen.getByText("查看全部 3 轮核验项")).toBeInTheDocument();
    expect(screen.getByText("2.5.1 · 历史 payload 兼容性")).toBeInTheDocument();
    expect(screen.getByText("2.6.2 · 独立复核工件")).toBeInTheDocument();
    expect(screen.getByText("可解析研报")).toBeInTheDocument();
    expect(screen.getByText("当前优先动作")).toBeInTheDocument();
    expect(screen.getByText("完成真实独立复核并归档复核工件。")).toBeInTheDocument();
  });
});
