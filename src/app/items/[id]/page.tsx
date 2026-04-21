import { notFound } from "next/navigation";
import { PageShell } from "@/components/layout/page-shell";
import {
  ItemDetailContent,
  type DetailItemViewModel,
} from "@/components/item/item-detail-content";
import { getItem, getItemDiagnostics } from "@/lib/api";
import { resolveItemTitle } from "@/lib/item-title";

interface ItemDetailPageProps {
  params: Promise<{ id: string }>;
}

async function loadDetailItem(id: string): Promise<DetailItemViewModel | null> {
  try {
    const [item, diagnostics] = await Promise.all([
      getItem(id),
      getItemDiagnostics(id).catch(() => null),
    ]);
    const valueScore =
      item.score_value !== null && item.score_value !== undefined
        ? Math.round(((item.score_value - 1) / 4) * 100)
        : 50;

    return {
      id: item.id,
      title: resolveItemTitle(item, ""),
      source: item.source_domain || "",
      url: item.source_url || "#",
      tags: (item.tags || []).map((tag) => tag.tag_name),
      rawContent: item.raw_content || "",
      cleanContent: item.clean_content || "",
      shortSummary: item.short_summary || "",
      longSummary: item.long_summary || "",
      suggestedActionType:
        item.action_suggestion === "deep_read"
          ? "deep_read"
          : item.action_suggestion === "later"
            ? "later"
            : "skip",
      valueScore,
      recommendationReasons: item.recommendation_reason || [],
      whyRecommended: item.why_recommended || [],
      matchedPreferences: item.matched_preferences || [],
      topicMatchScore: item.topic_match_score ?? undefined,
      sourceMatchScore: item.source_match_score ?? undefined,
      preferenceVersion: item.preference_version || undefined,
      diagnostics: diagnostics
        ? {
            ingestRoute: diagnostics.ingest_route,
            contentAcquisitionStatus: diagnostics.content_acquisition_status,
            contentAcquisitionNote:
              diagnostics.content_acquisition_note || "当前没有额外采集说明。",
            bodySource: diagnostics.body_source || "unknown",
            fallbackUsed: diagnostics.fallback_used,
            attemptCount: diagnostics.attempt_count,
            processingStatus: diagnostics.processing_status,
          }
        : undefined,
    };
  } catch {
    return null;
  }
}

export default async function ItemDetailPage({ params }: ItemDetailPageProps) {
  const { id } = await params;
  const item = await loadDetailItem(id);

  if (!item) {
    notFound();
  }

  return (
    <PageShell
      title="Item 详情"
      description="查看摘要、标签、建议动作，并进行用户操作。"
      titleKey="page.item.title"
      descriptionKey="page.item.description"
    >
      <ItemDetailContent item={item} />
    </PageShell>
  );
}
