"use client";

import { useEffect, useMemo, useState } from "react";
import {
  getResearchUpgradeDiagnosticsPreview,
  type ApiResearchUpgradeDiagnostics,
  type ApiResearchUpgradeRoundStatus,
} from "@/lib/api";

type TranslationFn = (key: string, fallback: string) => string;

const statusLabel: Record<ApiResearchUpgradeRoundStatus, string> = {
  ready: "ready",
  watch: "watch",
  blocked: "blocked",
};

const statusClass: Record<ApiResearchUpgradeRoundStatus, string> = {
  ready: "af-chip af-chip-success",
  watch: "af-chip af-chip-warning",
  blocked: "af-chip bg-rose-100 text-rose-700",
};

const priorityClass: Record<string, string> = {
  high: "bg-rose-100 text-rose-700",
  medium: "af-chip af-chip-warning",
  low: "af-chip",
};

export function ResearchCenterUpgradeDiagnosticsSection({ t }: { t: TranslationFn }) {
  const [diagnostics, setDiagnostics] = useState<ApiResearchUpgradeDiagnostics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const result = await getResearchUpgradeDiagnosticsPreview();
        if (active) setDiagnostics(result);
      } catch {
        if (active) setError(t("research.upgradeDiagnosticsLoadFailed", "读取研究升级诊断失败。"));
      } finally {
        if (active) setLoading(false);
      }
    };
    void load();
    return () => {
      active = false;
    };
  }, [t]);

  const statusCounts = useMemo(() => {
    const counts: Record<ApiResearchUpgradeRoundStatus, number> = {
      ready: 0,
      watch: 0,
      blocked: 0,
    };
    diagnostics?.roadmap_rounds.forEach((round) => {
      counts[round.status] += 1;
    });
    return counts;
  }, [diagnostics]);

  const changedFields = useMemo(
    () => diagnostics?.field_diffs.filter((diff) => diff.status !== "unchanged") ?? [],
    [diagnostics],
  );

  return (
    <section className="mt-5 rounded-[28px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] p-4 shadow-[var(--af-shadow-soft)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
            {t("research.upgradeDiagnosticsKicker", "Research Upgrade")}
          </p>
          <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
            {t("research.upgradeDiagnosticsDesc", "URL-first、检索收敛、图谱专家和输出质量门禁。")}
          </p>
        </div>
        <div className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-1 text-xs font-semibold text-[var(--af-text-secondary)]">
          {diagnostics ? `${diagnostics.readiness_score}/100 · ${diagnostics.status}` : "..."}
        </div>
      </div>

      {loading ? (
        <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">
          {t("research.upgradeDiagnosticsLoading", "诊断中...")}
        </p>
      ) : null}
      {error ? <p className="mt-4 text-sm text-[var(--af-warning)]">{error}</p> : null}

      {diagnostics ? (
        <>
          <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-3">
            {diagnostics.summary_lines.map((line) => (
              <p
                key={line}
                className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-xs leading-5 text-[var(--af-text-secondary)]"
              >
                {line}
              </p>
            ))}
          </div>

          {diagnostics.url_first_diagnostics.warnings.length ? (
            <div className="mt-3 rounded-[20px] border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
              {diagnostics.url_first_diagnostics.warnings.map((warning) => (
                <p key={warning}>{warning}</p>
              ))}
            </div>
          ) : null}

          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-5">
            <Metric label="Ready" value={statusCounts.ready} />
            <Metric label="Watch" value={statusCounts.watch} />
            <Metric label="Blocked" value={statusCounts.blocked} />
            <Metric label="Accepted" value={diagnostics.retrieval_evaluation.accepted_count} />
            <Metric label="Graph" value={diagnostics.lightweight_graph.nodes.length} />
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <div className="flex flex-wrap gap-2">
                {diagnostics.roadmap_rounds.map((round) => (
                  <span
                    key={round.key}
                    className={`rounded-full px-2.5 py-1 text-[11px] font-medium ${statusClass[round.status]}`}
                    title={round.summary}
                  >
                    {round.index}. {round.title} · {statusLabel[round.status]}
                  </span>
                ))}
              </div>
              <div className="mt-4 grid grid-cols-1 gap-2 text-xs leading-5 text-[var(--af-text-secondary)] md:grid-cols-3">
                <p>
                  URL-first: {diagnostics.url_first_diagnostics.valid_url_count}/
                  {diagnostics.retrieval_evaluation.source_count}
                </p>
                <p>
                  WeChat strict: {diagnostics.url_first_diagnostics.strict_wechat_path_count}/
                  {diagnostics.url_first_diagnostics.wechat_url_count}
                </p>
                <p>7 年窗: since {diagnostics.retrieval_evaluation.recency_cutoff_year}</p>
              </div>
            </div>

            <div className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-sm font-semibold text-[var(--af-text-primary)]">
                {t("research.upgradeFallbackTitle", "下一步动作")}
              </p>
              <div className="mt-3 space-y-2">
                {diagnostics.fallback_actions.slice(0, 3).map((action) => (
                  <div key={`${action.priority}-${action.action}`} className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${priorityClass[action.priority] || "af-chip"}`}>
                        {action.priority}
                      </span>
                      <p className="text-sm font-semibold text-[var(--af-text-primary)]">{action.action}</p>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">
                      {action.owner} · {action.reason}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
            {diagnostics.expert_panels.map((panel) => (
              <div key={panel.role} className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                <p className="text-sm font-semibold text-[var(--af-text-primary)]">{panel.label}</p>
                <p className="mt-2 text-2xl font-semibold text-[var(--af-text-primary)]">{panel.score}</p>
                <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">
                  {panel.findings[0] || panel.next_actions[0] || ""}
                </p>
              </div>
            ))}
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-3">
            <div className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-sm font-semibold text-[var(--af-text-primary)]">
                {t("research.upgradeEvidenceQuotaTitle", "章节证据配额")}
              </p>
              <div className="mt-3 space-y-2">
                {diagnostics.section_evidence_quotas.map((quota) => (
                  <div key={quota.section_title} className="rounded-[16px] bg-[var(--af-surface-muted)] p-3">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-semibold text-[var(--af-text-primary)]">{quota.section_title}</p>
                      <span className={quota.passed ? "af-chip af-chip-success" : "af-chip af-chip-warning"}>
                        {quota.actual_evidence_count}/{quota.required_evidence_count}
                      </span>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">{quota.note}</p>
                  </div>
                ))}
              </div>
            </div>

            <div className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-sm font-semibold text-[var(--af-text-primary)]">
                {t("research.upgradeFieldDiffTitle", "字段变化复核")}
              </p>
              <div className="mt-3 space-y-2">
                {changedFields.slice(0, 4).map((diff) => (
                  <div key={diff.field} className="rounded-[16px] bg-[var(--af-surface-muted)] p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="af-chip">{diff.status}</span>
                      <p className="text-sm font-semibold text-[var(--af-text-primary)]">{diff.field}</p>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">{diff.summary}</p>
                    <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">
                      {diff.before || "空"} → {diff.after || "空"}
                    </p>
                  </div>
                ))}
                {!changedFields.length ? (
                  <p className="text-xs text-[var(--af-text-tertiary)]">
                    {t("research.upgradeNoFieldDiffs", "字段未发生变化。")}
                  </p>
                ) : null}
              </div>
            </div>

            <div className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-sm font-semibold text-[var(--af-text-primary)]">
                {t("research.upgradeSourceContributionTitle", "来源贡献")}
              </p>
              <div className="mt-3 space-y-2">
                {diagnostics.source_type_contributions.map((source) => (
                  <div key={source.source_type} className="rounded-[16px] bg-[var(--af-surface-muted)] p-3">
                    <div className="flex items-start justify-between gap-2">
                      <p className="text-sm font-semibold text-[var(--af-text-primary)]">{source.source_type}</p>
                      <span className="af-chip">{source.contribution_percent}%</span>
                    </div>
                    <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">
                      accepted {source.accepted_count}/{source.count} · avg {source.average_relevance_score}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          </div>

          <div className="mt-4 rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
            <p className="text-sm font-semibold text-[var(--af-text-primary)]">
              {t("research.upgradeRetrievalHitsTitle", "检索命中复核")}
            </p>
            <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-3">
              {diagnostics.retrieval_evaluation.hits.slice(0, 3).map((hit) => (
                <div key={hit.url} className="rounded-[16px] bg-[var(--af-surface-muted)] p-3">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className={hit.accepted ? "af-chip af-chip-success" : "af-chip af-chip-warning"}>
                      {hit.accepted ? "accepted" : "review"}
                    </span>
                    <span className="text-xs font-semibold text-[var(--af-text-secondary)]">{hit.relevance_score}</span>
                  </div>
                  <p className="mt-2 text-sm font-semibold leading-5 text-[var(--af-text-primary)]">{hit.title}</p>
                  <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">
                    {hit.source_type} · {hit.reason}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
      <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">{label}</p>
      <p className="mt-2 text-2xl font-semibold text-[var(--af-text-primary)]">{value}</p>
    </div>
  );
}
