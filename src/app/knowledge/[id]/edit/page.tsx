import { notFound } from "next/navigation";
import { PageShell } from "@/components/layout/page-shell";
import { KnowledgeEditForm } from "@/components/knowledge/knowledge-edit-form";
import { getKnowledgeEntry } from "@/lib/api";

interface KnowledgeEditPageProps {
  params: Promise<{ id: string }>;
}

async function loadEntry(id: string) {
  try {
    return await getKnowledgeEntry(id);
  } catch {
    return null;
  }
}

export default async function KnowledgeEditPage({ params }: KnowledgeEditPageProps) {
  const { id } = await params;
  const entry = await loadEntry(id);

  if (!entry) {
    notFound();
  }

  const isActionCard = entry.metadata_payload?.kind === "research_action_card";

  return (
    <PageShell
      title={isActionCard ? "编辑行动卡" : "编辑知识卡片"}
      description={
        isActionCard
          ? "调整优先级、对象、时间窗和建议步骤，系统会自动重建行动卡内容。"
          : "调整标题、内容、分组和 Focus 参考状态。"
      }
    >
      <KnowledgeEditForm item={entry} />
    </PageShell>
  );
}
