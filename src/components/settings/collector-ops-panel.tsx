"use client";

import { useAppPreferences } from "@/components/settings/app-preferences-provider";
import { CollectorOpsDaemonSection } from "@/components/settings/collector-ops-daemon-section";
import { CollectorOpsGeneralSection } from "@/components/settings/collector-ops-general-section";
import { CollectorOpsWechatAgentSection } from "@/components/settings/collector-ops-wechat-agent-section";
import { useCollectorOpsPanelController } from "@/components/settings/use-collector-ops-panel-controller";
import { localText } from "@/components/settings/collector-ops-panel-copy";

export function CollectorOpsPanel() {
  const { preferences } = useAppPreferences();
  const language = preferences.language;
  const controller = useCollectorOpsPanelController({
    language,
    text: (key) => localText(language, key),
  });

  return (
    <section className="af-glass rounded-[30px] p-5 md:p-6">
      <p className="af-kicker">{localText(language, "title")}</p>
      <p className="mt-2 text-sm text-[var(--af-text-tertiary)]">{localText(language, "description")}</p>

      <CollectorOpsDaemonSection controller={controller} language={language} text={(key) => localText(language, key)} />

      <CollectorOpsWechatAgentSection controller={controller} text={(key) => localText(language, key)} />

      <CollectorOpsGeneralSection controller={controller} text={(key) => localText(language, key)} />
    </section>
  );
}
