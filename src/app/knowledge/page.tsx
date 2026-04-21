import { PageShell } from "@/components/layout/page-shell";
import { KnowledgeCommercialHub } from "@/components/knowledge/knowledge-commercial-hub";
import { KnowledgeList } from "@/components/knowledge/knowledge-list";
import { getKnowledgeDashboard, listKnowledgeAccounts, listKnowledgeEntries, listKnowledgeOpportunities } from "@/lib/api";

async function loadKnowledgeEntries() {
  try {
    const response = await listKnowledgeEntries(30);
    return response.items;
  } catch {
    return [];
  }
}

async function loadCommercialData() {
  try {
    const [dashboard, accounts, opportunities] = await Promise.all([
      getKnowledgeDashboard(),
      listKnowledgeAccounts(6),
      listKnowledgeOpportunities(6),
    ]);
    return {
      dashboard,
      accounts: accounts.items,
      opportunities: opportunities.items,
    };
  } catch {
    return {
      dashboard: {
        account_count: 0,
        opportunity_count: 0,
        high_confidence_report_count: 0,
        benchmark_case_count: 0,
        top_accounts: [],
        top_opportunities: [],
        top_alerts: [],
        role_views: [],
        review_queue: [],
      },
      accounts: [],
      opportunities: [],
    };
  }
}

export default async function KnowledgePage() {
  const [items, commercial] = await Promise.all([loadKnowledgeEntries(), loadCommercialData()]);

  return (
    <PageShell
      title="知识库列表"
      description="查看已沉淀的知识卡片，并回到原始内容继续延展。"
      titleKey="page.knowledge.title"
      descriptionKey="page.knowledge.description"
    >
      <div className="space-y-5">
        <KnowledgeCommercialHub
          dashboard={commercial.dashboard}
          accounts={commercial.accounts}
          opportunities={commercial.opportunities}
        />
        <KnowledgeList items={items} />
      </div>
    </PageShell>
  );
}
