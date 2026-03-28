import { PageShell } from "@/components/layout/page-shell";
import { SavedList } from "@/components/saved/saved-list";
import type { FeedItem } from "@/lib/mock-data";
import { listSavedItems, toFeedCardLabel } from "@/lib/api";
import { resolveItemTitle } from "@/lib/item-title";

async function loadSavedItems(): Promise<{ items: FeedItem[]; message: string }> {
  try {
    const response = await listSavedItems(30);
    if (!response.items.length) {
      return {
        items: [],
        message: "暂无真实收藏数据，当前不再自动回退演示卡片。",
      };
    }
    return {
      items: response.items.map((item) => {
      const score =
        item.score_value !== null && item.score_value !== undefined
          ? Math.round(((item.score_value - 1) / 4) * 100)
          : 50;

      return {
        id: item.id,
        title: resolveItemTitle(item, ""),
        source: item.source_domain || "",
        tags: (item.tags || []).map((tag) => tag.tag_name),
        summary: item.short_summary || item.long_summary || "",
        shortSummary: item.short_summary || "",
        longSummary: item.long_summary || "",
        valueScore: score,
        suggestedAction: toFeedCardLabel(item.action_suggestion || null),
        recommendationReasons: item.recommendation_reason || [],
        whyRecommended: item.why_recommended || [],
        matchedPreferences: item.matched_preferences || [],
        topicMatchScore: item.topic_match_score ?? undefined,
        sourceMatchScore: item.source_match_score ?? undefined,
        preferenceVersion: item.preference_version || undefined,
        url: item.source_url || "#",
      };
      }),
      message: "",
    };
  } catch {
    return {
      items: [],
      message: "收藏页当前未连上 API，已停止自动显示演示卡片。",
    };
  }
}

export default async function SavedPage() {
  const { items, message } = await loadSavedItems();
  return (
    <PageShell
      title="收藏 / 稍后读"
      description="按主题与评分筛选，保证之后能快速找回。"
      titleKey="page.saved.title"
      descriptionKey="page.saved.description"
    >
      {message ? (
        <div className="af-glass mb-4 rounded-3xl px-4 py-3 text-sm text-slate-600">
          {message}
        </div>
      ) : null}
      <SavedList items={items} />
    </PageShell>
  );
}
