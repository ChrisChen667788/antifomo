"use client";

import { useEffect, useMemo, useState } from "react";
import {
  getIterationProgram,
  getIterationProgramPreview,
  initializeIterationProgram,
  type ApiProductStrategyIterationProgram,
} from "@/lib/api";
import { AppIcon } from "@/components/ui/app-icon";

const decisionLabels = {
  build: "构建",
  integrate: "整合",
  defer: "暂缓",
  explicitly_not_copy: "明确不复制",
} as const;

export function CompetitiveIterationProgram() {
  const [snapshot, setSnapshot] = useState<ApiProductStrategyIterationProgram | null>(null);
  const [loading, setLoading] = useState(true);
  const [initializing, setInitializing] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const load = async () => {
      try {
        const [preview, persisted] = await Promise.all([
          getIterationProgramPreview(),
          getIterationProgram().catch(() => null),
        ]);
        if (active) setSnapshot(persisted?.initialized ? persisted : preview);
      } catch {
        if (active) setError("无法读取 2.10.3–2.11.7 迭代控制面；请确认后端已加载最新 product-strategy 路由。");
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, []);

  const workstreams = useMemo(
    () => new Set(snapshot?.iterations.map((iteration) => iteration.workstream) ?? []).size,
    [snapshot],
  );

  const initialize = async () => {
    if (!window.confirm("将 15 个受治理迭代记录写入本地台账。它不会批准执行、Office/视觉验收或生产发布，是否继续？")) {
      return;
    }
    setInitializing(true);
    setError("");
    try {
      setSnapshot(await initializeIterationProgram());
    } catch {
      setError("迭代台账初始化失败；未授权任何 Agent 动作或发布。请检查后端日志后重试。");
    } finally {
      setInitializing(false);
    }
  };

  return (
    <section
      className="rounded-[28px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] p-5 shadow-[var(--af-shadow-soft)]"
      data-testid="competitive-iteration-program"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-3xl">
          <p className="af-kicker">2.10.3–2.11.7 Development</p>
          <h3 className="mt-2 text-xl font-semibold text-[var(--af-text-primary)]">15 版本受治理迭代与 Agent 能力观察</h3>
          <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
            将执行提案、来源变更、Office/视觉证据、权限、回滚、性能、双周竞品监测和独立审计交接放进同一条可复核链；本地控制面完成不等于功能验收或生产授权。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="af-chip af-chip-warning">全部迭代 HOLD</span>
          <span className={snapshot?.initialized ? "af-chip af-chip-success" : "af-chip bg-slate-100 text-slate-700"}>
            {snapshot?.initialized ? "本地台账已初始化" : "只读预览"}
          </span>
          {snapshot && !snapshot.initialized ? (
            <button className="af-btn af-btn-primary px-3 py-2 text-xs" type="button" disabled={initializing} onClick={() => void initialize()}>
              {initializing ? "初始化中..." : "初始化 15 版本台账"}
            </button>
          ) : null}
        </div>
      </div>

      {loading ? <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">正在读取迭代与官方来源...</p> : null}
      {error ? <p className="mt-4 rounded-[16px] bg-rose-50 px-3 py-2 text-sm text-rose-700">{error}</p> : null}

      {snapshot ? (
        <>
          <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Metric label="版本切片" value={`${snapshot.iterations.length} 个`} />
            <Metric label="工作流" value={`${workstreams} 类`} />
            <Metric label="新增 Agent 来源" value={`${snapshot.agent_sources.length} 个`} />
            <Metric label="来源失效" value={formatDate(snapshot.expires_at)} />
          </div>

          <div className="mt-4 rounded-[18px] border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-900">
            <p className="font-semibold">硬门禁未变化</p>
            <p className="mt-1">
              `baseline_hybrid` 仍是唯一生产默认；竞品来源均为厂商主张，Office/视觉/具名人工验收、真实任务、shadow、漂移与回滚证据未齐前，不能自动执行、验收或发布。
            </p>
          </div>

          <div className="mt-5">
            <div className="flex flex-wrap items-baseline justify-between gap-2">
              <div>
                <p className="af-kicker">Official Agent Watch</p>
                <h4 className="mt-1 text-base font-semibold text-[var(--af-text-primary)]">国内外模型与 Agent 官方能力观察</h4>
              </div>
              <p className="text-xs text-[var(--af-text-tertiary)]">厂商主张 · 观察于 {formatDate(snapshot.observed_at)}</p>
            </div>
            <div className="mt-3 grid gap-3 lg:grid-cols-2">
              {snapshot.agent_sources.map((source) => (
                <article key={source.catalog_key} className="rounded-[20px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div>
                      <p className="text-xs text-[var(--af-text-tertiary)]">{source.vendor}</p>
                      <h5 className="mt-1 font-semibold text-[var(--af-text-primary)]">{source.product_name}</h5>
                    </div>
                    <span className={source.evidence.status === "stale" ? "af-chip af-chip-warning" : "af-chip bg-sky-100 text-sky-700"}>
                      {source.evidence.status === "stale" ? "来源已过期" : "厂商声明，未独立验证"}
                    </span>
                  </div>
                  <p className="mt-3 text-xs leading-5 text-[var(--af-text-secondary)]">{source.vendor_claim}</p>
                  <p className="mt-3 text-xs leading-5 text-[var(--af-text-secondary)]"><span className="font-semibold text-[var(--af-text-primary)]">模型信号：</span>{source.current_model_signal}</p>
                  <p className="mt-3 rounded-[14px] bg-[var(--af-surface-muted)] px-3 py-2 text-xs leading-5 text-[var(--af-text-secondary)]">
                    <span className="font-semibold text-[var(--af-text-primary)]">Anti-FOMO：</span>{source.anti_fomo_decision}
                  </p>
                  <a className="mt-3 inline-flex items-center gap-1 text-xs font-medium text-[var(--af-info)] hover:underline" href={source.source_url} target="_blank" rel="noreferrer">
                    官方来源 <AppIcon name="external" className="h-3.5 w-3.5" />
                  </a>
                </article>
              ))}
            </div>
          </div>

          <div className="mt-6">
            <p className="af-kicker">Iteration Train</p>
            <h4 className="mt-1 text-base font-semibold text-[var(--af-text-primary)]">15 个版本的开发与证据边界</h4>
            <div className="mt-3 space-y-2">
              {snapshot.iterations.map((iteration) => (
                <details key={iteration.iteration_key} className="group rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4" open={iteration.sequence <= 2}>
                  <summary className="cursor-pointer list-none">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex min-w-0 items-center gap-3">
                        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full bg-[var(--af-surface-muted)] text-xs font-semibold text-[var(--af-text-primary)]">{iteration.sequence}</span>
                        <div className="min-w-0">
                          <p className="text-[11px] font-mono text-[var(--af-text-tertiary)]">{iteration.version}</p>
                          <p className="truncate text-sm font-semibold text-[var(--af-text-primary)]">{iteration.title}</p>
                        </div>
                      </div>
                      <div className="flex gap-2">
                        <span className="af-chip bg-slate-100 text-slate-700">{decisionLabels[iteration.decision]}</span>
                        <span className="af-chip af-chip-warning">HOLD</span>
                      </div>
                    </div>
                  </summary>
                  <div className="mt-4 grid gap-3 text-xs leading-5 text-[var(--af-text-secondary)] lg:grid-cols-2">
                    <Info title="目标" value={iteration.purpose} />
                    <Info title="范围边界" value={iteration.scope_boundary} />
                    <List title="本地交付物" items={iteration.delivery_artifacts} />
                    <List title="外部证据仍需" items={iteration.external_evidence_requirements} />
                  </div>
                </details>
              ))}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[16px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
      <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">{label}</p>
      <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{value}</p>
    </div>
  );
}

function Info({ title, value }: { title: string; value: string }) {
  return <p className="rounded-[14px] bg-[var(--af-surface-muted)] px-3 py-2"><span className="font-semibold text-[var(--af-text-primary)]">{title}：</span>{value}</p>;
}

function List({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-[14px] bg-[var(--af-surface-muted)] px-3 py-2">
      <p className="font-semibold text-[var(--af-text-primary)]">{title}</p>
      <ul className="mt-1 space-y-1">{items.map((item) => <li key={item}>• {item}</li>)}</ul>
    </div>
  );
}

function formatDate(value: string): string {
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString("zh-CN");
}
