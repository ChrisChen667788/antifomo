import { DecisionStudioWorkspace } from "@/components/decision-studio/decision-studio-workspace";
import { PageShell } from "@/components/layout/page-shell";


export default function StudioPage() {
  return (
    <PageShell
      title="Decision Studio"
      description="证据绑定的 Notebook、正式文档、Claim Graph、治理与多形态决策工作台。"
    >
      <DecisionStudioWorkspace />
    </PageShell>
  );
}
