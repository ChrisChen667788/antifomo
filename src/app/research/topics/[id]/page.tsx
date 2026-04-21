import { PageShell } from "@/components/layout/page-shell";
import { ResearchTopicWorkspace } from "@/components/research/research-topic-workspace";

export default async function ResearchTopicPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <PageShell
      title="专题工作台"
      description="查看长期跟踪专题的最新版本、历史版本与关键指标变化。"
    >
      <ResearchTopicWorkspace topicId={id} />
    </PageShell>
  );
}
