import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ResearchRecoveryCard } from "@/components/inbox/research-recovery-card";
import type { ApiResearchJob } from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  submitResearchJobClarification: vi.fn(),
}));

vi.mock("@/lib/api", async () => ({
  submitResearchJobClarification: apiMock.submitResearchJobClarification,
}));

const parentJob = {
  id: "11111111-1111-1111-1111-111111111111",
  status: "needs_evidence",
  keyword: "城市文旅项目",
  output_language: "zh-CN",
  include_wechat: true,
  max_sources: 14,
  deep_research: true,
  progress_percent: 100,
  stage_key: "needs_evidence",
  stage_label: "等待补充",
  message: "",
  created_at: "2026-07-26T00:00:00Z",
  updated_at: "2026-07-26T00:05:00Z",
  interaction_state: "provisional",
  formal_delivery_allowed: false,
  clarification_packet: {
    schema_version: "research_clarification_v1",
    active: true,
    interaction_state: "provisional",
    reason_code: "near_threshold",
    title: "已生成可阅读草稿，还差少量证据",
    summary: "已采纳 7/8 条来源。草稿可供判断方向，但正式交付仍受保护。",
    accepted_source_count: 7,
    minimum_source_count: 8,
    evidence_snapshot_digest: "abc",
    can_view_provisional: true,
    formal_delivery_allowed: false,
    system_retryable: false,
    questions: [
      {
        question_id: "supporting_sources",
        input_kind: "file_or_url",
        prompt: "请补充 1-3 条官网、政策、采购公告或项目材料。",
        reason: "现有来源接近门槛。",
        required: true,
        placeholder: "",
        accepted_file_types: [".pdf", ".docx"],
        options: [],
      },
    ],
    recovery_options: [
      {
        action: "submit_answers",
        label: "补充资料并续跑",
        description: "保留当前证据。",
        recommended: true,
      },
      {
        action: "view_provisional",
        label: "先查看受限草稿",
        description: "不会解除正式交付保护。",
        recommended: false,
      },
    ],
    next_steps: ["已有来源会固定为父任务证据快照。"],
  },
} as ApiResearchJob;

describe("ResearchRecoveryCard", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    apiMock.submitResearchJobClarification.mockReset();
  });

  it("shows plain-language recovery and submits supplemental URLs", async () => {
    const childJob = {
      ...parentJob,
      id: "22222222-2222-2222-2222-222222222222",
      status: "queued",
      interaction_state: "recovering",
      clarification_packet: { ...parentJob.clarification_packet!, active: false },
    } as ApiResearchJob;
    apiMock.submitResearchJobClarification.mockResolvedValue({
      parent_job_id: parentJob.id,
      action: "submit_answers",
      idempotent_replay: false,
      parent_job: parentJob,
      child_job: childJob,
    });
    const onParentUpdated = vi.fn();
    const onRecoveryStarted = vi.fn();

    render(
      <ResearchRecoveryCard
        job={parentJob}
        onParentUpdated={onParentUpdated}
        onRecoveryStarted={onRecoveryStarted}
      />,
    );

    expect(screen.getByText("已生成可阅读草稿，还差少量证据")).toBeInTheDocument();
    expect(screen.queryByText("near_threshold")).not.toBeInTheDocument();
    expect(screen.queryByText("evidence_gap")).not.toBeInTheDocument();

    fireEvent.change(screen.getByPlaceholderText("每行一个官网、政策、采购公告或项目链接"), {
      target: { value: "https://example.gov.cn/policy" },
    });
    fireEvent.click(screen.getByRole("button", { name: "补充资料并续跑" }));

    await waitFor(() => expect(apiMock.submitResearchJobClarification).toHaveBeenCalledTimes(1));
    expect(apiMock.submitResearchJobClarification.mock.calls[0][1]).toMatchObject({
      action: "submit_answers",
      supplemental_urls: ["https://example.gov.cn/policy"],
    });
    expect(onParentUpdated).toHaveBeenCalledWith(parentJob);
    expect(onRecoveryStarted).toHaveBeenCalledWith(childJob);
  });

  it("requires a verifiable URL or file before starting another evidence recovery", async () => {
    const evidenceRequiredJob = {
      ...parentJob,
      recovery_attempt: 1,
      recovery_limit: 3,
      requires_evidence_input: true,
    } as ApiResearchJob;
    apiMock.submitResearchJobClarification.mockResolvedValue({
      parent_job_id: evidenceRequiredJob.id,
      action: "submit_answers",
      idempotent_replay: false,
      parent_job: evidenceRequiredJob,
      child_job: {
        ...evidenceRequiredJob,
        id: "33333333-3333-3333-3333-333333333333",
        status: "queued",
        recovery_attempt: 2,
      },
    });

    render(
      <ResearchRecoveryCard
        job={evidenceRequiredJob}
        onParentUpdated={vi.fn()}
        onRecoveryStarted={vi.fn()}
      />,
    );

    expect(screen.getByTestId("research-recovery-evidence-required")).toHaveTextContent(
      "仅填写文字不会再启动重复复核",
    );
    const resumeButton = screen.getByRole("button", { name: "补充资料并续跑" });
    expect(resumeButton).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText("会议背景、范围、约束或必须回答的问题"), {
      target: { value: "补充一段背景说明" },
    });
    expect(resumeButton).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText("每行一个官网、政策、采购公告或项目链接"), {
      target: { value: "example.gov.cn/policy" },
    });
    expect(resumeButton).toBeDisabled();

    fireEvent.change(screen.getByPlaceholderText("每行一个官网、政策、采购公告或项目链接"), {
      target: { value: "https://example.gov.cn/policy" },
    });
    expect(resumeButton).toBeEnabled();
    fireEvent.click(resumeButton);

    await waitFor(() => expect(apiMock.submitResearchJobClarification).toHaveBeenCalledTimes(1));
    expect(apiMock.submitResearchJobClarification.mock.calls[0][1]).toMatchObject({
      supplemental_urls: ["https://example.gov.cn/policy"],
      supplemental_text: "补充一段背景说明",
    });
  });

  it("closes exhausted recovery without exposing an action that creates another child", async () => {
    const exhaustedJob = {
      ...parentJob,
      recovery_attempt: 3,
      recovery_limit: 3,
      recovery_exhausted: true,
      requires_evidence_input: true,
      clarification_packet: {
        ...parentJob.clarification_packet!,
        active: false,
      },
    } as ApiResearchJob;
    apiMock.submitResearchJobClarification.mockResolvedValue({
      parent_job_id: exhaustedJob.id,
      action: "view_provisional",
      idempotent_replay: false,
      parent_job: exhaustedJob,
      child_job: null,
    });
    const onRecoveryStarted = vi.fn();

    render(
      <ResearchRecoveryCard
        job={exhaustedJob}
        onParentUpdated={vi.fn()}
        onRecoveryStarted={onRecoveryStarted}
      />,
    );

    expect(screen.getByTestId("research-recovery-round-summary")).toHaveTextContent(
      "系统不会再创建重复子任务",
    );
    expect(screen.getByTestId("research-recovery-exhausted")).toHaveTextContent(
      "已完成本任务可用的补证复核轮次",
    );
    expect(screen.queryByRole("button", { name: "补充资料并续跑" })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "先查看受限草稿" }));

    await waitFor(() => expect(apiMock.submitResearchJobClarification).toHaveBeenCalledTimes(1));
    expect(apiMock.submitResearchJobClarification.mock.calls[0][1]).toMatchObject({
      action: "view_provisional",
    });
    expect(onRecoveryStarted).not.toHaveBeenCalled();
  });
});
