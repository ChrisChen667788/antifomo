"use client";

import { useEffect, useMemo, useState } from "react";
import {
  getResearchAssurancePreview,
  type ApiResearchAssuranceSnapshot,
  type ApiResearchAssuranceStatus,
} from "@/lib/api";

type TranslationFn = (key: string, fallback: string) => string;

const statusClass: Record<ApiResearchAssuranceStatus, string> = {
  pass: "af-chip af-chip-success",
  watch: "af-chip af-chip-warning",
  blocked: "af-chip bg-rose-100 text-rose-700",
};

const statusLabel: Record<ApiResearchAssuranceStatus, string> = {
  pass: "通过",
  watch: "关注",
  blocked: "阻断",
};

export function ResearchCenterAssuranceSection({ t }: { t: TranslationFn }) {
  const [snapshot, setSnapshot] = useState<ApiResearchAssuranceSnapshot | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    const load = async () => {
      setLoading(true);
      setError("");
      try {
        const result = await getResearchAssurancePreview();
        if (active) setSnapshot(result);
      } catch {
        if (active) setError(t("research.assuranceLoadFailed", "读取质量保障计划失败。"));
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
    const counts: Record<ApiResearchAssuranceStatus, number> = { pass: 0, watch: 0, blocked: 0 };
    snapshot?.rounds.forEach((round) => {
      counts[round.status] += 1;
    });
    return counts;
  }, [snapshot]);

  return (
    <section
      data-testid="research-assurance-section"
      className="mt-5 scroll-mt-20 rounded-[28px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] p-4 shadow-[var(--af-shadow-soft)]"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-2xl">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
            {t("research.assuranceKicker", "质量保障")}
          </p>
          <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
            {t(
              "research.assuranceDesc",
              "按真实研报、质量队列、模型账本、人工复核和发布工件汇总 15 个后续版本的完成状态。",
            )}
          </p>
        </div>
        <div className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-1 text-xs font-semibold text-[var(--af-text-secondary)]">
          {snapshot ? `${snapshot.program_version} · ${snapshot.score}/100 · ${statusLabel[snapshot.status]}` : "..."}
        </div>
      </div>

      {loading ? <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">{t("research.assuranceLoading", "读取保障状态...")}</p> : null}
      {error ? <p className="mt-4 text-sm text-[var(--af-warning)]">{error}</p> : null}

      {snapshot ? (
        <>
          <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-3">
            {snapshot.summary_lines.map((line) => (
              <p
                key={line}
                className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-xs leading-5 text-[var(--af-text-secondary)]"
              >
                {line}
              </p>
            ))}
          </div>

          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-5">
            <Metric label="通过" value={statusCounts.pass} />
            <Metric label="关注" value={statusCounts.watch} />
            <Metric label="阻断" value={statusCounts.blocked} />
            <Metric label="研报" value={`${snapshot.valid_report_count}/${snapshot.report_sample_size}`} />
            <Metric label="异常数据" value={snapshot.invalid_report_count} />
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-[1.2fr_0.8fr]">
            <details className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <summary className="cursor-pointer list-none text-sm font-semibold text-[var(--af-text-primary)] [&::-webkit-details-marker]:hidden">
                {t("research.assuranceRoundDetails", `查看全部 ${snapshot.rounds.length} 轮核验项`)}
              </summary>
              <div className="mt-3 grid grid-cols-1 gap-2 md:grid-cols-2">
                {snapshot.rounds.map((round) => (
                  <article
                    key={round.key}
                    className="rounded-[20px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3"
                  >
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <p className="text-xs font-semibold text-[var(--af-text-primary)]">
                          {round.version} · {round.label}
                        </p>
                        <p className="mt-1 text-xs leading-5 text-[var(--af-text-secondary)]">{round.summary}</p>
                      </div>
                      <span className={`rounded-full px-2 py-0.5 text-[11px] font-semibold ${statusClass[round.status]}`}>
                        {statusLabel[round.status]}
                      </span>
                    </div>
                    <div className="mt-3 space-y-1.5 text-[11px] leading-4 text-[var(--af-text-secondary)]">
                      {round.metrics.slice(0, 2).map((metric) => (
                        <p key={metric.key} title={metric.summary}>
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

            <div className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-sm font-semibold text-[var(--af-text-primary)]">
                {t("research.assuranceNextActions", "当前优先动作")}
              </p>
              <div className="mt-3 space-y-2">
                {snapshot.next_actions.slice(0, 6).map((action) => (
                  <p
                    key={action}
                    className="rounded-[16px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2 text-xs leading-5 text-[var(--af-text-secondary)]"
                  >
                    {action}
                  </p>
                ))}
                {!snapshot.next_actions.length ? (
                  <p className="text-xs leading-5 text-[var(--af-text-secondary)]">
                    {t("research.assuranceNoActions", "当前没有待处理的保障动作。")}
                  </p>
                ) : null}
              </div>
            </div>
          </div>
        </>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
      <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-[var(--af-text-tertiary)]">{label}</p>
      <p className="mt-1 text-lg font-semibold text-[var(--af-text-primary)]">{value}</p>
    </div>
  );
}
