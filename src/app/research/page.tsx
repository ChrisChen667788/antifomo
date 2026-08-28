import { PageShell } from "@/components/layout/page-shell";
import { ResearchCenter } from "@/components/research/research-center";

export default function ResearchPage() {
  return (
    <PageShell
      title="商机情报中心"
      description="查看情报、动作和重点提醒。"
      titleKey="page.research.title"
      descriptionKey="page.research.description"
    >
      <ResearchCenter />
    </PageShell>
  );
}
