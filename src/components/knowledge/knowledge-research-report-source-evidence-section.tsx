"use client";

import type { ApiResearchSource } from "@/lib/api/types";
import type { KnowledgeReportSurfaceCopy } from "@/components/knowledge/knowledge-detail-card-model";
import { ExternalLinkActions, normalizeExternalUrl } from "@/components/ui/external-link-actions";

export interface KnowledgeResearchSourceGroup {
  key: string;
  title: string;
  items: ApiResearchSource[];
}

interface KnowledgeResearchReportSourceEvidenceSectionProps {
  groupedResearchSources: KnowledgeResearchSourceGroup[];
  copy: KnowledgeReportSurfaceCopy;
}

export function KnowledgeResearchReportSourceEvidenceSection({
  groupedResearchSources,
  copy,
}: KnowledgeResearchReportSourceEvidenceSectionProps) {
  if (!groupedResearchSources.length) {
    return null;
  }

  return (
    <div>
      <div className="mb-3">
        <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">{copy.sourceTitle}</p>
        <p className="mt-1 text-sm text-[var(--af-text-tertiary)]">按来源类型查看原文入口，便于快速复核关键结论和动作依据。</p>
      </div>
      <div className="grid gap-4">
        {groupedResearchSources.map((group) => (
          <article key={group.key} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">{group.title}</p>
            <div className="mt-3 space-y-3">
              {group.items.slice(0, 4).map((source) => (
                <div
                  key={`${group.key}-${source.url}`}
                  className="block rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3 transition hover:border-[var(--af-border-strong)] hover:bg-[var(--af-surface-hover)]"
                >
                  <a
                    href={normalizeExternalUrl(source.url)}
                    target="_blank"
                    rel="noreferrer"
                    className="text-sm font-semibold leading-6 text-[var(--af-text-primary)] underline-offset-4 hover:text-[var(--af-info)] hover:underline"
                  >
                    {source.title}
                  </a>
                  <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">
                    {[source.source_label, source.domain || "web"].filter(Boolean).join(" · ")}
                  </p>
                  <ExternalLinkActions
                    url={source.url}
                    className="mt-3"
                    openLabel="网页打开"
                  />
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
    </div>
  );
}
