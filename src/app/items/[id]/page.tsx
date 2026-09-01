import { notFound } from "next/navigation";
import Link from "next/link";
import { PageShell } from "@/components/layout/page-shell";
import {
  ItemDetailContent,
  type DetailItemViewModel,
} from "@/components/item/item-detail-content";
import { getItem, getItemDiagnostics } from "@/lib/api";
import { DataSourceStateBadge } from "@/components/ui/data-source-state-badge";
import { isApiRequestError } from "@/lib/api/client";
import { resolveDataSourceState } from "@/lib/data-source-state";
import { resolveItemTitle } from "@/lib/item-title";

interface ItemDetailPageProps {
  params: Promise<{ id: string }>;
}

type DetailLoadResult =
  | { status: "ready"; item: DetailItemViewModel }
  | { status: "not_found" }
  | { status: "unavailable" };

async function loadDetailItem(id: string): Promise<DetailLoadResult> {
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
      status: "ready",
      item: {
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
        dataSourceState: resolveDataSourceState({
          itemCount: 1,
          hasFallbackContent: Boolean(item.fallback_used || diagnostics?.fallback_used),
        }),
        diagnostics: diagnostics
          ? {
              ingestRoute: diagnostics.ingest_route,
              contentAcquisitionStatus: diagnostics.content_acquisition_status,
              contentAcquisitionNote:
                diagnostics.content_acquisition_note || "内容已完成基础整理。",
              bodySource: diagnostics.body_source || "unknown",
              fallbackUsed: diagnostics.fallback_used,
              attemptCount: diagnostics.attempt_count,
              processingStatus: diagnostics.processing_status,
            }
          : undefined,
      },
    };
  } catch (error) {
    if (isApiRequestError(error) && error.status === 404) {
      return { status: "not_found" };
    }
    return { status: "unavailable" };
  }
}

export default async function ItemDetailPage({ params }: ItemDetailPageProps) {
  const { id } = await params;
  const result = await loadDetailItem(id);

  if (result.status === "not_found") {
    notFound();
  }

  if (result.status === "unavailable") {
    return (
      <PageShell
        title="内容详情"
        description="实时内容暂时无法读取。"
        titleKey="page.item.title"
        descriptionKey="page.item.description"
      >
        <div className="mx-auto max-w-2xl space-y-4">
          <DataSourceStateBadge
            state="unavailable"
            detail="内容详情 API 当前不可用；未回退演示或缓存内容，也没有把服务异常伪装成条目不存在。"
          />
          <div className="flex flex-wrap gap-3">
            <Link className="af-btn af-btn-primary" href={`/items/${encodeURIComponent(id)}`}>
              重试
            </Link>
            <Link className="af-btn af-btn-secondary" href="/">
              返回 Feed
            </Link>
          </div>
        </div>
      </PageShell>
    );
  }

  return (
    <PageShell
      title="内容详情"
      description="查看摘要、标签和建议动作。"
      titleKey="page.item.title"
      descriptionKey="page.item.description"
    >
      <ItemDetailContent item={result.item} />
    </PageShell>
  );
}
