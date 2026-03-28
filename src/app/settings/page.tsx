import { PageShell } from "@/components/layout/page-shell";
import { CommonSettingsPanel } from "@/components/settings/common-settings-panel";
import { CollectorOpsPanel } from "@/components/settings/collector-ops-panel";
import { PreferenceInsightsPanel } from "@/components/settings/preference-insights-panel";
import { RecommenderTuner } from "@/components/settings/recommender-tuner";
import { WorkBuddyPanel } from "@/components/settings/workbuddy-panel";

export default function SettingsPage() {
  return (
    <PageShell
      title="设置与调优"
      description="管理主题、字体、字号、语言，并保留推荐调优能力。"
      titleKey="page.settings.title"
      descriptionKey="page.settings.description"
    >
      <div className="space-y-5">
        <CommonSettingsPanel />
        <PreferenceInsightsPanel />
        <WorkBuddyPanel />
        <CollectorOpsPanel />
        <RecommenderTuner />
      </div>
    </PageShell>
  );
}
