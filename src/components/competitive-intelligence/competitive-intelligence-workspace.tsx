"use client";

import { useEffect, useMemo, useState } from "react";
import {
  getCompetitiveLandscape,
  getCompetitiveLandscapePreview,
  seedCompetitiveLandscape,
  type ApiProductStrategyCompetitiveLandscape,
  type ApiProductStrategyCompetitiveLandscapePreview,
  type ApiProductStrategyDecision,
  type ApiProductStrategyEvidenceStatus,
} from "@/lib/api";
import { AppIcon } from "@/components/ui/app-icon";
import { CompetitiveArtifactAcceptance } from "@/components/competitive-intelligence/competitive-artifact-acceptance";
import { CompetitiveDecisionContextPackets } from "@/components/competitive-intelligence/competitive-decision-context-packets";

type Landscape = ApiProductStrategyCompetitiveLandscapePreview | ApiProductStrategyCompetitiveLandscape;

const evidenceLabels: Record<ApiProductStrategyEvidenceStatus, string> = {
  vendor_claim_unverified: "厂商声明，未独立验证",
  independently_verified: "已独立验证",
  stale: "已过期",
  unknown: "未知",
  blocked: "受阻",
};

const evidenceClasses: Record<ApiProductStrategyEvidenceStatus, string> = {
  vendor_claim_unverified: "af-chip af-chip-warning",
  independently_verified: "af-chip af-chip-success",
  stale: "af-chip af-chip-warning",
  unknown: "af-chip bg-slate-100 text-slate-600",
  blocked: "af-chip bg-rose-100 text-rose-700",
};

const decisionLabels: Record<ApiProductStrategyDecision, string> = {
  build: "构建",
  integrate: "整合",
  defer: "暂缓",
  explicitly_not_copy: "明确不复制",
};

const decisionClasses: Record<ApiProductStrategyDecision, string> = {
  build: "af-chip af-chip-success",
  integrate: "af-chip bg-sky-100 text-sky-700",
  defer: "af-chip af-chip-warning",
  explicitly_not_copy: "af-chip bg-slate-100 text-slate-600",
};

function isPersisted(snapshot: Landscape | null): snapshot is ApiProductStrategyCompetitiveLandscape {
  return Boolean(snapshot && "initialized" in snapshot && snapshot.initialized);
}

export function CompetitiveIntelligenceWorkspace() {
  const [snapshot, setSnapshot] = useState<Landscape | null>(null);
  const [loading, setLoading] = useState(true);
  const [seeding, setSeeding] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const [preview, persisted] = await Promise.all([
          getCompetitiveLandscapePreview(),
          getCompetitiveLandscape().catch(() => null),
        ]);
        if (!active) return;
        setSnapshot(persisted?.initialized ? persisted : preview);
      } catch {
        if (active) setError("无法读取竞品能力证据台账。请确认本地后端已加载 2.10.0 路由。");
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, []);

  const sourceSummary = useMemo(() => {
    if (!snapshot) return { vendorClaim: 0, verified: 0, other: 0 };
    return snapshot.products.reduce(
      (summary, product) => {
        if (product.evidence.recorded_status === "vendor_claim_unverified") summary.vendorClaim += 1;
        else if (product.evidence.status === "independently_verified") summary.verified += 1;
        else summary.other += 1;
        return summary;
      },
      { vendorClaim: 0, verified: 0, other: 0 },
    );
  }, [snapshot]);

  const initialize = async () => {
    if (!window.confirm("将当前官方来源快照和拟议路线图写入本地台账。不会覆盖已有人工编辑记录，是否继续？")) {
      return;
    }
    setSeeding(true);
    setError("");
    try {
      setSnapshot(await seedCompetitiveLandscape());
    } catch {
      setError("初始化本地竞品台账失败；未将任何来源声明为已验收。请检查后端日志后重试。");
    } finally {
      setSeeding(false);
    }
  };

  const persisted = isPersisted(snapshot);

  return (
    <div className="space-y-5" data-testid="competitive-intelligence-workspace">
      <section className="rounded-[28px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] p-5 shadow-[var(--af-shadow-soft)]">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <p className="af-kicker">2.10.0 Development</p>
            <h2 className="mt-2 text-2xl font-semibold text-[var(--af-text-primary)]">竞品能力证据台账</h2>
            <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
              把官方产品声明、Anti-FOMO 的本地工程状态与发布门禁分开呈现；它用于审查后续路线，不会自动升级策略或发布状态。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <span className="af-chip bg-slate-100 text-slate-700">官方来源快照</span>
            <span className={persisted ? "af-chip af-chip-success" : "af-chip af-chip-warning"}>
              {persisted ? "已初始化本地台账" : "只读预览"}
            </span>
            {!persisted ? (
              <button type="button" className="af-btn af-btn-primary px-3 py-2 text-xs" onClick={() => void initialize()} disabled={seeding}>
                {seeding ? "初始化中..." : "初始化台账"}
              </button>
            ) : null}
          </div>
        </div>

        {loading ? <p className="mt-5 text-sm text-[var(--af-text-tertiary)]">正在读取竞品来源与拟议路线图...</p> : null}
        {error ? <p className="mt-5 rounded-[16px] bg-rose-50 px-3 py-2 text-sm leading-6 text-rose-700">{error}</p> : null}

        {snapshot ? (
          <>
            <div className="mt-5 grid grid-cols-2 gap-3 md:grid-cols-4">
              <Metric label="竞品范围" value={`${snapshot.products.length} 个`} />
              <Metric label="厂商声明记录" value={`${sourceSummary.vendorClaim} 条`} />
              <Metric label="拟议路线" value={`${snapshot.roadmap_cards.length} 项`} />
              <Metric label="快照版本" value={snapshot.catalog_version} mono />
            </div>

            <div className="mt-4 rounded-[20px] border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-900">
              <p className="font-semibold">证据边界</p>
              <p className="mt-1">
                厂商公开声明不等于独立验证。来源过期会标为已过期，不可读或缺失时会标为未知；路线图卡不能自动批准，也不会改变既有 `baseline_hybrid` 或 release-readiness 的 `blocked` 状态。
              </p>
            </div>
          </>
        ) : null}
      </section>

      {snapshot ? (
        <>
          <section className="rounded-[28px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] p-5 shadow-[var(--af-shadow-soft)]">
            <div className="flex flex-wrap items-baseline justify-between gap-3">
              <div>
                <p className="af-kicker">Source Matrix</p>
                <h3 className="mt-2 text-lg font-semibold text-[var(--af-text-primary)]">官方能力观察</h3>
              </div>
              <p className="text-xs text-[var(--af-text-tertiary)]">观察于 {formatDate(snapshot.observed_at)} · 到期 {formatDate(snapshot.expires_at)}</p>
            </div>
            <div className="mt-4 grid gap-3 lg:grid-cols-2">
              {snapshot.products.map((product) => (
                <article key={product.catalog_key} className="min-w-0 rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-xs font-medium text-[var(--af-text-tertiary)]">{product.vendor}</p>
                      <h4 className="mt-1 text-base font-semibold text-[var(--af-text-primary)]">{product.product_name}</h4>
                      <p className="mt-1 text-[11px] text-[var(--af-text-tertiary)]">{product.source_title}</p>
                    </div>
                    <span className={evidenceClasses[product.evidence.status]}>{evidenceLabels[product.evidence.status]}</span>
                  </div>
                  <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">{product.vendor_claim}</p>
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {product.claimed_capabilities.map((capability) => (
                      <span key={capability} className="rounded-full bg-[var(--af-surface-muted)] px-2 py-1 text-[11px] text-[var(--af-text-secondary)]">
                        {capability}
                      </span>
                    ))}
                  </div>
                  <div className="mt-4 grid gap-2 text-xs leading-5 text-[var(--af-text-secondary)] sm:grid-cols-2">
                    <p className="rounded-[14px] bg-[var(--af-surface-muted)] px-3 py-2">
                      <span className="font-semibold text-[var(--af-text-primary)]">本地工程：</span>{product.local_implementation.notes}
                    </p>
                    <p className="rounded-[14px] bg-[var(--af-surface-muted)] px-3 py-2">
                      <span className="font-semibold text-[var(--af-text-primary)]">发布状态：</span>{product.local_release.notes}
                    </p>
                  </div>
                  <div className="mt-4 flex flex-wrap items-center justify-between gap-2 text-[11px] text-[var(--af-text-tertiary)]">
                    <a href={product.source_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 font-medium text-[var(--af-info)] hover:underline">
                      查看官方来源 <AppIcon name="external" className="h-3.5 w-3.5" />
                    </a>
                    <code title={product.source_digest}>{shortDigest(product.source_digest)}</code>
                  </div>
                </article>
              ))}
            </div>
          </section>

          <section className="rounded-[28px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] p-5 shadow-[var(--af-shadow-soft)]">
            <div>
              <p className="af-kicker">Decision Backlog</p>
              <h3 className="mt-2 text-lg font-semibold text-[var(--af-text-primary)]">拟议后续版本</h3>
              <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">每张卡都保留决策依据、来源快照、模块目标与验收条件；缺少人工审批时仅能保持拟议状态。</p>
            </div>
            <div className="mt-4 space-y-3">
              {snapshot.roadmap_cards.map((card) => (
                <article key={card.card_key} className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-xs text-[var(--af-text-tertiary)]">{card.card_key}</p>
                      <h4 className="mt-1 text-base font-semibold text-[var(--af-text-primary)]">{card.title}</h4>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <span className={decisionClasses[card.decision]}>{decisionLabels[card.decision]}</span>
                      <span className="af-chip bg-slate-100 text-slate-700">{card.approval_status}</span>
                    </div>
                  </div>
                  <div className="mt-3 grid gap-2 text-xs leading-5 text-[var(--af-text-secondary)] lg:grid-cols-3">
                    <Info label="决策依据" value={card.rationale} />
                    <Info label="来源状态" value={evidenceLabels[card.evidence.status]} />
                    <Info label="发布影响" value={card.release_impact} />
                  </div>
                  <div className="mt-3 grid gap-3 lg:grid-cols-2">
                    <Checklist title="验收条件" items={card.acceptance_criteria} />
                    <Checklist title="模块目标" items={card.module_targets} />
                  </div>
                </article>
              ))}
            </div>
          </section>
        </>
      ) : null}

      <CompetitiveDecisionContextPackets />
      <CompetitiveArtifactAcceptance />
    </div>
  );
}

function Metric({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0 rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
      <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">{label}</p>
      <p className={`mt-1 break-words text-sm font-semibold text-[var(--af-text-primary)]${mono ? " font-mono text-[11px]" : ""}`}>{value}</p>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <p className="rounded-[14px] bg-[var(--af-surface-muted)] px-3 py-2">
      <span className="font-semibold text-[var(--af-text-primary)]">{label}：</span>{value}
    </p>
  );
}

function Checklist({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-[16px] bg-[var(--af-surface-muted)] px-3 py-3">
      <p className="text-xs font-semibold text-[var(--af-text-primary)]">{title}</p>
      <ul className="mt-2 space-y-1 text-xs leading-5 text-[var(--af-text-secondary)]">
        {items.map((item) => <li key={item}>• {item}</li>)}
      </ul>
    </div>
  );
}

function shortDigest(value: string): string {
  return value.length > 16 ? `${value.slice(0, 12)}…${value.slice(-4)}` : value;
}

function formatDate(value: string | null): string {
  if (!value) return "尚未持久化";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString("zh-CN");
}
