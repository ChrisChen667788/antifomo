
"use client";

import type { useCollectorOpsPanelController } from "@/components/settings/use-collector-ops-panel-controller";
import { shortText } from "@/components/settings/collector-ops-panel-utils";

type CollectorOpsPanelController = ReturnType<typeof useCollectorOpsPanelController>;

type CollectorOpsWechatAgentLogSectionProps = {
  controller: CollectorOpsPanelController;
  text: (key: string) => string;
};

export function CollectorOpsWechatAgentLogSection({
  controller,
  text,
}: CollectorOpsWechatAgentLogSectionProps) {
  const {
    wechatAgentStatus,
    wechatAgentOutput,
  } = controller;

  return (
    <>
      {wechatAgentStatus?.last_cycle_error ? (
        <p className="mt-2 text-xs text-[var(--af-warning)]">
          {text("wechatAgentCycleError")}: {shortText(wechatAgentStatus.last_cycle_error, 180)}
        </p>
      ) : null}

      <details className="mt-2 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-inset)] px-3 py-2">
        <summary className="cursor-pointer text-[11px] uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">
          高级记录
        </summary>
        <pre className="mt-2 max-h-36 overflow-auto whitespace-pre-wrap text-[11px] leading-5 text-[var(--af-text-secondary)]">
          {wechatAgentOutput || (wechatAgentStatus?.log_tail || []).join("\n") || "-"}
        </pre>
      </details>
    </>
  );
}
