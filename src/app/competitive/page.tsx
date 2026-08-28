import { CompetitiveIntelligenceWorkspace } from "@/components/competitive-intelligence/competitive-intelligence-workspace";
import { PageShell } from "@/components/layout/page-shell";

export default function CompetitiveIntelligencePage() {
  return (
    <PageShell
      title="竞品能力证据台账"
      description="用官方来源、时效和明确的产品决策边界审查后续版本机会。"
    >
      <CompetitiveIntelligenceWorkspace />
    </PageShell>
  );
}
