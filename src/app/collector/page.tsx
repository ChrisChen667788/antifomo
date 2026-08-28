import { PageShell } from "@/components/layout/page-shell";
import { CollectorImportsPanel } from "@/components/settings/collector-imports-panel";
import { CollectorOpsPanel } from "@/components/settings/collector-ops-panel";
import { CollectorSourcesPanel } from "@/components/settings/collector-sources-panel";

export default function CollectorPage() {
  return (
    <PageShell
      title="Collector"
      description="管理自动采集、重试和日报。"
      titleKey="page.collector.title"
      descriptionKey="page.collector.description"
    >
      <div className="space-y-5">
        <CollectorImportsPanel />
        <CollectorSourcesPanel />
        <CollectorOpsPanel />
      </div>
    </PageShell>
  );
}
