"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import type { ApiSessionArtifact, ApiTaskBriefingContext } from "@/lib/api/types";
import { AppIcon } from "@/components/ui/app-icon";

export function MetricCard({ label, value }: { label: string; value: string }) {
  return (
    <div className="af-glass rounded-3xl p-4">
      <p className="af-kicker">{label}</p>
      <p className="mt-2 text-2xl font-semibold tracking-[-0.03em] text-[var(--af-text-primary)]">{value}</p>
    </div>
  );
}

export function TaskBriefingContextCard({
  context,
  title,
  compact = false,
}: {
  context: ApiTaskBriefingContext | null;
  title: string;
  compact?: boolean;
}) {
  if (!context) {
    return null;
  }
  const account = context.account;
  const riskRows = compact ? (context.top_alerts.length ? context.top_alerts : context.review_queue).slice(0, 2) : [];
  return (
    <div className="mt-3 rounded-2xl border border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--af-info)]">{title}</p>
      {account ? (
        <div className="mt-2 space-y-2 text-sm text-[var(--af-text-secondary)]">
          <p className="font-semibold text-[var(--af-text-primary)]">{account.name || "核心账户"}</p>
          {account.objective ? <p>推进目标：{account.objective}</p> : null}
          {account.next_meeting_goal ? <p>下次会议目标：{account.next_meeting_goal}</p> : null}
          {!compact && account.stakeholders.length ? (
            <div className="flex flex-wrap gap-2">
              {account.stakeholders.slice(0, 3).map((item) => (
                <span key={`${item.name}-${item.role}`} className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px] text-[var(--af-text-secondary)]">
                  {item.name || item.role}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
      {compact && riskRows.length ? (
        <div className="mt-3 space-y-2 text-sm text-[var(--af-text-secondary)]">
          {riskRows.map((item) => (
            <div key={`${item.title}-${item.account_name}`} className="rounded-2xl bg-[var(--af-surface-elevated)] px-3 py-2">
              <p className="font-medium text-[var(--af-text-primary)]">{item.title}</p>
              <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">{item.recommended_action || item.summary}</p>
            </div>
          ))}
        </div>
      ) : null}
      {!compact && context.review_queue.length ? (
        <div className="mt-3 space-y-2">
          {context.review_queue.slice(0, 2).map((item) => (
            <div key={item.id} className="rounded-2xl bg-[var(--af-surface-elevated)] px-3 py-2 text-sm text-[var(--af-text-secondary)]">
              <p className="font-medium text-[var(--af-text-primary)]">{item.title}</p>
              <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">{item.recommended_action || item.summary}</p>
            </div>
          ))}
        </div>
      ) : null}
    </div>
  );
}

export function OutputBlock({
  title,
  content,
  emptyText,
  onCopy,
  copyLabel,
  artifact,
  extraActions,
  contextBlock,
}: {
  title: string;
  content: string;
  emptyText: string;
  onCopy: (content: string) => Promise<void>;
  copyLabel: string;
  artifact?: ApiSessionArtifact | null;
  extraActions?: ReactNode;
  contextBlock?: ReactNode;
}) {
  return (
    <div className="mt-4">
      <p className="af-kicker">{title}</p>
      {content ? (
        <div className="mt-2">
          <div className="mb-2 flex flex-wrap justify-end gap-2">
            {extraActions}
            <button
              type="button"
              onClick={() => {
                void onCopy(content);
              }}
              className="inline-flex items-center gap-1 rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px] font-semibold text-[var(--af-text-tertiary)]"
            >
              <AppIcon name="copy" className="h-3.5 w-3.5" />
              {copyLabel}
            </button>
          </div>
          <textarea
            readOnly
            value={content}
            rows={8}
            className="w-full rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-4 py-3 font-mono text-xs leading-6 text-[var(--af-text-secondary)] outline-none md:text-sm"
          />
          {contextBlock}
          {artifact?.items?.length ? <ArtifactSources artifact={artifact} /> : null}
        </div>
      ) : (
        <div className="mt-2 space-y-2">
          <p className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-4 py-3 text-sm text-[var(--af-text-tertiary)]">
            {emptyText}
          </p>
          {extraActions ? <div className="flex justify-end">{extraActions}</div> : null}
        </div>
      )}
    </div>
  );
}

function ArtifactSources({ artifact }: { artifact: ApiSessionArtifact }) {
  return (
    <div className="mt-3 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-4 py-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">
        来源条目
      </p>
      <div className="mt-2 space-y-2">
        {artifact.items.map((item) => (
          <div key={item.id} className="flex flex-wrap items-center justify-between gap-3 text-sm">
            <div className="min-w-0 flex-1">
              <div className="truncate font-medium text-[var(--af-text-primary)]">{item.title_snapshot}</div>
              <div className="truncate text-xs text-[var(--af-text-tertiary)]">
                {item.included_reason || "artifact_reference"}
              </div>
            </div>
            <div className="flex shrink-0 items-center gap-2">
              {item.source_url_snapshot ? (
                <a
                  href={item.source_url_snapshot}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded-full border border-[color-mix(in_srgb,var(--af-info)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-info)_14%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] font-semibold text-[var(--af-info)]"
                >
                  原文
                </a>
              ) : null}
              {item.item_id ? (
                <Link
                  href={`/items/${item.item_id}`}
                  className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px] font-semibold text-[var(--af-text-secondary)]"
                >
                  详情
                </Link>
              ) : null}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
