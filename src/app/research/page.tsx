import { PageShell } from "@/components/layout/page-shell";
import { ResearchCenter } from "@/components/research/research-center";

export default function ResearchPage() {
  return (
    <PageShell
      title="商机情报中心"
      description="查看关键词情报简报、推荐动作与 Focus 参考，持续沉淀行业情报与客户推进动作。"
      titleKey="page.research.title"
      descriptionKey="page.research.description"
    >
      <ResearchCenter />
    </PageShell>
  );
}
