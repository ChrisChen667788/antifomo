import { notFound } from "next/navigation";
import { PageShell } from "@/components/layout/page-shell";
import { KnowledgeAccountWorkspace } from "@/components/knowledge/knowledge-account-workspace";
import { getKnowledgeAccountDetail } from "@/lib/api";

interface KnowledgeAccountDetailPageProps {
  params: Promise<{ slug: string }>;
}

async function loadAccount(slug: string) {
  try {
    return await getKnowledgeAccountDetail(slug);
  } catch {
    return null;
  }
}

export default async function KnowledgeAccountDetailPage({ params }: KnowledgeAccountDetailPageProps) {
  const { slug } = await params;
  const account = await loadAccount(slug);

  if (!account) {
    notFound();
  }

  return (
    <PageShell
      title={account.name}
      description="查看账户成熟度、预算概率、下一步动作与关联研报。"
    >
      <KnowledgeAccountWorkspace account={account} />
    </PageShell>
  );
}
