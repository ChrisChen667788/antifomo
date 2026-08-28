"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  exportResearchIndustryKnowledgeRetrievalEvidenceOperationsTemplates,
  getResearchIndustryKnowledgeRetrievalEvidenceOperations,
  type ApiResearchIndustryKnowledgeRetrievalAssuranceStatus,
  type ApiResearchIndustryKnowledgeRetrievalEvidenceOperationsSnapshot,
} from "@/lib/api";

type TranslationFn = (key: string, fallback: string) => string;

const statusClass: Record<ApiResearchIndustryKnowledgeRetrievalAssuranceStatus, string> = {
  pass: "af-chip af-chip-success",
  watch: "af-chip af-chip-warning",
  blocked: "af-chip bg-rose-100 text-rose-700",
};

const statusLabel: Record<ApiResearchIndustryKnowledgeRetrievalAssuranceStatus, string> = {
  pass: "通过",
  watch: "关注",
  blocked: "阻断",
};

export function ResearchIndustryKnowledgeRetrievalEvidenceOperationsSection({ t }: { t: TranslationFn }) {
  const [snapshot, setSnapshot] = useState<ApiResearchIndustryKnowledgeRetrievalEvidenceOperationsSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setSnapshot(await getResearchIndustryKnowledgeRetrievalEvidenceOperations());
    } catch {
      setError(t("research.retrievalEvidenceOperationsLoadFailed", "读取检索证据运营状态失败。"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const exportTemplates = async () => {
    setExporting(true);
    setError("");
    setMessage("");
    try {
      const result = await exportResearchIndustryKnowledgeRetrievalEvidenceOperationsTemplates();
      setMessage(
        result.created_paths.length
          ? `已生成 ${result.created_paths.length} 个 pending 运营模板；它们不构成外部完成证据。`
          : "运营模板已存在，未覆盖任何人工工件。",
      );
      await load();
    } catch {
      setError(t("research.retrievalEvidenceOperationsExportFailed", "生成检索证据运营模板失败。"));
    } finally {
      setExporting(false);
    }
  };

  const visibleRounds = useMemo(() => snapshot?.rounds.slice(0, 15) || [], [snapshot]);

  return (
    <section
      data-testid="research-industry-knowledge-retrieval-evidence-operations-section"
      className="mt-5 rounded-[28px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] p-4 shadow-[var(--af-shadow-soft)]"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
            {t("research.retrievalEvidenceOperationsKicker", "Evidence Operations")}
          </p>
          <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
            {t(
              "research.retrievalEvidenceOperationsDesc",
              "将检索评测后的工件清单、摘要绑定、时效、职责分离、事件、回退和独立审计交接统一成可追踪运营门。生产默认始终保持受保护状态。",
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {snapshot ? <span className={`shrink-0 px-2.5 py-1 text-xs font-semibold ${statusClass[snapshot.status]}`}>{statusLabel[snapshot.status]}</span> : null}
          <button type="button" onClick={() => void load()} disabled={loading || exporting} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
            {loading ? "读取中..." : "刷新状态"}
          </button>
          <button type="button" onClick={() => void exportTemplates()} disabled={exporting} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
            {exporting ? "生成中..." : "导出运营模板"}
          </button>
        </div>
      </div>

      {loading && !snapshot ? <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">正在读取检索证据运营状态...</p> : null}
      {error ? <p className="mt-4 text-sm text-[var(--af-warning)]">{error}</p> : null}
      {message ? <p className="mt-4 text-sm text-[var(--af-success)]">{message}</p> : null}

      {snapshot ? (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-5">
            <Metric label="运营评分" value={`${snapshot.score}/100`} />
            <Metric label="通过 / 关注 / 阻断" value={`${snapshot.pass_count} / ${snapshot.watch_count} / ${snapshot.blocked_count}`} />
            <Metric label="固定题集" value={`${snapshot.case_count} 题`} />
            <Metric label="生产默认" value={snapshot.current_default_strategy} />
            <Metric label="证据链" value={snapshot.evidence_chain_digest.slice(0, 12) || "待生成"} mono />
          </div>

          <div className="mt-4 rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-[var(--af-text-primary)]">受控运营状态</p>
              <span className="text-xs text-[var(--af-text-tertiary)]">{snapshot.program_version}</span>
            </div>
            <p className="mt-2 text-xs leading-5 text-[var(--af-text-secondary)]">
              上游保证：<span className="font-semibold text-[var(--af-text-primary)]">{snapshot.parent_program_version || "未发现"}</span>
              <span className="mx-1">·</span>
              {statusLabel[snapshot.parent_status]}。运营门只汇总真实工件，不能代替人工复核、批准或独立审计。
            </p>
          </div>

          <details className="mt-4 rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
            <summary className="cursor-pointer list-none text-sm font-semibold text-[var(--af-text-primary)] [&::-webkit-details-marker]:hidden">
              查看全部 {visibleRounds.length} 轮证据运营
            </summary>
            <div className="mt-3 grid grid-cols-1 gap-2 lg:grid-cols-2">
              {visibleRounds.map((round) => (
                <article key={round.key} className="rounded-[20px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-[var(--af-text-primary)]">{round.version} · {round.title}</p>
                      <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">{round.summary}</p>
                    </div>
                    <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-semibold ${statusClass[round.status]}`}>
                      {statusLabel[round.status]}
                    </span>
                  </div>
                  <div className="mt-3 space-y-1.5 text-[11px] leading-4 text-[var(--af-text-secondary)]">
                    {round.metrics.slice(0, 2).map((metric) => (
                      <p key={metric.key} title={metric.note || metric.target}>
                        <span className="font-medium text-[var(--af-text-primary)]">{metric.label}</span>
                        {": "}{metric.observed}{" / "}{metric.target}
                      </p>
                    ))}
                  </div>
                </article>
              ))}
            </div>
          </details>

          <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-[1.15fr_0.85fr]">
            <div className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-sm font-semibold text-[var(--af-text-primary)]">下一步证据</p>
              <div className="mt-3 space-y-2">
                {snapshot.next_actions.slice(0, 5).map((action) => (
                  <p key={action} className="rounded-[16px] bg-[var(--af-surface-muted)] px-3 py-2 text-xs leading-5 text-[var(--af-text-secondary)]">{action}</p>
                ))}
              </div>
            </div>
            <div className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-sm font-semibold text-[var(--af-text-primary)]">工件状态</p>
              <div className="mt-3 space-y-2">
                {snapshot.artifacts.map((artifact) => (
                  <p key={artifact.label} className="rounded-[16px] bg-[var(--af-surface-muted)] px-3 py-2 text-xs leading-5 text-[var(--af-text-secondary)]">
                    <span className="font-semibold text-[var(--af-text-primary)]">{artifact.label}</span>
                    {" · "}{artifact.exists ? "已发现" : "未发现"}{" · "}{artifact.summary}
                  </p>
                ))}
              </div>
            </div>
          </div>

          {snapshot.warnings.length ? (
            <div className="mt-3 rounded-[18px] border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
              {snapshot.warnings.map((warning) => <p key={warning}>{warning}</p>)}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function Metric({ label, value, mono = false }: { label: string; value: string; mono?: boolean }) {
  return (
    <div className="min-w-0 rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
      <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">{label}</p>
      <p className={`mt-1 break-words text-sm font-semibold text-[var(--af-text-primary)]${mono ? " font-mono text-[11px]" : ""}`}>{value}</p>
    </div>
  );
}
