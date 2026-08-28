"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  getArtifactAcceptance,
  getArtifactAcceptancePreview,
  initializeArtifactAcceptance,
} from "@/lib/api/competitive-intelligence";
import type {
  ApiProductStrategyArtifactAcceptance,
  ApiProductStrategyArtifactAcceptanceArtifact,
  ApiProductStrategyArtifactAcceptanceInitialization,
  ApiProductStrategyArtifactAcceptanceRevision,
  ApiProductStrategyDecisionContextDecision,
} from "@/lib/api/type-contracts/competitive-intelligence";

type ArtifactAcceptanceSnapshot = ApiProductStrategyArtifactAcceptance | ApiProductStrategyArtifactAcceptanceInitialization;

const decisionLabels: Record<ApiProductStrategyDecisionContextDecision, string> = {
  build: "构建",
  integrate: "整合",
  defer: "暂缓",
};

const decisionClasses: Record<ApiProductStrategyDecisionContextDecision, string> = {
  build: "af-chip af-chip-success",
  integrate: "af-chip bg-sky-100 text-sky-700",
  defer: "af-chip af-chip-warning",
};

function shortDigest(value: string | null | undefined): string {
  if (!value) return "未记录";
  return value.length > 20 ? `${value.slice(0, 12)}…${value.slice(-6)}` : value;
}

function formatDate(value: string | null | undefined): string {
  if (!value) return "未记录";
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? value : parsed.toLocaleDateString("zh-CN");
}

function hasInitialization(snapshot: ArtifactAcceptanceSnapshot): snapshot is ApiProductStrategyArtifactAcceptanceInitialization {
  return "initialization" in snapshot;
}

function blockedChecklistCount(artifact: ApiProductStrategyArtifactAcceptanceArtifact): number {
  return artifact.acceptance_checklist.filter((item) => item.result === "hold" && item.blocks_acceptance).length;
}

function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "∅";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  try {
    return JSON.stringify(value);
  } catch {
    return "[不可序列化值]";
  }
}

export function CompetitiveArtifactAcceptance() {
  const [snapshot, setSnapshot] = useState<ArtifactAcceptanceSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [initializing, setInitializing] = useState(false);
  const [error, setError] = useState("");

  const refresh = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [preview, persisted] = await Promise.all([
        getArtifactAcceptancePreview(),
        getArtifactAcceptance().catch(() => null),
      ]);
      setSnapshot(persisted?.initialized ? persisted : preview);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "无法读取 2.10.2 工件验收与修订差异台账。");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  const summary = useMemo(() => {
    const artifacts = snapshot?.artifacts ?? [];
    return {
      artifacts: artifacts.length,
      blockedChecks: artifacts.reduce((count, artifact) => count + blockedChecklistCount(artifact), 0),
      revisions: artifacts.reduce((count, artifact) => count + artifact.revisions.length, 0),
    };
  }, [snapshot]);

  async function initialize() {
    const confirmed = window.confirm(
      "仅初始化可复核的工件验收与修订差异台账。Office/视觉证据缺失时仍保持 HOLD / blocked；此操作不会接受工件、批准发布或执行任何变更。是否继续？",
    );
    if (!confirmed) return;

    setInitializing(true);
    setError("");
    try {
      setSnapshot(await initializeArtifactAcceptance());
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "初始化工件验收台账失败；未产生任何验收、发布或执行授权。");
    } finally {
      setInitializing(false);
    }
  }

  return (
    <section
      className="rounded-[28px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] p-5 shadow-[var(--af-shadow-soft)]"
      data-testid="competitive-artifact-acceptance"
    >
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div className="max-w-3xl">
          <p className="af-kicker">2.10.2 Artifact Acceptance</p>
          <h3 className="mt-2 text-xl font-semibold text-[var(--af-text-primary)]">可复核工件验收与修订差异</h3>
          <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
            将可编辑交付物绑定到 2.10.1 决策上下文、来源包和字段级修订差异。它只呈现验收前证据与阻断原因，不把本地初始化表述为工件验收、发布或执行许可。
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="af-chip bg-rose-100 text-rose-700">HOLD · blocked</span>
          <span className={snapshot?.initialized ? "af-chip af-chip-success" : "af-chip af-chip-warning"}>
            {snapshot?.initialized ? "已初始化审查台账" : "只读预览"}
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

      {loading ? <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">正在读取工件证据与修订差异...</p> : null}
      {error ? <p className="mt-4 rounded-[16px] bg-rose-50 px-3 py-2 text-sm leading-6 text-rose-700">{error}</p> : null}

      {snapshot ? (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Metric label="审查工件" value={`${summary.artifacts} 项`} />
            <Metric label="阻断检查" value={`${summary.blockedChecks} 项`} />
            <Metric label="修订记录" value={`${summary.revisions} 条`} />
            <Metric label="目录摘要" value={shortDigest(snapshot.catalog_digest)} mono />
          </div>

          <div className="mt-4 rounded-[20px] border border-rose-200 bg-rose-50 px-4 py-3 text-xs leading-5 text-rose-900">
            <p className="font-semibold">硬门禁：Office / 视觉证据缺失即保持 HOLD</p>
            <p className="mt-1">
              {snapshot.governance.note} 缺少独立 Office roundtrip 或视觉确认的检查必须显示为 `missing` 与 `hold`，并维持 `blocked`；初始化不会自动补齐证据、接受工件、批准发布或触发执行。
            </p>
          </div>

          {hasInitialization(snapshot) ? (
            <p className="mt-3 rounded-[16px] bg-[var(--af-surface-muted)] px-3 py-2 text-xs leading-5 text-[var(--af-text-secondary)]">
              初始化记录：新建 {snapshot.initialization.drafts.created} 个工件台账，已存在 seed 管理项 {snapshot.initialization.drafts.existing_seed_managed ?? 0} 个，保留人工项 {snapshot.initialization.drafts.preserved_human ?? 0} 个；新增 revision {snapshot.initialization.revisions.created} 条，初始化审计新增 {snapshot.initialization.initialization_audit.created} 条。
            </p>
          ) : null}

          {snapshot.initialization_audit ? (
            <p className="mt-3 rounded-[16px] bg-[var(--af-surface-muted)] px-3 py-2 text-xs leading-5 text-[var(--af-text-secondary)]">
              初始化审计：{snapshot.initialization_audit.event_type} · 绑定 {snapshot.initialization_audit.required_context_packet_keys.length} 个上下文包 · 事件摘要 {shortDigest(snapshot.initialization_audit.event_digest)}。
            </p>
          ) : null}

          {snapshot.context_packet_readiness ? (
            <p className="mt-3 rounded-[16px] bg-[var(--af-surface-muted)] px-3 py-2 text-xs leading-5 text-[var(--af-text-secondary)]">
              2.10.1 前置：{snapshot.context_packet_readiness.ready_for_explicit_initialization ? "已具备显式初始化条件" : "尚未具备初始化条件"}；缺失 {snapshot.context_packet_readiness.missing_context_packet_keys.length} 项，不可用 {snapshot.context_packet_readiness.unusable_context_packet_keys.length} 项。
            </p>
          ) : null}
        </>
      ) : null}

      {snapshot?.artifacts.length ? (
        <div className="mt-5 space-y-3">
          {snapshot.artifacts.map((artifact) => (
            <ArtifactCard key={artifact.artifact_key} artifact={artifact} />
          ))}
        </div>
      ) : null}
    </section>
  );
}

function ArtifactCard({ artifact }: { artifact: ApiProductStrategyArtifactAcceptanceArtifact }) {
  return (
    <article className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="font-mono text-[11px] text-[var(--af-text-tertiary)]">{artifact.artifact_key}</p>
          <h4 className="mt-1 text-base font-semibold text-[var(--af-text-primary)]">{artifact.title}</h4>
          <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">
            关联上下文包：{artifact.decision_context_packet_key} · 当前 revision r{artifact.revision}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className={decisionClasses[artifact.decision]}>{decisionLabels[artifact.decision]}</span>
          <span className="af-chip bg-rose-100 text-rose-700">{artifact.acceptance_status} · {artifact.blocking_status}</span>
        </div>
      </div>

      <div className="mt-3 grid gap-2 text-xs leading-5 text-[var(--af-text-secondary)] lg:grid-cols-3">
        <Info label="来源包摘要" value={shortDigest(artifact.evidence_source_bundle_digest)} mono />
        <Info label="当前 revision" value={`r${artifact.revision} · ${shortDigest(artifact.revision_digest)}`} mono />
        <Info label="验收状态" value={`HOLD · ${blockedChecklistCount(artifact)} 项缺失阻断证据`} />
      </div>

      <div className="mt-3 grid gap-3 xl:grid-cols-2">
        <ListBlock
          title="来源包绑定"
          items={sourceBundleItems(artifact)}
        />
        <ChecklistBlock items={artifact.acceptance_checklist} />
      </div>

      <div className="mt-3 rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
        <div className="flex flex-wrap items-baseline justify-between gap-2">
          <div>
            <p className="text-xs font-semibold text-[var(--af-text-primary)]">来源与字段级修订差异</p>
            <p className="mt-1 text-[11px] leading-5 text-[var(--af-text-secondary)]">所有 diff 仅供人工复核；`auto_acceptance_forbidden=true`，不会把变更升级为接受。</p>
          </div>
          <span className="af-chip bg-rose-100 text-rose-700">禁止自动接受</span>
        </div>
        <div className="mt-3 space-y-2">
          {artifact.revisions.map((revision) => <RevisionDiff key={`${revision.artifact_key}-${revision.revision}-${revision.revision_digest}`} revision={revision} />)}
          {!artifact.revisions.length && artifact.initial_field_level_diff ? (
            <InitialRevisionDiff diff={artifact.initial_field_level_diff} />
          ) : null}
        </div>
      </div>
    </article>
  );
}

function ChecklistBlock({ items }: { items: ApiProductStrategyArtifactAcceptanceArtifact["acceptance_checklist"] }) {
  return (
    <div className="rounded-[16px] bg-[var(--af-surface-muted)] px-3 py-3">
      <p className="text-xs font-semibold text-[var(--af-text-primary)]">验收前检查</p>
      <ul className="mt-2 space-y-2 text-xs leading-5 text-[var(--af-text-secondary)]">
        {items.map((item) => (
          <li key={item.check_key} className="rounded-[12px] border border-rose-100 bg-rose-50 px-2.5 py-2 text-rose-900">
            <p className="font-medium">{item.title} · {item.evidence_status} / {item.result}</p>
            <p className="mt-0.5">{item.note}{item.blocks_acceptance ? " · 阻断验收" : ""}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function RevisionDiff({ revision }: { revision: ApiProductStrategyArtifactAcceptanceRevision }) {
  const diff = revision.field_level_diff;
  return (
    <div className="rounded-[14px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] px-3 py-2.5 text-xs leading-5 text-[var(--af-text-secondary)]">
      <p className="font-medium text-[var(--af-text-primary)]">
        r{revision.revision} · {shortDigest(revision.revision_digest)} · {formatDate(revision.created_at)}
      </p>
      <p className="mt-0.5">差异：r{diff.from_revision ?? "初始"} → r{diff.to_revision} · {diff.auto_acceptance_forbidden ? "禁止自动接受" : "仍须人工核验"}</p>
      {diff.changed_fields.length ? (
        <ul className="mt-1.5 space-y-1">
          {diff.changed_fields.map((change) => (
            <li key={`${revision.revision}-${change.field}-${change.change_type}`}>
              <span className="font-medium text-[var(--af-text-primary)]">{change.field}</span> · {change.change_type}：{displayValue(change.before)} → {displayValue(change.after)}
            </li>
          ))}
        </ul>
      ) : <p className="mt-1.5">无字段变更；仍不构成自动接受。</p>}
    </div>
  );
}

function sourceBundleItems(artifact: ApiProductStrategyArtifactAcceptanceArtifact): string[] {
  const bundle = artifact.evidence_source_bundle;
  const packet = bundle.decision_context_packet;
  return [
    `上下文包：${packet.packet_key} · r${packet.revision} / ${shortDigest(packet.revision_digest)}`,
    `路线卡：${packet.roadmap_card_key} · ${packet.decision}`,
    `来源目录版本：${packet.source_catalog_version}`,
    `来源键：${packet.source_catalog_keys.join("、") || "未记录"}`,
    `来源摘要：${packet.source_digests.map(shortDigest).join("、") || "未记录"}`,
    ...packet.source_references.map((source) => `${source.catalog_key} · ${source.evidence.status} · ${shortDigest(source.source_digest)}`),
    bundle.evidence_collection.note,
  ];
}

function InitialRevisionDiff({ diff }: { diff: ApiProductStrategyArtifactAcceptanceArtifact["initial_field_level_diff"] }) {
  if (!diff) return null;
  return (
    <div className="rounded-[14px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] px-3 py-2.5 text-xs leading-5 text-[var(--af-text-secondary)]">
      <p className="font-medium text-[var(--af-text-primary)]">预览初始修订 · r{diff.to_revision}</p>
      <p className="mt-0.5">差异：r{diff.from_revision ?? "初始"} → r{diff.to_revision} · 禁止自动接受</p>
      <p className="mt-1.5">{diff.changed_fields.length} 个字段已进入人工复核范围；尚未形成已验收交付物。</p>
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
        {items.map((item, index) => <li key={`${title}-${index}-${item}`}>• {item}</li>)}
      </ul>
    </div>
  );
}
