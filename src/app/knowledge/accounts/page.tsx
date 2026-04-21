import { PageShell } from "@/components/layout/page-shell";
import { KnowledgeCommercialHub } from "@/components/knowledge/knowledge-commercial-hub";
import { getKnowledgeDashboard, listKnowledgeAccounts, listKnowledgeOpportunities } from "@/lib/api";

async function loadAccountWorkspace() {
  try {
    const [dashboard, accounts, opportunities] = await Promise.all([
      getKnowledgeDashboard(),
      listKnowledgeAccounts(24),
      listKnowledgeOpportunities(16),
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

export default async function KnowledgeAccountsPage() {
  const data = await loadAccountWorkspace();
  return (
    <PageShell
      title="账户情报"
      description="把研报中的甲方、预算窗口和下一步动作沉淀成连续可跟进的账户对象。"
    >
      <KnowledgeCommercialHub
        dashboard={data.dashboard}
        accounts={data.accounts}
        opportunities={data.opportunities}
        expanded
      />
    </PageShell>
  );
}
