import { InboxForm } from "@/components/inbox/inbox-form";
import { PageShell } from "@/components/layout/page-shell";

export default function InboxPage() {
  return (
    <PageShell
      title="解决方案智囊"
      description="按区域、行业与关键词收敛输入，生成更像咨询顾问底稿的多源方案研判。"
      titleKey="page.inbox.title"
      descriptionKey="page.inbox.description"
    >
      <InboxForm />
    </PageShell>
  );
}
