"use client";

import type { ApiResearchReport } from "@/lib/api/types";
import type { KnowledgeReportSurfaceCopy } from "@/components/knowledge/knowledge-detail-card-model";
import { ExternalLinkActions, normalizeExternalUrl } from "@/components/ui/external-link-actions";

interface KnowledgeResearchReportReviewQueueSectionProps {
  reviewQueue: NonNullable<ApiResearchReport["review_queue"]>;
  reviewQueueActionId: string;
  copy: KnowledgeReportSurfaceCopy;
  onReviewQueueAction: (reviewId: string, action: "open" | "resolved" | "deferred") => void;
}

export function KnowledgeResearchReportReviewQueueSection({
  reviewQueue,
  reviewQueueActionId,
  copy,
  onReviewQueueAction,
}: KnowledgeResearchReportReviewQueueSectionProps) {
  if (!reviewQueue.length) {
    return null;
  }

  return (
    <article className="rounded-[24px] border border-[color-mix(in_srgb,var(--af-danger)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">{copy.reviewQueueTitle}</p>
          <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">{copy.reviewQueueDesc}</p>
        </div>
        <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-xs text-[var(--af-text-secondary)]">{reviewQueue.length} 条</span>
      </div>
      <div className="mt-4 space-y-3">
        {reviewQueue.map((item) => (
          <article key={`knowledge-review-${item.id}`} className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-semibold text-[var(--af-text-primary)]">{item.section_title}</p>
              <div className="flex flex-wrap items-center gap-2">
                <span className={`rounded-full px-2 py-0.5 text-[10px] ${item.severity === "high" ? "af-chip af-chip-danger" : item.severity === "medium" ? "af-chip af-chip-warning" : "af-chip"}`}>
                  {item.severity === "high" ? "高优先级" : item.severity === "medium" ? "中优先级" : "低优先级"}
                </span>
                <span className={`rounded-full px-2 py-0.5 text-[10px] ${item.resolution_status === "resolved" ? "af-chip af-chip-success" : item.resolution_status === "deferred" ? "af-chip af-chip-warning" : "af-chip"}`}>
                  {item.resolution_status === "resolved" ? "已核验" : item.resolution_status === "deferred" ? "已延后" : "待处理"}
                </span>
              </div>
            </div>
            <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{item.summary}</p>
            {item.recommended_action ? (
              <p className="mt-2 text-sm font-medium leading-6 text-[var(--af-danger)]">建议：{item.recommended_action}</p>
            ) : null}
            {item.resolution_note ? (
              <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">备注：{item.resolution_note}</p>
            ) : null}
            {item.evidence_links?.length ? (
              <div className="mt-3 space-y-2">
                {item.evidence_links.slice(0, 2).map((link) => (
                  <div key={`knowledge-review-evidence-${item.id}-${link.url}`} className="rounded-xl border border-[color-mix(in_srgb,var(--af-danger)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-danger)_14%,var(--af-surface-muted))] px-3 py-2">
                    <a
                      href={normalizeExternalUrl(link.url)}
                      target="_blank"
                      rel="noreferrer"
                      className="text-xs font-medium text-[var(--af-text-primary)] underline-offset-4 hover:text-[var(--af-danger)] hover:underline"
                    >
                      {link.anchor_text || link.title}
                    </a>
                    <ExternalLinkActions
                      url={link.url}
                      className="mt-2"
                      openLabel="网页打开"
                    />
                  </div>
                ))}
              </div>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              {item.resolution_status !== "resolved" ? (
                <button
                  type="button"
                  onClick={() => onReviewQueueAction(item.id, "resolved")}
                  disabled={reviewQueueActionId === item.id}
                  className="rounded-full border border-[color-mix(in_srgb,var(--af-success)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-success)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] font-semibold text-[var(--af-success)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {reviewQueueActionId === item.id ? "处理中..." : "标记已核验"}
                </button>
              ) : null}
              {item.resolution_status !== "deferred" ? (
                <button
                  type="button"
                  onClick={() => onReviewQueueAction(item.id, "deferred")}
                  disabled={reviewQueueActionId === item.id}
                  className="rounded-full border border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] font-semibold text-[var(--af-warning)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {reviewQueueActionId === item.id ? "处理中..." : "延后处理"}
                </button>
              ) : null}
              {item.resolution_status !== "open" ? (
                <button
                  type="button"
                  onClick={() => onReviewQueueAction(item.id, "open")}
                  disabled={reviewQueueActionId === item.id}
                  className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-2.5 py-1 text-[11px] font-semibold text-[var(--af-text-secondary)] disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {reviewQueueActionId === item.id ? "处理中..." : "重新打开"}
                </button>
              ) : null}
            </div>
          </article>
        ))}
      </div>
    </article>
  );
}
