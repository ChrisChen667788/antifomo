import { notFound } from "next/navigation";
import { PageShell } from "@/components/layout/page-shell";
import { ResearchMarkdownArchiveViewer } from "@/components/research/research-markdown-archive-viewer";
import type { ApiResearchMarkdownArchive } from "@/lib/api";
import { getResearchMarkdownArchive, getResearchWorkspace } from "@/lib/api";

interface ResearchMarkdownArchivePageProps {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ compare?: string | string[] }>;
}

async function loadArchive(id: string) {
  try {
    return await getResearchMarkdownArchive(id);
  } catch {
    return null;
  }
}

function scoreRelatedArchive(currentId: string, compareId: string | null, archiveId: string, score: number) {
  if (archiveId === currentId) return Number.NEGATIVE_INFINITY;
  if (compareId && archiveId === compareId) return score + 1000;
  return score;
}

function buildRelatedArchives(
  archives: ApiResearchMarkdownArchive[],
  currentArchive: Awaited<ReturnType<typeof getResearchMarkdownArchive>>,
  compareArchiveId: string | null,
) {
  return [...archives]
    .map((archive) => {
      let score = 0;
      if (archive.archive_kind === currentArchive.archive_kind) score += 120;
      if (archive.tracking_topic_id && archive.tracking_topic_id === currentArchive.tracking_topic_id) score += 240;
      if (archive.report_version_id && archive.report_version_id === currentArchive.report_version_id) score += 90;
      if (archive.compare_snapshot_id && archive.compare_snapshot_id === currentArchive.compare_snapshot_id) score += 60;
      const updatedAt = Date.parse(archive.updated_at);
      if (Number.isFinite(updatedAt)) {
        score += Math.floor(updatedAt / 100000000);
      }
      return {
        archive,
        score: scoreRelatedArchive(currentArchive.id, compareArchiveId, archive.id, score),
      };
    })
    .filter((item) => Number.isFinite(item.score))
    .sort((left, right) => right.score - left.score)
    .map((item) => item.archive)
    .slice(0, 10);
}

export default async function ResearchMarkdownArchivePage({
  params,
  searchParams,
}: ResearchMarkdownArchivePageProps) {
  const { id } = await params;
  const resolvedSearchParams = await searchParams;
  const compareIdValue = resolvedSearchParams.compare;
  const compareId = Array.isArray(compareIdValue) ? compareIdValue[0] : compareIdValue || null;

  const [archive, workspace] = await Promise.all([loadArchive(id), getResearchWorkspace()]);

  if (!archive) {
    notFound();
  }

  const compareArchive =
    compareId && compareId !== archive.id ? await loadArchive(compareId) : null;
  const relatedArchives = buildRelatedArchives(workspace.markdown_archives || [], archive, compareArchive?.id || compareId);

  return (
    <PageShell
      title="Markdown 归档"
      description="在线查看历史归档，并在同一页面对照两个版本的结构与差异摘要。"
    >
      <ResearchMarkdownArchiveViewer
        archive={archive}
        compareArchive={compareArchive}
        relatedArchives={relatedArchives}
      />
    </PageShell>
  );
}
