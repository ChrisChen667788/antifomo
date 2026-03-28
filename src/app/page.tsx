import { FeedHomeClient } from "@/components/feed/feed-home-client";
import { PageShell } from "@/components/layout/page-shell";

export default function FeedPage() {
  return (
    <PageShell
      title="Anti-FOMO"
      description="1秒判断推文价值,从信息大爆炸中解放自我"
      titleKey="page.feed.title"
      descriptionKey="page.feed.description"
    >
      <FeedHomeClient />
    </PageShell>
  );
}
