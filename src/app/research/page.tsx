import { PageShell } from "@/components/layout/page-shell";
import { ResearchCenter } from "@/components/research/research-center";

export default function ResearchPage() {
  return (
    <PageShell
      title="研报中心"
      description="查看关键词研报、行动卡与 Focus 参考，持续沉淀行业情报与销售/投标动作。"
      titleKey="page.research.title"
      descriptionKey="page.research.description"
    >
      <ResearchCenter />
    </PageShell>
  );
}
