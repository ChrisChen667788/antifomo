import { PageShell } from "@/components/layout/page-shell";
import { KnowledgeMergeWorkspace } from "@/components/knowledge/knowledge-merge-workspace";
import { getKnowledgeEntry } from "@/lib/api";

interface KnowledgeMergePageProps {
  searchParams: Promise<{ ids?: string; title?: string }>;
}

async function loadEntries(ids: string[]) {
  const results = await Promise.all(
    ids.map(async (id) => {
      try {
        return await getKnowledgeEntry(id);
      } catch {
        return null;
      }
    }),
  );
  return results.filter((item): item is NonNullable<typeof item> => Boolean(item));
}

export default async function KnowledgeMergePage({ searchParams }: KnowledgeMergePageProps) {
  const { ids = "", title = "" } = await searchParams;
  const entryIds = ids
    .split(",")
    .map((value) => value.trim())
    .filter(Boolean);
  const entries = await loadEntries(entryIds);

  return (
    <PageShell
      title="知识卡片合并"
      description="在正式合并前检查预览、继承状态和目标标题。"
    >
      <KnowledgeMergeWorkspace entries={entries} initialTitle={title} />
    </PageShell>
  );
}
