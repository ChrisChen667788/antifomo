import { InboxForm } from "@/components/inbox/inbox-form";
import { PageShell } from "@/components/layout/page-shell";

export default function InboxPage() {
  return (
    <PageShell
      title="解决方案智囊"
      description="输入主题，生成研报和交付文件。"
      titleKey="page.inbox.title"
      descriptionKey="page.inbox.description"
    >
      <InboxForm />
    </PageShell>
  );
}
