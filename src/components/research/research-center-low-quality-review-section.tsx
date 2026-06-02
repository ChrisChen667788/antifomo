"use client";

import Link from "next/link";
import type { useResearchCenterController } from "@/components/research/use-research-center-controller";
import {
  lowQualityReviewStatusLabel,
  lowQualityReviewStatusTone,
  qualityLabel,
  qualityTone,
} from "@/components/research/research-center-utils";
import { sanitizeExternalDisplayText } from "@/lib/commercial-risk-copy";

type ResearchCenterController = ReturnType<typeof useResearchCenterController>;
type ResearchCenterLowQualityReviewSectionProps = ResearchCenterController["lowQualityReviewSectionProps"];

export function ResearchCenterLowQualityReviewSection({
  t,
  lowQualityQueue,
  lowQualityLoading,
  lowQualityActionKey,
  lowQualityMessage,
  lowQualityError,
  handleRewriteLowQualityItem,
  handleResolveLowQualityItem,
}: ResearchCenterLowQualityReviewSectionProps) {
  return (
          <section className="af-glass rounded-[30px] p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="af-kicker">Review Queue</p>
                <h3 className="mt-2 text-lg font-semibold text-[var(--af-text-primary)]">低质量研报审计队列</h3>
                <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
                  {sanitizeExternalDisplayText("将低质量条目沉淀为可审查队列，支持先查看修订差异，再决定接受或回退。")}
                </p>
              </div>
              <div className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-1.5 text-xs text-[var(--af-text-tertiary)]">
                待处理 · {lowQualityQueue?.flagged_reports ?? 0}
              </div>
            </div>
            <div className="mt-4 flex flex-wrap gap-2 text-[11px]">
              <span className="rounded-full af-chip px-2.5 py-1 ">
                扫描研报 {lowQualityQueue?.total_reports ?? 0}
              </span>
              <span className="rounded-full af-chip af-chip-danger px-2.5 py-1 ">
                队列样本 {lowQualityQueue?.items.length ?? 0}
              </span>
              {(lowQualityQueue?.invalid_payloads ?? 0) > 0 ? (
                <span className="rounded-full af-chip af-chip-warning px-2.5 py-1 ">
                  schema 异常 {lowQualityQueue?.invalid_payloads ?? 0}
                </span>
              ) : null}
            </div>
            {lowQualityQueue?.recommendations?.length ? (
              <p className="mt-3 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-secondary)]">
                {sanitizeExternalDisplayText(lowQualityQueue.recommendations[0])}
              </p>
            ) : null}
            {lowQualityMessage ? <p className="mt-3 text-sm text-[var(--af-success)]">{lowQualityMessage}</p> : null}
            {lowQualityError ? <p className="mt-3 text-sm text-[var(--af-danger)]">{lowQualityError}</p> : null}
            {lowQualityLoading ? (
              <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">{t("common.loading", "加载中")}</p>
            ) : lowQualityQueue?.items.length ? (
              <div className="mt-4 space-y-3">
                {lowQualityQueue.items.map((item) => {
                  const latestRewrite = item.latest_rewrite;
                  const rewriteBusy = lowQualityActionKey === `${item.entry_id}:rewrite`;
                  const acceptBusy = lowQualityActionKey === `${item.entry_id}:accept`;
                  const revertBusy = lowQualityActionKey === `${item.entry_id}:revert`;
                  return (
                    <article key={item.entry_id} className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="text-sm font-semibold text-[var(--af-text-primary)]">{item.report_title || item.entry_title || item.entry_id}</p>
                          <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
                            {item.keyword || "历史研报"} · 风险 {item.risk_score} · 来源 {item.source_count}
                          </p>
                        </div>
                        <div className="flex flex-wrap justify-end gap-2 text-[11px]">
                          <span className={`rounded-full px-2.5 py-1 font-medium ${lowQualityReviewStatusTone(item.review_status)}`}>
                            {lowQualityReviewStatusLabel(item.review_status)}
                          </span>
                          {item.guarded_backlog ? (
                            <span className="rounded-full af-chip af-chip-warning px-2.5 py-1 ">guarded backlog</span>
                          ) : null}
                          <span className={`rounded-full px-2.5 py-1 font-medium ${qualityTone(item.retrieval_quality || "low")}`}>
                            检索·{qualityLabel(item.retrieval_quality || "low")}
                          </span>
                          <span className="rounded-full af-chip px-2.5 py-1 ">
                            官方源 {Math.round((item.official_source_ratio || 0) * 100)}%
                          </span>
                        </div>
                      </div>
                      <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">{item.executive_summary || item.next_action || "待人工复核"}</p>
                      {item.issues?.length ? (
                        <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
                          {item.issues.slice(0, 3).map((issue) => (
                            <span key={`${item.entry_id}-${issue.code}`} className="rounded-full af-chip af-chip-danger px-2 py-1 ">
                              {issue.code}
                            </span>
                          ))}
                        </div>
                      ) : null}
                      {item.suggested_focus?.length ? (
                        <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">建议收口：{item.suggested_focus.join(" / ")}</p>
                      ) : null}
                      {latestRewrite ? (
                        <div className="mt-3 rounded-[18px] af-state-panel-info p-3">
                          <div className="flex flex-wrap items-center gap-2 text-[11px] text-[var(--af-info)]">
                            <span className="rounded-full bg-[var(--af-surface-elevated)] px-2 py-1">
                              {latestRewrite.rewrite_mode === "guarded" ? "谨慎修订" : "标准修订"}
                            </span>
                            <span>
                              风险 {latestRewrite.before_risk_score} → {latestRewrite.after_risk_score}
                            </span>
                          </div>
                          <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">Before · {latestRewrite.before_title || "空标题"}</p>
                          <p className="mt-1 text-sm font-medium text-[var(--af-text-primary)]">After · {latestRewrite.after_title || "空标题"}</p>
                          {latestRewrite.after_summary ? (
                            <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{sanitizeExternalDisplayText(latestRewrite.after_summary)}</p>
                          ) : null}
                        </div>
                      ) : null}
                      <div className="mt-3 flex flex-wrap gap-2">
                        <button
                          type="button"
                          onClick={() => void handleRewriteLowQualityItem(item.entry_id)}
                          className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                          disabled={Boolean(lowQualityActionKey)}
                        >
                          {rewriteBusy ? "重写中..." : "执行修订"}
                        </button>
                        {item.review_status === "rewritten" ? (
                          <button
                            type="button"
                            onClick={() => void handleResolveLowQualityItem(item.entry_id, "accept")}
                            className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                            disabled={Boolean(lowQualityActionKey)}
                          >
                            {acceptBusy ? "接受中..." : "接受结果"}
                          </button>
                        ) : null}
                        {item.has_rewrite_snapshot ? (
                          <button
                            type="button"
                            onClick={() => void handleResolveLowQualityItem(item.entry_id, "revert")}
                            className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                            disabled={Boolean(lowQualityActionKey)}
                          >
                            {revertBusy ? "回退中..." : "回退版本"}
                          </button>
                        ) : null}
                        <Link href={`/knowledge/${item.entry_id}`} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
                          打开研报
                        </Link>
                      </div>
                    </article>
                  );
                })}
              </div>
            ) : (
              <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">当前没有待处理的低质量研报。</p>
            )}
          </section>
  );
}
