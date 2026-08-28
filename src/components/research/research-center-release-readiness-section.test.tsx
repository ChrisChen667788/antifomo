import { render, screen, within } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { ResearchCenterReleaseReadinessSection } from "@/components/research/research-center-release-readiness-section";
import type { ReleaseReadinessSnapshot } from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  getReleaseReadiness: vi.fn(),
}));

vi.mock("@/lib/api", async () => ({
  getReleaseReadiness: apiMock.getReleaseReadiness,
}));

const snapshotFixture: ReleaseReadinessSnapshot = {
  generated_at: "2026-07-09T00:00:00Z",
  release_version: "1.9.1-executable-architecture-evidence",
  overall_status: "blocked",
  readiness_score: 63,
  summary_lines: [
    "1.9.1 Executable Architecture Evidence：2 pass / 2 watch / 2 blocked。",
    "总体 readiness score 63/100，overall_status=blocked。",
  ],
  gates: [
    {
      key: "health",
      label: "系统健康与稳定性",
      status: "pass",
      score: 100,
      target: "API/DB healthy, recent stability smoke passed",
      observed: "API route responding",
      summary: "API、数据库和最近 stability smoke 均通过。",
      evidence: [
        {
          label: "API health",
          status: "pass",
          summary: "`/healthz` 可由当前 FastAPI 进程提供。",
          source: "/healthz",
          details: {},
        },
      ],
      actions: [],
    },
    {
      key: "research_diagnostics",
      label: "Research Upgrade Diagnostics",
      status: "watch",
      score: 63,
      target: "status=ready and score>=80",
      observed: "63/100 · watch",
      summary: "15 轮研究升级诊断 ready 11/15，blocked 0/15。",
      evidence: [
        {
          label: "Diagnostics preview",
          status: "watch",
          summary: "复用 diagnostics payload。",
          source: "/api/research/upgrade-diagnostics/preview",
          details: {},
        },
      ],
      actions: [],
    },
    {
      key: "low_quality_audit",
      label: "低质量审计",
      status: "watch",
      score: 72,
      target: "flagged/total <= 10%, invalid_payloads=0",
      observed: "15/47 flagged · 0 invalid · 31.9%",
      summary: "低质量率仍未达到 ≤10%。",
      evidence: [],
      actions: [],
    },
    {
      key: "evidence_governance",
      label: "1.8.2/1.8.3 Evidence Governance",
      status: "pass",
      score: 100,
      target: "topic hard-negative blocked and supported claim gate passed",
      observed: "deterministic hard-negative/positive/claim fixtures passed",
      summary: "主题硬门禁、最低证据包和主张引用门确定性回归通过。",
      evidence: [],
      actions: [],
    },
    {
      key: "independent_review",
      label: "独立复核",
      status: "blocked",
      score: 0,
      target: "100/100 cases approved, reviewer metadata, attestation, digest valid",
      observed: "0/100 approved · pending",
      summary: "独立复核仍未完成，不能作为 release approval。",
      evidence: [],
      actions: [],
    },
    {
      key: "visual_gate",
      label: "视觉与 Office 门禁",
      status: "blocked",
      score: 45,
      target: "screenshots accepted, Office roundtrip pass, human visual confirmation recorded",
      observed: "视觉/Office 自动门禁存在失败或缺关键截图。",
      summary: "视觉/Office 自动门禁存在失败或缺关键截图。",
      evidence: [],
      actions: [],
    },
  ],
  next_actions: [
    {
      priority: "high",
      owner: "evaluation-owner",
      action: "完成 1.2.0 独立复核并生成 digest",
      reason: "pending template 不能代替独立批准。",
      gate_key: "independent_review",
      gate_label: "独立复核",
    },
    {
      priority: "medium",
      owner: "delivery-review",
      action: "补齐 Office/视觉确认 manifest",
      reason: "运行 office visual baseline。",
      gate_key: "visual_gate",
      gate_label: "视觉与 Office 门禁",
    },
  ],
  operator_commands: [
    {
      gate_key: "independent_review",
      gate_label: "独立复核",
      label: "校验独立复核 artifact",
      command: "npm run research:evaluate:review:validate -- --review .tmp/research-evaluation-independent-review.json",
      purpose: "验证 100/100 case approved、digest、reviewer metadata 和 attestation。",
    },
    {
      gate_key: "visual_gate",
      gate_label: "视觉与 Office 门禁",
      label: "生成 Office 视觉基线",
      command: "npm run office:visual-baseline",
      purpose: "生成 DOCX/PPTX/PDF artifact、结构校验和 visual fingerprint manifest。",
    },
  ],
  artifacts: [
    {
      gate_key: "independent_review",
      gate_label: "独立复核",
      label: "Independent review artifact",
      path: ".tmp/research-evaluation-independent-review.json",
      exists: true,
      status: "blocked",
      summary: "独立复核模板或最终批准 artifact；存在不代表已通过。",
    },
    {
      gate_key: "visual_gate",
      gate_label: "视觉与 Office 门禁",
      label: "roundtrip-manifest.json",
      path: ".tmp/formal-artifact-visual-baseline/roundtrip-manifest.json",
      exists: false,
      status: "watch",
      summary: "Office visual-baseline 或 roundtrip manifest 搜索路径。",
    },
  ],
};

describe("ResearchCenterReleaseReadinessSection", () => {
  beforeEach(() => {
    apiMock.getReleaseReadiness.mockReset();
  });

  it("renders release gates, evidence, and next actions", async () => {
    apiMock.getReleaseReadiness.mockResolvedValue(snapshotFixture);

    render(<ResearchCenterReleaseReadinessSection t={(_key, fallback) => fallback} />);

    expect(await screen.findByText("Evidence-Closed Research")).toBeInTheDocument();
    expect(screen.getByText("1.9.1-executable-architecture-evidence · 63/100 · blocked")).toBeInTheDocument();
    expect(screen.getByText("系统健康与稳定性")).toBeInTheDocument();
    expect(screen.getByText("Research Upgrade Diagnostics")).toBeInTheDocument();
    expect(screen.getByText("1.8.2/1.8.3 Evidence Governance")).toBeInTheDocument();
    expect(screen.getAllByText("独立复核").length).toBeGreaterThan(0);
    expect(screen.getAllByText("视觉与 Office 门禁").length).toBeGreaterThan(0);
    expect(screen.getByText("/api/research/upgrade-diagnostics/preview")).toBeInTheDocument();

    const actions = screen.getByText("Release blockers / next actions").closest("div");
    expect(actions).not.toBeNull();
    expect(within(actions as HTMLElement).getByText("完成 1.2.0 独立复核并生成 digest")).toBeInTheDocument();
    expect(within(actions as HTMLElement).getByText("补齐 Office/视觉确认 manifest")).toBeInTheDocument();
    expect(screen.getByText("Operator commands")).toBeInTheDocument();
    expect(screen.getByText("校验独立复核 artifact")).toBeInTheDocument();
    expect(screen.getByText("npm run office:visual-baseline")).toBeInTheDocument();
    expect(screen.getByText("Release artifacts")).toBeInTheDocument();
    expect(screen.getByText("Independent review artifact")).toBeInTheDocument();
    expect(screen.getByText(".tmp/research-evaluation-independent-review.json")).toBeInTheDocument();
  });
});
