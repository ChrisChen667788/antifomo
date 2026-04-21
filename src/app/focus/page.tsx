import { FocusTimer } from "@/components/focus/focus-timer";
import { PageShell } from "@/components/layout/page-shell";

export default function FocusPage() {
  return (
    <PageShell
      title="Focus"
      description="选择 25/50 分钟专注时段，输入本次目标并开始倒计时。"
      titleKey="page.focus.title"
      descriptionKey="page.focus.description"
    >
      <FocusTimer />
    </PageShell>
  );
}
