import { notFound } from "next/navigation";
import { PageShell } from "@/components/layout/page-shell";
import { KnowledgeDetailCard } from "@/components/knowledge/knowledge-detail-card";
import { getKnowledgeEntry } from "@/lib/api";

interface KnowledgeDetailPageProps {
  params: Promise<{ id: string }>;
}

async function loadKnowledgeEntry(id: string) {
  try {
    return await getKnowledgeEntry(id);
  } catch {
    return null;
  }
}

export default async function KnowledgeDetailPage({ params }: KnowledgeDetailPageProps) {
  const { id } = await params;
  const item = await loadKnowledgeEntry(id);

  if (!item) {
    notFound();
  }

  return (
    <PageShell
      title="知识卡片"
      description="查看沉淀后的结构化结论，并跳回原内容详情。"
      titleKey="page.knowledge.title"
    >
      <KnowledgeDetailCard item={item} />
    </PageShell>
  );
}
