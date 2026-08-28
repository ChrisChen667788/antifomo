import { FocusTimer } from "@/components/focus/focus-timer";
import { PageShell } from "@/components/layout/page-shell";

export default function FocusPage() {
  return (
    <PageShell
      title="Focus"
      description="设定目标，开始专注。"
      titleKey="page.focus.title"
      descriptionKey="page.focus.description"
    >
      <FocusTimer />
    </PageShell>
  );
}
