import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LegacyResearchProgressCard } from "@/components/inbox/legacy-research-progress-card";

const baseProps = {
  progress: 42,
  stateLabel: "研究中",
  stageLabel: "正在检索",
  stageMessage: "正在整理来源",
  modeLabel: "深度调研",
  estimatedMinutes: 5,
  keywordGroups: ["城市文旅"],
  modeHint: "更全面，预计 5 分钟以上。",
  activePipelineLabel: "收集",
  pipelineStages: [
    {
      key: "fetch" as const,
      label: "收集",
      value: 12,
      summary: "收集公开来源",
      status: "active" as const,
    },
  ],
};

describe("LegacyResearchProgressCard", () => {
  it("keeps the standard progress wording for a root research job", () => {
    render(<LegacyResearchProgressCard {...baseProps} />);

    expect(screen.getByText("进度")).toBeInTheDocument();
    expect(screen.queryByTestId("research-recovery-progress-context")).not.toBeInTheDocument();
  });

  it("labels child-job progress as an independent recovery round and preserves the parent summary", () => {
    render(
      <LegacyResearchProgressCard
        {...baseProps}
        progress={2}
        stateLabel="补证复核中 · 第 2/3 轮"
        recoveryAttempt={2}
        recoveryLimit={3}
        previousRound={{
          progress: 100,
          stageLabel: "等待补充证据",
          acceptedSourceCount: 7,
        }}
      />,
    );

    expect(screen.getByText("上轮完成")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
    expect(screen.getByLabelText("本轮补证复核进度 2%")).toBeInTheDocument();
    expect(screen.getByTestId("research-recovery-progress-context")).toHaveTextContent(
      "第 2/3 轮补证复核 · 本轮 2%",
    );
    expect(screen.getByTestId("research-recovery-progress-context")).toHaveTextContent(
      "原任务与已有证据均已保留，并未归零",
    );
    expect(screen.getByTestId("research-previous-round-summary")).toHaveTextContent(
      "上一轮：等待补充证据 · 100% · 已保留 7 条有效来源",
    );
  });
});
