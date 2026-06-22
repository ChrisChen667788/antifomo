"use client";

import Link from "next/link";
import type { ApiKnowledgeEntry } from "@/lib/api/types";
import type { KnowledgeTranslateFn } from "@/components/knowledge/knowledge-detail-card-model";
import { AppIcon } from "@/components/ui/app-icon";

interface KnowledgeDetailRelatedSectionProps {
  entry: ApiKnowledgeEntry;
  relatedEntries: ApiKnowledgeEntry[];
  t: KnowledgeTranslateFn;
}

export function KnowledgeDetailRelatedSection({
  entry,
  relatedEntries,
  t,
}: KnowledgeDetailRelatedSectionProps) {
  return (
    <>
      {relatedEntries.length ? (
        <section className="af-glass rounded-[30px] p-5 md:p-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <p className="af-kicker">{t("knowledge.relatedTitle", "关联卡片")}</p>
              <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">
                {t("knowledge.relatedSubtitle", "这些卡片和当前主题接近，适合继续串联或合并。")}
              </p>
            </div>
          </div>
          <div className="mt-4 grid grid-cols-1 gap-3">
            {relatedEntries.map((related) => (
              <Link
                key={related.id}
                href={`/knowledge/${related.id}`}
                className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-4 py-4 transition hover:-translate-y-0.5 hover:bg-[var(--af-surface-hover)]"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap gap-2">
                      {related.is_pinned ? (
                        <span className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2 py-0.5 text-[11px] text-[var(--af-info)]">
                          {t("knowledge.pinned", "置顶")}
                        </span>
                      ) : null}
                      {related.collection_name ? (
                        <span className="rounded-full bg-[var(--af-surface-muted)] px-2 py-0.5 text-[11px] text-[var(--af-text-secondary)]">
                          {related.collection_name}
                        </span>
                      ) : null}
                    </div>
                    <h3 className="truncate text-sm font-semibold text-[var(--af-text-primary)]">{related.title}</h3>
                    <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
                      {related.source_domain || t("common.unknownSource", "未知来源")}
                    </p>
                  </div>
                  <AppIcon name="external" className="mt-0.5 h-4 w-4 text-[var(--af-text-tertiary)]" />
                </div>
                <p
                  className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]"
                  style={{
                    display: "-webkit-box",
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: "vertical",
                    overflow: "hidden",
                  }}
                >
                  {related.content}
                </p>
              </Link>
            ))}
          </div>
        </section>
      ) : null}

      {entry.item_id ? (
        <section className="af-glass rounded-[30px] p-5 md:p-6">
          <Link href={`/items/${entry.item_id}`} className="af-btn af-btn-primary px-4 py-2">
            <AppIcon name="external" className="h-4 w-4" />
            {t("knowledge.openItem", "打开原内容详情")}
          </Link>
        </section>
      ) : null}
    </>
  );
}
