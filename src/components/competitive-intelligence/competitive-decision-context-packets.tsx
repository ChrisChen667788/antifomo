"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getDecisionContextPackets,
  getDecisionContextPacketsPreview,
  initializeDecisionContextPackets,
} from "@/lib/api/competitive-intelligence";
import type {
  ApiProductStrategyDecision,
  ApiProductStrategyDecisionContextPackets,
  ApiProductStrategyDecisionContextPacketsInitialization,
  ApiProductStrategyDecisionContextPacket,
} from "@/lib/api/type-contracts/competitive-intelligence";

type DecisionContextSnapshot = ApiProductStrategyDecisionContextPackets | ApiProductStrategyDecisionContextPacketsInitialization;

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

function shortDigest(value: string | null | undefined): string {
  if (!value) return "尚未持久化";
  return value.length > 20 ? `${value.slice(0, 12)}…${value.slice(-6)}` : value;
}

function formatDate(value: string | null): string {
  if (!value) return "未设置";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString("zh-CN");
}

function packetGateSummary(packet: ApiProductStrategyDecisionContextPacket): string {
  return [
    packet.can_auto_execute ? "可自动执行" : "不可自动执行",
    packet.can_auto_approve_release ? "可自动批准发布" : "不可自动批准发布",
    packet.requires_human_change_approval ? "变更需人工审批" : "变更审批未声明",
  ].join(" · ");
}

export function CompetitiveDecisionContextPackets() {
  const [snapshot, setSnapshot] = useState<DecisionContextSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [initializing, setInitializing] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [preview, persisted] = await Promise.all([
        getDecisionContextPacketsPreview(),
        getDecisionContextPackets().catch(() => null),
      ]);
      setSnapshot(persisted?.initialized ? persisted : preview);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "无法读取 2.10.1 可复核决策上下文包。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const governance = snapshot?.governance;
  const includedCount = snapshot?.packets.length ?? 0;
  const excludedCount = snapshot?.excluded_cards.length ?? 0;
  const decisionCounts = useMemo(() => {
    const counts: Partial<Record<ApiProductStrategyDecision, number>> = {};
    snapshot?.packets.forEach((packet) => {
      counts[packet.decision] = (counts[packet.decision] ?? 0) + 1;
    });
    return counts;
  }, [snapshot]);

  async function initialize() {
    const confirmed = window.confirm(
      "仅把已获用户指令支持的 build / integrate / defer 路线写为可复核决策上下文包。不会执行功能变更、不会批准发布，也不会覆盖已有人工记录。是否继续？",
    );
    if (!confirmed) return;

    setInitializing(true);
    setError("");
    try {
      setSnapshot(await initializeDecisionContextPackets());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "初始化决策上下文包失败；没有产生发布或执行授权。");
    } finally {
      setInitializing(false);
    }
  }

  return (
    <section
      className="rounded-[28px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] p-5 shadow-[var(--af-shadow-soft)]"
      data-testid="competitive-decision-context-packets"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-3xl">
          <p className="af-kicker">2.10.1 Context Packets</p>
          <h3 className="mt-2 text-xl font-semibold text-[var(--af-text-primary)]">可复核决策上下文包</h3>
          <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
            将已获用户指令支持的产品路线保留为可审查上下文：它说明为什么纳入、依据何在、适用边界和保留策略；不等同于执行授权或发布批准。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={snapshot?.initialized ? "af-chip af-chip-success" : "af-chip af-chip-warning"}>
            {snapshot?.initialized ? "已初始化本地上下文包" : "只读预览"}
          </span>
          {!snapshot?.initialized ? (
            <button
              type="button"
              className="af-btn af-btn-primary px-3 py-2 text-xs"
              onClick={() => void initialize()}
              disabled={initializing || loading}
            >
              {initializing ? "初始化中..." : "显式确认并初始化"}
            </button>
          ) : null}
        </div>
      </div>

      {loading ? <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">正在读取决策上下文包...</p> : null}
      {error ? <p className="mt-4 rounded-[16px] bg-rose-50 px-3 py-2 text-sm leading-6 text-rose-700">{error}</p> : null}

      {snapshot && governance ? (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Metric label="纳入上下文包" value={`${includedCount} 项`} />
            <Metric label="明确排除" value={`${excludedCount} 项`} />
            <Metric label="持久化摘要" value={shortDigest(snapshot.persistent_snapshot_digest)} mono />
            <Metric
              label="变更门禁"
              value={governance.requires_human_change_approval ? "需人工批准" : "未声明"}
            />
          </div>

          <div className="mt-4 rounded-[20px] border border-amber-200 bg-amber-50 px-4 py-3 text-xs leading-5 text-amber-900">
            <p className="font-semibold">硬边界：上下文不是执行令</p>
            <p className="mt-1">
              {governance.note} 当前策略：{governance.can_auto_execute ? "可自动执行" : "不可自动执行"}；
              {governance.can_auto_approve_release ? "可自动批准发布" : "不可自动批准发布"}；
              {governance.requires_human_change_approval ? "每次实际变更仍需人工审批。" : "人工变更审批状态未声明。"}
            </p>
          </div>

          {hasInitialization(snapshot) ? (
            <p className="mt-3 rounded-[16px] bg-[var(--af-surface-muted)] px-3 py-2 text-xs leading-5 text-[var(--af-text-secondary)]">
              初始化记录：新建 {snapshot.initialization.packets.created} 个上下文包，已存在 seed 管理包 {snapshot.initialization.packets.existing_seed_managed ?? 0} 个，保留人工包 {snapshot.initialization.packets.preserved_human ?? 0} 个；新增 revision {snapshot.initialization.revisions.created} 条，审批审计新增 {snapshot.initialization.approval_audit.created} 条。
            </p>
          ) : null}

          {snapshot.initialization_audit ? (
            <p className="mt-3 rounded-[16px] bg-[var(--af-surface-muted)] px-3 py-2 text-xs leading-5 text-[var(--af-text-secondary)]">
              初始化审计：{snapshot.initialization_audit.event_type} · 允许 {snapshot.initialization_audit.allowed_decisions.join(" / ")} · 事件摘要 {shortDigest(snapshot.initialization_audit.event_digest)}。
            </p>
          ) : null}

          <div className="mt-5 flex flex-wrap gap-2 text-xs text-[var(--af-text-secondary)]">
            {(Object.entries(decisionCounts) as Array<[ApiProductStrategyDecision, number]>).map(([decision, count]) => (
              <span key={decision} className={decisionClasses[decision]}>{decisionLabels[decision]} {count} 项</span>
            ))}
          </div>
        </>
      ) : null}

      {snapshot?.packets.length ? (
        <div className="mt-5 space-y-3">
          {snapshot.packets.map((packet) => (
            <article key={packet.packet_key} className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="font-mono text-[11px] text-[var(--af-text-tertiary)]">{packet.packet_key}</p>
                  <h4 className="mt-1 text-base font-semibold text-[var(--af-text-primary)]">{packet.title}</h4>
                  <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">关联路线卡：{packet.roadmap_card_key} · 状态：{packet.status}</p>
                </div>
                <span className={decisionClasses[packet.decision]}>{decisionLabels[packet.decision]}</span>
              </div>

              <div className="mt-3 grid gap-2 text-xs leading-5 text-[var(--af-text-secondary)] lg:grid-cols-3">
                <Info label="问题与决策依据" value={`${packet.problem_statement} ${packet.rationale}`} />
                <Info label="执行/发布/变更" value={packetGateSummary(packet)} />
                <Info label="修订与摘要" value={`r${packet.revision} · ${shortDigest(packet.revision_digest)} · 不可变 revision ${packet.revisions.length} 条`} mono />
              </div>

              <div className="mt-3 grid gap-3 xl:grid-cols-2">
                <ListBlock title="来源绑定" items={[
                  `来源卡：${packet.source_catalog_keys.join("、") || "未记录"}`,
                  `来源摘要：${packet.source_digests.map(shortDigest).join("、") || "未记录"}`,
                  `包目录摘要：${shortDigest(packet.packet_catalog_digest)}`,
                  ...packet.source_references.map((source) => `${source.catalog_key} · ${source.evidence.status} · 观察 ${formatDate(source.observed_at)} · 到期 ${formatDate(source.expires_at)}`),
                ]} />
                <ListBlock title="假设与约束" items={[
                  ...packet.assumptions.map((item) => `假设：${item}`),
                  ...packet.constraints.map((item) => `约束：${item}`),
                  `模块目标：${packet.module_targets.join("、") || "未记录"}`,
                ]} />
                <ListBlock title="审批证据" items={[
                  `证据类型：${packet.approval_evidence.kind} · ${packet.approval_evidence.approval_kind}`,
                  `内容：${packet.approval_evidence.instruction}`,
                  packet.approval_evidence.owner.display_name
                    ? `具名记录：${packet.approval_evidence.owner.display_name}`
                    : "未伪造具名审批人；仅记录用户指令作为上下文依据。",
                  `记录时间：${formatDate(packet.approval_evidence.recorded_at)}`,
                  `授权范围：${packet.approval_evidence.authorization_scope}`,
                ]} />
                <ListBlock title="保留与失效" items={[
                  `保留至：${formatDate(packet.retention_until)}`,
                  `生产状态：${packet.production_status}`,
                  `发布影响：${packet.release_impact}`,
                  `来源目录版本：${packet.source_catalog_version}`,
                ]} />
              </div>
            </article>
          ))}
        </div>
      ) : null}

      {snapshot?.excluded_cards.length ? (
        <div className="mt-5 rounded-[22px] border border-slate-200 bg-slate-50 p-4">
          <p className="text-sm font-semibold text-slate-900">明确不复制：保留为排除记录，不写入可执行路线</p>
          <p className="mt-1 text-xs leading-5 text-slate-600">这些卡片不会被初始化为决策上下文包，也不构成任何功能实现、发布或外部操作的授权。</p>
          <div className="mt-3 grid gap-3 lg:grid-cols-2">
            {snapshot.excluded_cards.map((card) => (
              <article key={card.card_key} className="rounded-[18px] border border-slate-200 bg-white p-3">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-mono text-[10px] text-slate-500">{card.card_key}</p>
                    <p className="mt-1 text-sm font-semibold text-slate-900">{card.title}</p>
                    <p className="mt-1 text-[11px] text-slate-500">产品域：{card.product_key}</p>
                  </div>
                  <span className={decisionClasses.explicitly_not_copy}>{decisionLabels.explicitly_not_copy}</span>
                </div>
                <p className="mt-2 text-xs leading-5 text-slate-700">{card.exclusion_reason || card.rationale}</p>
                <p className="mt-2 text-[11px] text-slate-500">不可自动执行 · 不可自动批准发布</p>
              </article>
            ))}
          </div>
        </div>
      ) : null}
    </section>
  );
}

function hasInitialization(snapshot: DecisionContextSnapshot): snapshot is ApiProductStrategyDecisionContextPacketsInitialization {
  return "initialization" in snapshot;
}

function Metric({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0 rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
      <p className="text-[11px] font-medium uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">{label}</p>
      <p className={`mt-1 break-words text-sm font-semibold text-[var(--af-text-primary)]${mono ? " font-mono text-[11px]" : ""}`}>{value}</p>
    </div>
  );
}

function Info({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <p className={`rounded-[14px] bg-[var(--af-surface-muted)] px-3 py-2${mono ? " font-mono text-[11px]" : ""}`}>
      <span className="font-semibold text-[var(--af-text-primary)]">{label}：</span>{value}
    </p>
  );
}

function ListBlock({ title, items }: { title: string; items: string[] }) {
  return (
    <div className="rounded-[16px] bg-[var(--af-surface-muted)] px-3 py-3">
      <p className="text-xs font-semibold text-[var(--af-text-primary)]">{title}</p>
      <ul className="mt-2 space-y-1 text-xs leading-5 text-[var(--af-text-secondary)]">
        {items.filter(Boolean).map((item, index) => <li key={`${title}-${index}-${item}`}>• {item}</li>)}
      </ul>
    </div>
  );
}
