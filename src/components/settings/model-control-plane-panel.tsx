"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getModelControlPlane,
  scanSupportedModels,
  upgradeToStrongestModels,
  type ModelControlPlaneSnapshot,
  type ModelRouteStatus,
  type SupportedModelScan,
} from "@/lib/api";

const roleLabels: Record<string, string> = {
  generation: "通用生成",
  strategy: "复杂策略",
  vision: "视觉识别",
};

const statusLabels: Record<ModelRouteStatus, string> = {
  configured: "已配置",
  fallback: "回退运行",
  disabled: "未启用",
  local: "本地执行",
  external: "外部运行时",
};

function StatusBadge({ status }: { status: string }) {
  const ready = status === "ready" || status === "configured" || status === "local" || status === "applied" || status === "no_change";
  const blocked = status === "blocked" || status === "disabled";
  return (
    <span
      className={`af-chip inline-flex px-2.5 py-1 text-xs font-semibold ${
        ready
          ? "af-chip-success"
          : blocked
            ? "af-chip-danger"
            : "af-chip-warning"
      }`}
    >
      {status === "ready" ? "就绪" : statusLabels[status as ModelRouteStatus] ?? status}
    </span>
  );
}

export function ModelControlPlanePanel() {
  const [snapshot, setSnapshot] = useState<ModelControlPlaneSnapshot | null>(null);
  const [scan, setScan] = useState<SupportedModelScan | null>(null);
  const [busy, setBusy] = useState<"load" | "scan" | "upgrade" | "">("load");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const loadSnapshot = useCallback(async () => {
    setError("");
    try {
      const result = await getModelControlPlane();
      setSnapshot(result);
    } catch {
      setError("读取模型路由失败，请确认后端服务已启动。");
    }
  }, []);

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const result = await getModelControlPlane();
        if (active) setSnapshot(result);
      } catch {
        if (active) setError("读取模型路由失败，请确认后端服务已启动。");
      } finally {
        if (active) setBusy("");
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, []);

  const refresh = async () => {
    setBusy("load");
    setMessage("");
    await loadSnapshot();
    setBusy("");
  };

  const runScan = async () => {
    setBusy("scan");
    setError("");
    setMessage("");
    try {
      const result = await scanSupportedModels();
      setScan(result);
      setMessage(result.message);
    } catch {
      setError("模型扫描请求失败，未修改任何配置。");
    } finally {
      setBusy("");
    }
  };

  const runUpgrade = async () => {
    setBusy("upgrade");
    setError("");
    setMessage("");
    try {
      const result = await upgradeToStrongestModels();
      setScan(result.scan);
      setMessage(result.message);
      await loadSnapshot();
    } catch {
      setError("模型升级请求失败，当前配置保持不变。");
    } finally {
      setBusy("");
    }
  };

  return (
    <section className="af-glass rounded-lg p-5 md:p-6">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <p className="af-kicker">模型控制台</p>
          <h2 className="mt-2 text-lg font-semibold text-[var(--af-text-primary)]">模块模型与策略</h2>
          <p className="mt-1 text-sm text-[var(--af-text-secondary)]">
            查看实际运行路由，扫描供应商支持的模型，并按能力策略整批升级。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
            disabled={Boolean(busy)}
            onClick={() => void refresh()}
          >
            {busy === "load" ? "刷新中..." : "刷新路由"}
          </button>
          <button
            type="button"
            className="af-btn af-btn-secondary disabled:cursor-not-allowed disabled:opacity-60"
            disabled={Boolean(busy)}
            onClick={() => void runScan()}
          >
            {busy === "scan" ? "扫描中..." : "扫描全部模型"}
          </button>
          <button
            type="button"
            className="af-btn af-btn-primary disabled:cursor-not-allowed disabled:opacity-60"
            disabled={Boolean(busy)}
            onClick={() => void runUpgrade()}
          >
            {busy === "upgrade" ? "升级中..." : "更新到最强模型"}
          </button>
        </div>
      </div>

      <div aria-live="polite">
        {message ? <p className="mt-4 text-sm text-[var(--af-info)]">{message}</p> : null}
        {error ? <p className="mt-4 text-sm text-[var(--af-danger)]">{error}</p> : null}
      </div>

      {snapshot ? (
        <>
          <div className="mt-5 space-y-3 md:hidden">
            {snapshot.routes.map((route) => (
              <article key={route.key} className="af-subpanel p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="font-semibold text-[var(--af-text-primary)]">{route.label}</p>
                    <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">{route.effective_provider}</p>
                  </div>
                  <StatusBadge status={route.status} />
                </div>
                <p className="mt-3 break-all font-mono text-xs text-[var(--af-text-primary)]">{route.model || "无独立模型"}</p>
                <p className="mt-2 text-xs leading-5 text-[var(--af-text-secondary)]">{route.strategy}</p>
                <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">{route.fallback}</p>
                {route.base_url ? <p className="mt-2 break-all text-xs text-[var(--af-text-tertiary)]">{route.base_url}</p> : null}
              </article>
            ))}
          </div>

          <div className="mt-5 hidden overflow-x-auto md:block">
            <table className="w-full min-w-[780px] border-collapse text-left text-sm">
              <thead>
                <tr className="border-b border-[var(--af-border-subtle)] text-xs text-[var(--af-text-tertiary)]">
                  <th className="px-3 py-2 font-semibold">运行路由</th>
                  <th className="px-3 py-2 font-semibold">供应商</th>
                  <th className="px-3 py-2 font-semibold">当前模型</th>
                  <th className="px-3 py-2 font-semibold">策略与回退</th>
                  <th className="px-3 py-2 font-semibold">状态</th>
                </tr>
              </thead>
              <tbody>
                {snapshot.routes.map((route) => (
                  <tr key={route.key} className="border-b border-[var(--af-border-subtle)] align-top">
                    <td className="px-3 py-3 font-semibold text-[var(--af-text-primary)]">{route.label}</td>
                    <td className="px-3 py-3 text-[var(--af-text-secondary)]">
                      <p>{route.effective_provider}</p>
                      {route.base_url ? <p className="mt-1 break-all text-xs text-[var(--af-text-tertiary)]">{route.base_url}</p> : null}
                    </td>
                    <td className="px-3 py-3 font-mono text-xs text-[var(--af-text-primary)]">{route.model || "无独立模型"}</td>
                    <td className="max-w-[360px] px-3 py-3 text-xs leading-5 text-[var(--af-text-secondary)]">
                      <p>{route.strategy}</p>
                      <p className="mt-1 text-[var(--af-text-tertiary)]">{route.fallback}</p>
                    </td>
                    <td className="px-3 py-3"><StatusBadge status={route.status} /></td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="mt-6">
            <div className="flex flex-wrap items-end justify-between gap-2">
              <div>
                <h3 className="text-sm font-semibold text-[var(--af-text-primary)]">模块绑定</h3>
                <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">策略版本 {snapshot.policy_version}</p>
              </div>
              <p className="text-xs text-[var(--af-text-tertiary)]">共 {snapshot.modules.length} 个 AI/规则模块</p>
            </div>
            <div className="mt-3 space-y-3 md:hidden">
              {snapshot.modules.map((module) => (
                <article key={module.key} className="af-subpanel p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="font-semibold text-[var(--af-text-primary)]">{module.label}</p>
                      <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">{module.area} · {module.provider}</p>
                    </div>
                    <span className="shrink-0 text-xs text-[var(--af-text-tertiary)]">
                      {module.upgrade_managed ? "跟随升级" : "独立"}
                    </span>
                  </div>
                  <p className="mt-3 break-all font-mono text-xs text-[var(--af-text-primary)]">{module.model || "无模型 / 运行时决定"}</p>
                  <p className="mt-2 text-xs leading-5 text-[var(--af-text-secondary)]">{module.strategy}</p>
                </article>
              ))}
            </div>
            <div className="mt-3 hidden overflow-x-auto md:block">
              <table className="w-full min-w-[860px] border-collapse text-left text-sm">
                <thead>
                  <tr className="border-b border-[var(--af-border-subtle)] text-xs text-[var(--af-text-tertiary)]">
                    <th className="px-3 py-2 font-semibold">模块</th>
                    <th className="px-3 py-2 font-semibold">底层模型</th>
                    <th className="px-3 py-2 font-semibold">执行策略</th>
                    <th className="px-3 py-2 font-semibold">升级管理</th>
                  </tr>
                </thead>
                <tbody>
                  {snapshot.modules.map((module) => (
                    <tr key={module.key} className="border-b border-[var(--af-border-subtle)] align-top">
                      <td className="px-3 py-3">
                        <p className="font-semibold text-[var(--af-text-primary)]">{module.label}</p>
                        <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">{module.area} · {module.provider}</p>
                      </td>
                      <td className="px-3 py-3 font-mono text-xs text-[var(--af-text-primary)]">{module.model || "无模型 / 运行时决定"}</td>
                      <td className="max-w-[420px] px-3 py-3 text-xs leading-5 text-[var(--af-text-secondary)]">
                        {module.strategy}
                      </td>
                      <td className="px-3 py-3 text-xs text-[var(--af-text-secondary)]">
                        {module.upgrade_managed ? "跟随一键升级" : "保持独立"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      ) : busy === "load" ? (
        <p className="mt-5 text-sm text-[var(--af-text-secondary)]">正在读取模型路由...</p>
      ) : null}

      {scan ? <ModelScanResults scan={scan} /> : null}
    </section>
  );
}

function ModelScanResults({ scan }: { scan: SupportedModelScan }) {
  return (
    <div className="mt-7 border-t border-[var(--af-border-subtle)] pt-5">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h3 className="text-sm font-semibold text-[var(--af-text-primary)]">模型扫描结果</h3>
          <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
            发现 {scan.total_discovered} 个模型 · policy {scan.policy_version}
          </p>
        </div>
        <StatusBadge status={scan.status} />
      </div>

      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
        {scan.recommendations.map((recommendation) => (
          <div key={recommendation.role} className="af-subpanel p-4">
            <p className="text-xs text-[var(--af-text-tertiary)]">{roleLabels[recommendation.role]}</p>
            <p className="mt-1 break-all font-mono text-sm font-semibold text-[var(--af-text-primary)]">{recommendation.model}</p>
            <p className="mt-2 text-xs text-[var(--af-text-secondary)]">
              当前：{recommendation.current_model || "未配置"} · 评分 {recommendation.score}
            </p>
            <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">{recommendation.reason}</p>
          </div>
        ))}
      </div>

      <div className="mt-4 space-y-2">
        {scan.routes.map((route) => (
          <div key={route.route_key} className="flex flex-wrap items-center justify-between gap-2 border-b border-[var(--af-border-subtle)] px-1 py-2 text-xs">
            <span className="font-semibold text-[var(--af-text-primary)]">{route.label}</span>
            <span className="text-[var(--af-text-secondary)]">{route.message}</span>
            <StatusBadge status={route.status} />
          </div>
        ))}
      </div>

      <div className="mt-5 max-h-[420px] space-y-3 overflow-auto md:hidden">
        {scan.models.map((model) => (
          <article key={model.id} className="af-subpanel p-4">
            <p className="break-all font-mono text-xs font-semibold text-[var(--af-text-primary)]">{model.id}</p>
            <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">{model.owned_by || "unknown"} · {model.routes.join(" / ")}</p>
            <p className="mt-2 text-xs text-[var(--af-text-secondary)]">能力：{model.capabilities.join("、") || "不适用"}</p>
            <p className="mt-1 font-mono text-xs text-[var(--af-text-secondary)]">
              生成 / 策略 / 视觉：{model.scores.generation ?? -1} / {model.scores.strategy ?? -1} / {model.scores.vision ?? -1}
            </p>
            <p className={`mt-2 text-xs leading-5 ${model.excluded ? "text-[var(--af-danger)]" : "text-[var(--af-text-tertiary)]"}`}>
              {model.excluded ? model.exclusion_reason : model.rank_reason}
            </p>
          </article>
        ))}
      </div>

      <div className="mt-5 hidden max-h-[420px] overflow-auto border-y border-[var(--af-border-subtle)] md:block">
        <table className="w-full min-w-[760px] border-collapse text-left text-xs">
          <thead className="sticky top-0 bg-[var(--af-surface-elevated)] text-[var(--af-text-tertiary)]">
            <tr>
              <th className="px-3 py-2 font-semibold">模型</th>
              <th className="px-3 py-2 font-semibold">能力</th>
              <th className="px-3 py-2 font-semibold">生成 / 策略 / 视觉</th>
              <th className="px-3 py-2 font-semibold">扫描结论</th>
            </tr>
          </thead>
          <tbody>
            {scan.models.map((model) => (
              <tr key={model.id} className="border-t border-[var(--af-border-subtle)] align-top">
                <td className="px-3 py-3">
                  <p className="font-mono font-semibold text-[var(--af-text-primary)]">{model.id}</p>
                  <p className="mt-1 text-[var(--af-text-tertiary)]">{model.owned_by || "unknown"} · {model.routes.join(" / ")}</p>
                </td>
                <td className="px-3 py-3 text-[var(--af-text-secondary)]">{model.capabilities.join("、") || "不适用"}</td>
                <td className="px-3 py-3 font-mono text-[var(--af-text-secondary)]">
                  {model.scores.generation ?? -1} / {model.scores.strategy ?? -1} / {model.scores.vision ?? -1}
                </td>
                <td className={`max-w-[320px] px-3 py-3 leading-5 ${model.excluded ? "text-[var(--af-danger)]" : "text-[var(--af-text-secondary)]"}`}>
                  {model.excluded ? model.exclusion_reason : model.rank_reason}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
