"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  exportResearchIndustryKnowledgeRetrievalApprovalTemplate,
  exportResearchIndustryKnowledgeRetrievalEvidenceTemplates,
  getResearchIndustryKnowledgeRetrievalAssurance,
  type ApiResearchIndustryKnowledgeRetrievalAssuranceSnapshot,
  type ApiResearchIndustryKnowledgeRetrievalAssuranceStatus,
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

export function ResearchIndustryKnowledgeRetrievalAssuranceSection({ t }: { t: TranslationFn }) {
  const [snapshot, setSnapshot] = useState<ApiResearchIndustryKnowledgeRetrievalAssuranceSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [exportingEvidence, setExportingEvidence] = useState(false);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setSnapshot(await getResearchIndustryKnowledgeRetrievalAssurance());
    } catch {
      setError(t("research.retrievalAssuranceLoadFailed", "读取本地知识检索保证状态失败。"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const exportApprovalTemplate = async () => {
    setExporting(true);
    setError("");
    setMessage("");
    try {
      const template = await exportResearchIndustryKnowledgeRetrievalApprovalTemplate();
      setMessage(
        template.candidate_strategy
          ? `已生成待人工审批模板：候选 ${template.candidate_strategy}。该操作不会切换生产默认策略。`
          : "已生成待人工审批模板；当前尚无满足上线条件的候选策略。",
      );
      await load();
    } catch {
      setError(t("research.retrievalAssuranceExportFailed", "生成候选审批模板失败。"));
    } finally {
      setExporting(false);
    }
  };

  const exportEvidenceTemplates = async () => {
    setExportingEvidence(true);
    setError("");
    setMessage("");
    try {
      const templates = await exportResearchIndustryKnowledgeRetrievalEvidenceTemplates();
      setMessage(
        templates.candidate_strategy
          ? "已生成 pending 的审批、影子和漂移模板；仍需由真实负责人填写并验证。"
          : "已生成 pending 证据模板；当前没有可上线候选，生产默认未改变。",
      );
      await load();
    } catch {
      setError(t("research.retrievalAssuranceEvidenceExportFailed", "生成影子与漂移证据模板失败。"));
    } finally {
      setExportingEvidence(false);
    }
  };

  const visibleRounds = useMemo(() => snapshot?.rounds.slice(0, 15) || [], [snapshot]);

  return (
    <section
      data-testid="research-industry-knowledge-retrieval-assurance-section"
      className="mt-5 rounded-[28px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] p-4 shadow-[var(--af-shadow-soft)]"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
            {t("research.retrievalAssuranceKicker", "Retrieval Assurance")}
          </p>
          <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
            {t(
              "research.retrievalAssuranceDesc",
              "将本地行业资料的检索评测、完整研报复核、真实复排、人工批准、影子运行与漂移检查收敛为 15 个可审计门。默认检索保持不变，直到所有证据完成。",
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {snapshot ? <span className={`shrink-0 px-2.5 py-1 text-xs font-semibold ${statusClass[snapshot.status]}`}>{statusLabel[snapshot.status]}</span> : null}
          <button type="button" onClick={() => void load()} disabled={loading || exporting || exportingEvidence} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
            {loading ? "读取中..." : "刷新状态"}
          </button>
          <button type="button" onClick={() => void exportApprovalTemplate()} disabled={exporting || exportingEvidence} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
            {exporting ? "生成中..." : "导出审批模板"}
          </button>
          <button type="button" onClick={() => void exportEvidenceTemplates()} disabled={exporting || exportingEvidence} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
            {exportingEvidence ? "生成中..." : "导出运行模板"}
          </button>
        </div>
      </div>

      {loading && !snapshot ? <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">正在读取检索保证状态...</p> : null}
      {error ? <p className="mt-4 text-sm text-[var(--af-warning)]">{error}</p> : null}
      {message ? <p className="mt-4 text-sm text-[var(--af-success)]">{message}</p> : null}

      {snapshot ? (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-5">
            <Metric label="保证评分" value={`${snapshot.score}/100`} />
            <Metric label="通过 / 关注 / 阻断" value={`${snapshot.pass_count} / ${snapshot.watch_count} / ${snapshot.blocked_count}`} />
            <Metric label="固定题集" value={`${snapshot.case_count} 题`} />
            <Metric label="生产默认" value={snapshot.current_default_strategy} />
            <Metric label="候选状态" value={snapshot.candidate_strategy || "尚无候选"} />
          </div>

          <div className="mt-4 rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-[var(--af-text-primary)]">受控上线状态</p>
              <span className="text-xs text-[var(--af-text-tertiary)]">{snapshot.program_version}</span>
            </div>
            <p className="mt-2 text-xs leading-5 text-[var(--af-text-secondary)]">
              当前评测判定：<span className="font-semibold text-[var(--af-text-primary)]">{snapshot.promotion_decision}</span>。生产默认固定为
              <span className="mx-1 font-mono text-[11px] text-[var(--af-text-primary)]">{snapshot.current_default_strategy}</span>
              ，审批模板只允许人工留存候选证据，不能自动上线。
            </p>
          </div>

          <details className="mt-4 rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
            <summary className="cursor-pointer list-none text-sm font-semibold text-[var(--af-text-primary)] [&::-webkit-details-marker]:hidden">
              查看全部 {visibleRounds.length} 轮检索保证
            </summary>
            <div className="mt-3 grid grid-cols-1 gap-2 lg:grid-cols-2">
              {visibleRounds.map((round) => (
                <article key={round.key} className="rounded-[20px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                  <div className="flex flex-wrap items-start justify-between gap-2">
                    <div className="min-w-0">
                      <p className="text-xs font-semibold text-[var(--af-text-primary)]">
                        {round.version} · {round.title}
                      </p>
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
                        {": "}
                        {metric.observed}
                        {" / "}
                        {metric.target}
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
                  <p key={action} className="rounded-[16px] bg-[var(--af-surface-muted)] px-3 py-2 text-xs leading-5 text-[var(--af-text-secondary)]">
                    {action}
                  </p>
                ))}
              </div>
            </div>
            <div className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-sm font-semibold text-[var(--af-text-primary)]">工件状态</p>
              <div className="mt-3 space-y-2">
                {snapshot.artifacts.map((artifact) => (
                  <p key={artifact.label} className="rounded-[16px] bg-[var(--af-surface-muted)] px-3 py-2 text-xs leading-5 text-[var(--af-text-secondary)]">
                    <span className="font-semibold text-[var(--af-text-primary)]">{artifact.label}</span>
                    {" · "}
                    {artifact.exists ? "已发现" : "未发现"}
                    {" · "}
                    {artifact.summary}
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

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-0 rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
      <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">{label}</p>
      <p className="mt-1 break-words text-sm font-semibold text-[var(--af-text-primary)]">{value}</p>
    </div>
  );
}
