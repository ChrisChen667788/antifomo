import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ModelControlPlanePanel } from "@/components/settings/model-control-plane-panel";
import type {
  ModelControlPlaneSnapshot,
  StrongestModelUpgrade,
  SupportedModelScan,
} from "@/lib/api";

const apiMock = vi.hoisted(() => ({
  getModelControlPlane: vi.fn(),
  scanSupportedModels: vi.fn(),
  upgradeToStrongestModels: vi.fn(),
}));

vi.mock("@/lib/api", async () => ({
  getModelControlPlane: apiMock.getModelControlPlane,
  scanSupportedModels: apiMock.scanSupportedModels,
  upgradeToStrongestModels: apiMock.upgradeToStrongestModels,
}));

const snapshotFixture: ModelControlPlaneSnapshot = {
  generated_at: "2026-07-12T00:00:00Z",
  policy_version: "2026-07-12.1",
  routes: [
    {
      key: "generation",
      label: "通用生成路由",
      provider: "openai",
      effective_provider: "openai",
      model: "gpt-5.4",
      base_url: "https://models.example/v1",
      strategy: "结构化输出：json_schema",
      fallback: "远程失败回退 deterministic mock",
      status: "configured",
      upgrade_managed: true,
    },
    {
      key: "strategy",
      label: "复杂策略路由",
      provider: "openai",
      effective_provider: "openai",
      model: "claude-sonnet-4-7",
      base_url: "https://models.example/v1",
      strategy: "低温度独立推理",
      fallback: "失败时保留规则结果",
      status: "configured",
      upgrade_managed: true,
    },
  ],
  modules: [
    {
      key: "research_generation",
      label: "研报主报告生成",
      area: "研究",
      route_key: "generation",
      provider: "openai",
      model: "gpt-5.4",
      strategy: "基于检索证据生成结构化主报告",
      fallback: "远程失败回退 deterministic mock",
      status: "configured",
      upgrade_managed: true,
    },
    {
      key: "wechat_parser",
      label: "微信收藏导入与解析",
      area: "采集",
      route_key: "deterministic",
      provider: "rule_based",
      model: null,
      strategy: "确定性解析 URL 与文本块",
      fallback: "无模型依赖",
      status: "local",
      upgrade_managed: false,
    },
  ],
};

const scanFixture: SupportedModelScan = {
  generated_at: "2026-07-12T00:01:00Z",
  policy_version: "2026-07-12.1",
  status: "ready",
  total_discovered: 3,
  message: "扫描完成，共发现 3 个模型，可安全执行整批升级。",
  routes: [
    {
      route_key: "generation",
      label: "通用生成与视觉路由",
      provider: "openai",
      base_url: "https://models.example/v1",
      status: "ready",
      model_count: 3,
      models: ["gpt-5.5", "gpt-5.5-vision", "claude-opus-4-7"],
      error_code: "",
      message: "已发现 3 个模型。",
    },
  ],
  recommendations: [
    {
      role: "generation",
      route_key: "generation",
      model: "gpt-5.5",
      current_model: "gpt-5.4",
      change_required: true,
      score: 955,
      reason: "GPT 系列，按旗舰等级排序",
    },
    {
      role: "strategy",
      route_key: "strategy",
      model: "claude-opus-4-7",
      current_model: "claude-sonnet-4-7",
      change_required: true,
      score: 992,
      reason: "Claude 系列，按旗舰等级排序",
    },
    {
      role: "vision",
      route_key: "generation",
      model: "gpt-5.5-vision",
      current_model: "gpt-5.4",
      change_required: true,
      score: 1045,
      reason: "GPT 系列，按视觉适配度排序",
    },
  ],
  models: [
    {
      id: "gpt-5.5",
      owned_by: "openai",
      created: 20,
      routes: ["generation", "strategy"],
      capabilities: ["generation", "strategy", "vision"],
      excluded: false,
      exclusion_reason: "",
      scores: { generation: 955, strategy: 910, vision: 955 },
      rank_reason: "GPT 系列，按旗舰等级排序",
    },
    {
      id: "gpt-5.5-vision",
      owned_by: "openai",
      created: 21,
      routes: ["generation"],
      capabilities: ["generation", "strategy", "vision"],
      excluded: false,
      exclusion_reason: "",
      scores: { generation: 885, strategy: 840, vision: 1045 },
      rank_reason: "GPT 系列，按视觉适配度排序",
    },
    {
      id: "claude-opus-4-7",
      owned_by: "anthropic",
      created: 19,
      routes: ["strategy"],
      capabilities: ["generation", "strategy", "vision"],
      excluded: false,
      exclusion_reason: "",
      scores: { generation: 912, strategy: 992, vision: 912 },
      rank_reason: "Claude 系列，按策略适配度排序",
    },
  ],
};

describe("ModelControlPlanePanel", () => {
  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    apiMock.getModelControlPlane.mockReset();
    apiMock.scanSupportedModels.mockReset();
    apiMock.upgradeToStrongestModels.mockReset();
    apiMock.getModelControlPlane.mockResolvedValue(snapshotFixture);
  });

  it("shows module routes and scans the complete provider catalog", async () => {
    apiMock.scanSupportedModels.mockResolvedValue(scanFixture);

    render(<ModelControlPlanePanel />);

    expect((await screen.findAllByText("研报主报告生成")).length).toBeGreaterThan(0);
    expect(screen.getAllByText("微信收藏导入与解析").length).toBeGreaterThan(0);
    fireEvent.click(screen.getByRole("button", { name: "扫描全部模型" }));

    await waitFor(() => expect(apiMock.scanSupportedModels).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("模型扫描结果")).toBeInTheDocument();
    expect(screen.getByText("发现 3 个模型 · policy 2026-07-12.1")).toBeInTheDocument();
    expect(screen.getAllByText("gpt-5.5").length).toBeGreaterThan(0);
    expect(screen.getAllByText("claude-opus-4-7").length).toBeGreaterThan(0);
  });

  it("runs the one-click upgrade and reloads current bindings", async () => {
    const upgrade: StrongestModelUpgrade = {
      generated_at: "2026-07-12T00:02:00Z",
      status: "applied",
      previous_models: {
        openai_model: "gpt-5.4",
        openai_vision_model: "gpt-5.4",
        strategy_openai_model: "claude-sonnet-4-7",
      },
      applied_models: {
        openai_model: "gpt-5.5",
        openai_vision_model: "gpt-5.5-vision",
        strategy_openai_model: "claude-opus-4-7",
      },
      changed_fields: ["openai_model", "openai_vision_model", "strategy_openai_model"],
      persisted: true,
      runtime_reloaded: true,
      message: "已更新 3 个模型配置，并热刷新运行时。",
      scan: scanFixture,
    };
    apiMock.upgradeToStrongestModels.mockResolvedValue(upgrade);

    render(<ModelControlPlanePanel />);
    fireEvent.click(await screen.findByRole("button", { name: "更新到最强模型" }));

    await waitFor(() => expect(apiMock.upgradeToStrongestModels).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("已更新 3 个模型配置，并热刷新运行时。")).toBeInTheDocument();
    expect(apiMock.getModelControlPlane).toHaveBeenCalledTimes(2);
  });
});
