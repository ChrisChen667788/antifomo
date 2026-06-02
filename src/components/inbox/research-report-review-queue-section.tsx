"use client";

import { ExternalLinkActions, normalizeExternalUrl } from "@/components/ui/external-link-actions";
import type { ApiResearchReport } from "@/lib/api/types";

export function ResearchReportReviewQueueSection({
  reviewQueue,
  reviewQueueTitle,
  reviewQueueDesc,
}: {
  reviewQueue: NonNullable<ApiResearchReport["review_queue"]>;
  reviewQueueTitle: string;
  reviewQueueDesc: string;
}) {
  return (
    <>
      {reviewQueue.length ? (
        <article className="mt-5 rounded-2xl border border-[color-mix(in_srgb,var(--af-danger)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">{reviewQueueTitle}</p>
              <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">{reviewQueueDesc}</p>
            </div>
            <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-xs text-[var(--af-text-secondary)]">{reviewQueue.length} 条</span>
          </div>
          <div className="mt-4 space-y-3">
            {reviewQueue.map((item) => (
              <div key={`review-${item.id}`} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-3">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm font-semibold text-[var(--af-text-primary)]">{item.section_title}</p>
                  <span className={`rounded-full px-2 py-0.5 text-[10px] ${item.severity === "high" ? "af-chip af-chip-danger" : item.severity === "medium" ? "af-chip af-chip-warning" : "bg-[var(--af-surface-muted)] text-[var(--af-text-tertiary)]"}`}>
                    {item.severity === "high" ? "高优先级" : item.severity === "medium" ? "中优先级" : "低优先级"}
                  </span>
                </div>
                <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{item.summary}</p>
                {item.recommended_action ? (
                  <p className="mt-2 text-sm font-medium leading-6 text-[var(--af-danger)]">建议：{item.recommended_action}</p>
                ) : null}
                {item.evidence_links?.length ? (
                  <div className="mt-3 space-y-2">
                    {item.evidence_links.slice(0, 2).map((link) => (
                      <div key={`review-evidence-${item.id}-${link.url}`} className="rounded-xl border border-[color-mix(in_srgb,var(--af-danger)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-danger)_10%,var(--af-surface-muted))] px-3 py-2">
                        <a
                          href={normalizeExternalUrl(link.url)}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs font-medium text-[var(--af-text-primary)] underline-offset-4 text-[var(--af-danger)] hover:underline"
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
              </div>
            ))}
          </div>
        </article>
      ) : null}
    </>
  );
}
