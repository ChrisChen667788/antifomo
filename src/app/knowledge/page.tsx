import { PageShell } from "@/components/layout/page-shell";
import { KnowledgeList } from "@/components/knowledge/knowledge-list";
import { listKnowledgeEntries } from "@/lib/api";

async function loadKnowledgeEntries() {
  try {
    const response = await listKnowledgeEntries(30);
    return response.items;
  } catch {
    return [];
  }
}

export default async function KnowledgePage() {
  const items = await loadKnowledgeEntries();

  return (
    <PageShell
      title="知识库列表"
      description="查看已沉淀的知识卡片，并回到原始内容继续延展。"
      titleKey="page.knowledge.title"
      descriptionKey="page.knowledge.description"
    >
      <KnowledgeList items={items} />
    </PageShell>
  );
}
