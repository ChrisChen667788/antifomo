"use client";

import { useMemo, useState } from "react";
import {
  type ApiResearchMarkdownArchive,
  deleteResearchMarkdownArchive,
  getResearchMarkdownArchive,
} from "@/lib/api";
import type {
  ArchiveDeliveryFilter,
  ArchiveSortMode,
} from "@/components/research/research-center-markdown-archives-section";
import {
  buildArchiveDeliveryDigest,
  buildArchiveDeliveryScore,
} from "@/lib/research-archive-metadata";
import { triggerMarkdownDownload } from "@/components/research/research-center-utils";

type TranslationFn = (key: string, fallback: string) => string;

export function useResearchCenterArchiveController({
  t,
  markdownArchives,
  onMarkdownArchiveDeleted,
  onAfterMarkdownArchiveDeleted,
}: {
  t: TranslationFn;
  markdownArchives: ApiResearchMarkdownArchive[];
  onMarkdownArchiveDeleted: (archiveId: string) => void;
  onAfterMarkdownArchiveDeleted: () => Promise<unknown>;
}) {
  const [archiveLinkMessage, setArchiveLinkMessage] = useState("");
  const [archiveDeliveryFilter, setArchiveDeliveryFilter] = useState<ArchiveDeliveryFilter>("all");
  const [archiveSortMode, setArchiveSortMode] = useState<ArchiveSortMode>("updated_desc");
  const [archiveSaving, setArchiveSaving] = useState(false);

  const visibleMarkdownArchives = useMemo(() => {
    return markdownArchives
      .map((archive) => ({
        archive,
        digest: buildArchiveDeliveryDigest(archive),
        score: buildArchiveDeliveryScore(archive),
      }))
      .filter(({ score }) => {
        if (archiveDeliveryFilter === "strong_evidence") {
          return score.hasEvidenceSignal && score.evidenceStrength >= 18 && score.outstandingCount <= 1;
        }
        if (archiveDeliveryFilter === "needs_followup") {
          return score.outstandingCount > 0;
        }
        if (archiveDeliveryFilter === "official_rich") {
          return score.hasEvidenceSignal && score.officialRatio >= 0.45 && score.officialCount > 0;
        }
        return true;
      })
      .sort((left, right) => {
        if (archiveSortMode === "evidence_strength" && right.score.evidenceStrength !== left.score.evidenceStrength) {
          return right.score.evidenceStrength - left.score.evidenceStrength;
        }
        if (archiveSortMode === "outstanding_count" && right.score.outstandingCount !== left.score.outstandingCount) {
          return right.score.outstandingCount - left.score.outstandingCount;
        }
        if (archiveSortMode === "official_ratio" && right.score.officialRatio !== left.score.officialRatio) {
          return right.score.officialRatio - left.score.officialRatio;
        }
        return new Date(right.archive.updated_at).getTime() - new Date(left.archive.updated_at).getTime();
      });
  }, [archiveDeliveryFilter, archiveSortMode, markdownArchives]);

  const archiveFilterMeta: Array<{ key: ArchiveDeliveryFilter; label: string }> = [
    { key: "all", label: t("research.archiveFilterAll", "全部归档") },
    { key: "strong_evidence", label: t("research.archiveFilterStrongEvidence", "证据较强") },
    { key: "needs_followup", label: t("research.archiveFilterNeedsFollowup", "待核验较多") },
    { key: "official_rich", label: t("research.archiveFilterOfficialRich", "官方源占比较高") },
  ];

  const archiveSortMeta: Array<{ key: ArchiveSortMode; label: string }> = [
    { key: "updated_desc", label: t("research.archiveSortUpdated", "按更新时间") },
    { key: "evidence_strength", label: t("research.archiveSortEvidence", "按证据强度") },
    { key: "outstanding_count", label: t("research.archiveSortOutstanding", "按待核验数量") },
    { key: "official_ratio", label: t("research.archiveSortOfficialRatio", "按官方源占比") },
  ];

  const handleDownloadMarkdownArchive = async (archive: ApiResearchMarkdownArchive) => {
    const detail = await getResearchMarkdownArchive(archive.id);
    triggerMarkdownDownload(detail.filename, detail.content);
  };

  const handleDeleteMarkdownArchive = async (archiveId: string) => {
    setArchiveSaving(true);
    try {
      await deleteResearchMarkdownArchive(archiveId);
      onMarkdownArchiveDeleted(archiveId);
      await onAfterMarkdownArchiveDeleted();
    } finally {
      setArchiveSaving(false);
    }
  };

  return {
    archiveLinkMessage,
    setArchiveLinkMessage,
    archiveDeliveryFilter,
    setArchiveDeliveryFilter,
    archiveSortMode,
    setArchiveSortMode,
    archiveSaving,
    visibleMarkdownArchives,
    archiveFilterMeta,
    archiveSortMeta,
    handleDownloadMarkdownArchive,
    handleDeleteMarkdownArchive,
  };
}
