import { PageShell } from "@/components/layout/page-shell";
import { SessionSummaryPanel } from "@/components/session/session-summary-panel";
import type { SessionMetrics } from "@/lib/mock-data";

const EMPTY_SESSION_METRICS: SessionMetrics = {
  sessionId: undefined,
  durationMinutes: 0,
  goalText: "",
  newContentCount: 0,
  deepReadCount: 0,
  laterCount: 0,
  ignorableCount: 0,
};

export default function SessionSummaryPage() {
  return (
    <PageShell
      title="Session Summary"
      description="查看本轮专注统计，并生成 Markdown 总结、稍后读清单和待办草稿。"
      titleKey="page.summary.title"
      descriptionKey="page.summary.description"
    >
      <SessionSummaryPanel metrics={EMPTY_SESSION_METRICS} />
    </PageShell>
  );
}
