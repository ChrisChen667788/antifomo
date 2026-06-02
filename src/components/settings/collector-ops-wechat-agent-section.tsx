
"use client";

import type { useCollectorOpsPanelController } from "@/components/settings/use-collector-ops-panel-controller";
import { CollectorOpsWechatAgentBatchSection } from "@/components/settings/collector-ops-wechat-agent-batch-section";
import { CollectorOpsWechatAgentConfigSection } from "@/components/settings/collector-ops-wechat-agent-config-section";
import { CollectorOpsWechatAgentLogSection } from "@/components/settings/collector-ops-wechat-agent-log-section";
import { CollectorOpsWechatAgentPreviewSection } from "@/components/settings/collector-ops-wechat-agent-preview-section";
import { CollectorOpsWechatAgentStatusSection } from "@/components/settings/collector-ops-wechat-agent-status-section";

type CollectorOpsPanelController = ReturnType<typeof useCollectorOpsPanelController>;

type CollectorOpsWechatAgentSectionProps = {
  controller: CollectorOpsPanelController;
  text: (key: string) => string;
};

export function CollectorOpsWechatAgentSection({
  controller,
  text,
}: CollectorOpsWechatAgentSectionProps) {
  return (
    <>
      <div className="mt-4 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
        <CollectorOpsWechatAgentStatusSection controller={controller} text={text} />
        <CollectorOpsWechatAgentBatchSection controller={controller} text={text} />
        <CollectorOpsWechatAgentLogSection controller={controller} text={text} />
        <CollectorOpsWechatAgentPreviewSection controller={controller} text={text} />
      </div>
      <CollectorOpsWechatAgentConfigSection controller={controller} text={text} />
    </>
  );
}
