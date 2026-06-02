"use client";

import { ExternalLinkActions, normalizeExternalUrl } from "@/components/ui/external-link-actions";
import type { ApiResearchReport } from "@/lib/api/types";
import type { ResearchReportSource } from "@/components/inbox/research-report-section-types";

export function ResearchReportSourceListSection({
  sources,
  hideSources,
  sourcesLabel,
  sourceTierLabel,
  classifySourceTier,
}: {
  sources: ApiResearchReport["sources"];
  hideSources: boolean;
  sourcesLabel: string;
  sourceTierLabel: (value: string) => string;
  classifySourceTier: (source: ResearchReportSource) => string;
}) {
  return (
    <>
      {!hideSources && sources.length > 0 ? (
        <div className="mt-6 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">{sourcesLabel}</p>
          <ol className="mt-3 space-y-3 text-sm leading-6 text-[var(--af-text-secondary)]">
            {sources.map((source, index) => (
              <li key={`${source.url}-${index}`} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-3">
                <div className="flex flex-wrap items-center gap-2 text-xs text-[var(--af-text-tertiary)]">
                  <span className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-2 py-0.5 font-semibold text-[var(--af-text-secondary)]">
                    [{index + 1}]
                  </span>
                  <span className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-2 py-0.5">
                    {sourceTierLabel(source.source_tier || classifySourceTier(source))}
                  </span>
                  {source.source_label ? (
                    <span className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-2 py-0.5">
                      {source.source_label}
                    </span>
                  ) : null}
                  <span className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-2 py-0.5">
                    {source.domain || "web"}
                  </span>
                  <span>{source.source_type}</span>
                </div>
                <a
                  href={normalizeExternalUrl(source.url)}
                  target="_blank"
                  rel="noreferrer"
                  className="mt-2 block text-sm font-semibold leading-6 text-[var(--af-text-primary)] underline-offset-4 hover:underline"
                >
                  {source.title}
                </a>
                <p className="mt-1 text-sm leading-6 text-[var(--af-text-secondary)]">{source.snippet}</p>
                <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">{source.url}</p>
                <ExternalLinkActions
                  url={source.url}
                  className="mt-3"
                  openLabel="网页打开"
                />
              </li>
            ))}
          </ol>
        </div>
      ) : null}
    </>
  );
}
