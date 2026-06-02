"use client";

import { ExternalLinkActions, normalizeExternalUrl } from "@/components/ui/external-link-actions";
import type { ApiResearchReport } from "@/lib/api/types";
import type { ReportToneMeta } from "@/components/inbox/research-report-section-types";

type SectionConfidenceToneMeta = {
  panel: string;
  badge: string;
  item: string;
  excerpt: string;
};

export function ResearchReportInsightsSection({
  sections,
  insightsTitle,
  insightsDesc,
  confidenceToneMeta,
  sectionStatusMeta,
  qualityTone,
  qualityLabel,
  sourceTierLabel,
}: {
  sections: ApiResearchReport["sections"];
  insightsTitle: string;
  insightsDesc: string;
  confidenceToneMeta: (value?: string) => SectionConfidenceToneMeta;
  sectionStatusMeta: (value?: string) => ReportToneMeta;
  qualityTone: (value: string) => string;
  qualityLabel: (value: string) => string;
  sourceTierLabel: (value: string) => string;
}) {
  return (
    <>
      {sections.length > 0 ? (
        <div className="mt-5">
          <div className="mb-3">
            <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">{insightsTitle}</p>
            <p className="mt-1 text-sm text-[var(--af-text-tertiary)]">{insightsDesc}</p>
          </div>
        <div className="grid gap-4 md:grid-cols-2">
          {sections.map((section) => {
            const tone = confidenceToneMeta(section.confidence_tone);
            const statusMeta = sectionStatusMeta(section.status);
            return (
            <article
              key={section.title}
              className={`rounded-2xl border p-4 ${tone.panel}`}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <h4 className="text-sm font-semibold text-[var(--af-text-primary)]">{section.title}</h4>
                <div className="flex flex-wrap gap-2 text-[11px]">
                  {section.confidence_label ? (
                    <span className={`rounded-full px-2 py-0.5 ${tone.badge}`}>
                      {section.confidence_label}
                    </span>
                  ) : null}
                  <span className={`rounded-full px-2 py-0.5 ${statusMeta.className}`}>
                    {statusMeta.label}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 ${qualityTone(section.evidence_density || "low")}`}>
                    证据密度·{qualityLabel(section.evidence_density || "low")}
                  </span>
                  <span className={`rounded-full px-2 py-0.5 ${qualityTone(section.source_quality || "low")}`}>
                    来源质量·{qualityLabel(section.source_quality || "low")}
                  </span>
                  {section.official_source_ratio ? (
                    <span className="rounded-full bg-[color-mix(in_srgb,var(--af-success)_9%,var(--af-surface-muted))] px-2 py-0.5 text-[var(--af-success)]">
                      官方源·{Math.round(section.official_source_ratio * 100)}%
                    </span>
                  ) : null}
                  {typeof section.evidence_quota === "number" && section.evidence_quota > 0 ? (
                    <span
                      className={`rounded-full px-2 py-0.5 ${
                        section.meets_evidence_quota
                          ? "af-chip af-chip-success"
                          : "af-chip af-chip-warning"
                      }`}
                    >
                      配额 {section.evidence_count || 0}/{section.evidence_quota}
                    </span>
                  ) : null}
                </div>
              </div>
              <ul className="mt-3 space-y-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                {section.items.map((item) => (
                  <li key={item} className={`flex gap-2 rounded-xl px-2 py-1.5 ${tone.item}`}>
                    <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-border-strong)]" />
                    <span>{item}</span>
                  </li>
                ))}
              </ul>
              {section.insufficiency_reasons?.length ? (
                <div className="mt-3 rounded-2xl border border-[color-mix(in_srgb,var(--af-danger)_30%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-danger)]">
                    为什么还不够
                  </p>
                  <ul className="mt-2 space-y-1.5 text-xs leading-5 text-[var(--af-text-secondary)]">
                    {section.insufficiency_reasons.slice(0, 3).map((reason) => (
                      <li key={`${section.title}-${reason}`} className="flex gap-2">
                        <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-danger)]" />
                        <span>{reason}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {section.confidence_reason ? (
                <p className="mt-3 text-xs leading-5 text-[var(--af-text-secondary)]">{section.confidence_reason}</p>
              ) : null}
              {section.evidence_note ? (
                <p className="mt-3 text-xs leading-5 text-[var(--af-text-tertiary)]">{section.evidence_note}</p>
              ) : null}
              {section.quota_note ? (
                <p
                  className={`mt-2 text-xs leading-5 ${
                    section.meets_evidence_quota ? "text-[var(--af-success)]" : "text-[var(--af-warning)]"
                  }`}
                >
                  {section.quota_note}
                </p>
              ) : null}
              {section.next_verification_steps?.length ? (
                <div className="mt-3 rounded-2xl border border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_10%,var(--af-surface-muted))] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-warning)]">
                    下一步核验
                  </p>
                  <ul className="mt-2 space-y-1.5 text-xs leading-5 text-[var(--af-warning)]">
                    {section.next_verification_steps.slice(0, 3).map((step) => (
                      <li key={`${section.title}-${step}`} className="flex gap-2">
                        <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-[var(--af-warning)]" />
                        <span>{step}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              ) : null}
              {section.evidence_links?.length ? (
                <div className="mt-3 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-[var(--af-text-tertiary)]">证据锚点</p>
                  <div className="mt-2 space-y-2">
                    {section.evidence_links.slice(0, 3).map((link) => (
                      <div
                        key={`${section.title}-${link.url}`}
                        className={`block rounded-xl border border-[var(--af-border-subtle)] px-3 py-2 text-xs text-[var(--af-text-secondary)] transition hover:border-[var(--af-border-subtle)] hover:bg-[var(--af-surface-hover)] ${tone.excerpt}`}
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          <a
                            href={normalizeExternalUrl(link.url)}
                            target="_blank"
                            rel="noreferrer"
                            className="font-medium text-[var(--af-text-primary)] underline-offset-4 text-[var(--af-info)] hover:underline"
                          >
                            {link.anchor_text || link.title}
                          </a>
                          <span className="rounded-full bg-[var(--af-surface-muted)] px-2 py-0.5 text-[10px] text-[var(--af-text-tertiary)]">
                            {sourceTierLabel(link.source_tier || "media")}
                          </span>
                          {link.source_label ? (
                            <span className="rounded-full bg-[var(--af-surface-muted)] px-2 py-0.5 text-[10px] text-[var(--af-text-tertiary)]">
                              {link.source_label}
                            </span>
                          ) : null}
                        </div>
                        {link.excerpt ? (
                          <p className="mt-2 rounded-lg bg-[var(--af-surface-elevated)] px-2 py-1.5 text-[11px] leading-5 text-[var(--af-text-secondary)]">
                            {link.excerpt}
                          </p>
                        ) : (
                          <p className="mt-1 line-clamp-1 text-[11px] text-[var(--af-text-tertiary)]">{link.title}</p>
                        )}
                        <ExternalLinkActions
                          url={link.url}
                          className="mt-2"
                          openLabel="网页打开"
                        />
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}
            </article>
            );
          })}
          </div>
        </div>
      ) : null}
    </>
  );
}
