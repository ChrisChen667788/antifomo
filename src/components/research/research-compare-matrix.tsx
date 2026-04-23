"use client";

import { useRouter } from "next/navigation";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { AppIcon } from "@/components/ui/app-icon";
import { ExternalLinkActions, normalizeExternalUrl } from "@/components/ui/external-link-actions";
import {
  createResearchMarkdownArchive,
  createResearchCompareSnapshot,
  getResearchCompareSnapshot,
  getResearchOfflineEvaluation,
  listKnowledgeEntries,
  type ApiKnowledgeEntry,
  type ApiResearchCompareSnapshotDetail,
  type ApiResearchOfflineEvaluation,
} from "@/lib/api";
import {
  buildResearchCompareExecBrief,
  buildResearchCompareExecBriefFilename,
  buildResearchCompareExportFilename,
  buildResearchCompareMarkdown,
  buildResearchComparePdfFilename,
  buildResearchComparePlainText,
  buildResearchCompareRows,
  summarizeResearchCompareEvidence,
  summarizeResearchCompareSectionDiagnostics,
  type ResearchCompareRow,
  type ResearchCompareRole,
} from "@/lib/research-compare";
import { buildSimplePdfFromText, triggerFileDownload } from "@/lib/research-delivery-export";
import { useAppPreferences } from "@/components/settings/app-preferences-provider";

type CompareRoleFilter = "all" | ResearchCompareRole;

function sourceTierLabel(tier: "official" | "media" | "aggregate", t: (key: string, fallback: string) => string) {
  if (tier === "official") return t("research.sourceOfficial", "官方源");
  if (tier === "aggregate") return t("research.sourceAggregate", "聚合源");
  return t("research.sourceMedia", "媒体源");
}

function diffStatusTone(status: string) {
  if (status === "aligned") return "bg-emerald-100 text-emerald-700";
  if (status === "expanded") return "bg-sky-100 text-sky-700";
  if (status === "trimmed") return "bg-amber-100 text-amber-700";
  if (status === "mixed") return "bg-rose-100 text-rose-700";
  return "bg-slate-100 text-slate-500";
}

function diffStatusLabel(status: string, t: (key: string, fallback: string) => string) {
  if (status === "aligned") return t("research.compareSnapshotDiffAligned", "主线一致");
  if (status === "expanded") return t("research.compareSnapshotDiffExpanded", "快照扩展");
  if (status === "trimmed") return t("research.compareSnapshotDiffTrimmed", "快照收敛");
  if (status === "mixed") return t("research.compareSnapshotDiffMixed", "双向差异");
  return t("research.compareSnapshotDiffUnavailable", "无法比较");
}

function offlineStatusTone(status: string) {
  if (status === "good") return "bg-emerald-100 text-emerald-700";
  if (status === "watch") return "bg-amber-100 text-amber-700";
  return "bg-rose-100 text-rose-700";
}

function offlineStatusLabel(status: string) {
  if (status === "good") return "达标";
  if (status === "watch") return "观察";
  return "偏弱";
}

function asRecord(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value) ? (value as Record<string, unknown>) : {};
}

function asPositiveNumber(value: unknown): number {
  const parsed = Number(value || 0);
  return Number.isFinite(parsed) && parsed > 0 ? Math.round(parsed) : 0;
}

function asStringList(value: unknown, limit = 8): string[] {
  return Array.isArray(value)
    ? value
        .map((item) => String(item || "").trim())
        .filter(Boolean)
        .filter((item, index, list) => list.indexOf(item) === index)
        .slice(0, limit)
    : [];
}

function asCleanString(value: unknown): string {
  return String(value || "").trim();
}

function formatSnapshotMetadataTime(value: string | null): string {
  if (!value) {
    return "";
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function parseSnapshotOfflineEvaluation(metadata: Record<string, unknown> | null | undefined): ApiResearchOfflineEvaluation | null {
  const summary = asRecord(asRecord(metadata).offline_evaluation_snapshot);
  if (!Object.keys(summary).length) {
    return null;
  }
  const metrics = Array.isArray(summary.metrics)
    ? summary.metrics
        .map((metric) => {
          const record = asRecord(metric);
          const key = String(record.key || "").trim();
          const label = String(record.label || "").trim();
          if (!key && !label) {
            return null;
          }
          return {
            key: key || label,
            label: label || key,
            numerator: asPositiveNumber(record.numerator),
            denominator: asPositiveNumber(record.denominator),
            rate: Number(record.rate || 0),
            percent: asPositiveNumber(record.percent),
            benchmark: Number(record.benchmark || 0),
            status: String(record.status || "bad"),
            summary: String(record.summary || "").trim(),
          };
        })
        .filter((metric): metric is ApiResearchOfflineEvaluation["metrics"][number] => Boolean(metric))
    : [];
  return {
    generated_at: String(summary.generated_at || new Date().toISOString()),
    total_reports: asPositiveNumber(summary.total_reports),
    evaluated_reports: asPositiveNumber(summary.evaluated_reports),
    invalid_payloads: asPositiveNumber(summary.invalid_payloads),
    metrics,
    weakest_reports: Array.isArray(summary.weakest_reports)
      ? summary.weakest_reports
          .map((item) => {
            const record = asRecord(item);
            return {
              entry_id: String(record.entry_id || ""),
              entry_title: String(record.entry_title || ""),
              report_title: String(record.report_title || ""),
              keyword: String(record.keyword || ""),
              weakness_score: asPositiveNumber(record.weakness_score),
              retrieval_hit: Boolean(record.retrieval_hit),
              supported_target_accounts: asPositiveNumber(record.supported_target_accounts),
              unsupported_target_accounts: asPositiveNumber(record.unsupported_target_accounts),
              unsupported_targets: asStringList(record.unsupported_targets, 6),
              quota_passed_section_count: asPositiveNumber(record.quota_passed_section_count),
              quota_total_section_count: asPositiveNumber(record.quota_total_section_count),
              failing_sections: asStringList(record.failing_sections, 6),
              official_source_ratio: Number(record.official_source_ratio || 0),
              strict_match_ratio: Number(record.strict_match_ratio || 0),
              retrieval_quality: String(record.retrieval_quality || "low"),
            };
          })
          .filter((item) => item.entry_id || item.entry_title || item.report_title)
      : [],
    summary_lines: asStringList(summary.summary_lines, 6),
  };
}

function parseSnapshotSectionDiagnosticsSummary(
  metadata: Record<string, unknown> | null | undefined,
): ReturnType<typeof summarizeResearchCompareSectionDiagnostics> | null {
  const summary = asRecord(asRecord(metadata).section_diagnostics_summary);
  if (!Object.keys(summary).length) {
    return null;
  }
  return {
    sourceReportCount: asPositiveNumber(summary.sourceReportCount ?? summary.source_report_count),
    weakSectionCount: asPositiveNumber(summary.weakSectionCount ?? summary.weak_section_count),
    quotaRiskSectionCount: asPositiveNumber(summary.quotaRiskSectionCount ?? summary.quota_risk_section_count),
    contradictionSectionCount: asPositiveNumber(summary.contradictionSectionCount ?? summary.contradiction_section_count),
    highlightedSections: asStringList(summary.highlightedSections ?? summary.highlighted_sections, 8),
  };
}

function sortEntries(items: ApiKnowledgeEntry[]): ApiKnowledgeEntry[] {
  return [...items].sort((left, right) => {
    const leftTime = new Date(left.updated_at || left.created_at).getTime();
    const rightTime = new Date(right.updated_at || right.created_at).getTime();
    return rightTime - leftTime;
  });
}

function serializeSnapshotRows(rows: ResearchCompareRow[]): Array<Record<string, unknown>> {
  return rows.map((row) => ({
    ...row,
    targetDepartments: [...row.targetDepartments],
    publicContacts: [...row.publicContacts],
    candidateProfileCompanies: [...row.candidateProfileCompanies],
    candidateProfileSourceLabels: [...row.candidateProfileSourceLabels],
    partnerHighlights: [...row.partnerHighlights],
    competitorHighlights: [...row.competitorHighlights],
    benchmarkCases: [...row.benchmarkCases],
    evidenceLinks: row.evidenceLinks.map((item) => ({ ...item })),
  }));
}

export function ResearchCompareMatrix({
  initialQuery = "",
  initialRegion = "",
  initialIndustry = "",
  initialSnapshotId = "",
  initialTopicId = "",
}: {
  initialQuery?: string;
  initialRegion?: string;
  initialIndustry?: string;
  initialSnapshotId?: string;
  initialTopicId?: string;
}) {
  const router = useRouter();
  const { t } = useAppPreferences();
  const [entries, setEntries] = useState<ApiKnowledgeEntry[]>([]);
  const [loadedQuery, setLoadedQuery] = useState<string | null>(null);
  const [query, setQuery] = useState(initialQuery);
  const [regionFilter, setRegionFilter] = useState(initialRegion);
  const [industryFilter, setIndustryFilter] = useState(initialIndustry);
  const [roleFilter, setRoleFilter] = useState<CompareRoleFilter>("all");
  const [statusNotice, setStatusNotice] = useState("");
  const [statusTone, setStatusTone] = useState<"success" | "error">("success");
  const [snapshotDetail, setSnapshotDetail] = useState<ApiResearchCompareSnapshotDetail | null>(null);
  const [offlineEvaluation, setOfflineEvaluation] = useState<ApiResearchOfflineEvaluation | null>(null);
  const [snapshotLoading, setSnapshotLoading] = useState(false);
  const [snapshotError, setSnapshotError] = useState("");
  const [savingSnapshot, setSavingSnapshot] = useState(false);
  const [archivingMarkdown, setArchivingMarkdown] = useState(false);
  const loading = loadedQuery !== initialQuery || snapshotLoading;

  useEffect(() => {
    let active = true;
    listKnowledgeEntries(80, {
      sourceDomain: "research.report",
      query: initialQuery || undefined,
    })
      .then((response) => {
        if (!active) return;
        setEntries(sortEntries(response.items || []));
      })
      .catch(() => {
        if (!active) return;
        setEntries([]);
      })
      .finally(() => {
        if (!active) return;
        setLoadedQuery(initialQuery);
      });
    return () => {
      active = false;
    };
  }, [initialQuery]);

  useEffect(() => {
    let active = true;
    getResearchOfflineEvaluation(6)
      .then((evaluation) => {
        if (!active) return;
        setOfflineEvaluation(evaluation);
      })
      .catch(() => {
        if (!active) return;
        setOfflineEvaluation(null);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!initialSnapshotId) {
      setSnapshotDetail(null);
      setSnapshotError("");
      return;
    }
    let active = true;
    setSnapshotLoading(true);
    setSnapshotError("");
    getResearchCompareSnapshot(initialSnapshotId)
      .then((snapshot) => {
        if (!active) return;
        setSnapshotDetail(snapshot);
        setQuery(snapshot.query || "");
        setRegionFilter(snapshot.region_filter || "");
        setIndustryFilter(snapshot.industry_filter || "");
        setRoleFilter(snapshot.role_filter || "all");
      })
      .catch(() => {
        if (!active) return;
        setSnapshotDetail(null);
        setSnapshotError(t("research.compareSnapshotLoadFailed", "保存的对比快照加载失败，请返回工作台重试"));
      })
      .finally(() => {
        if (!active) return;
        setSnapshotLoading(false);
      });
    return () => {
      active = false;
    };
  }, [initialSnapshotId, t]);

  const rows = useMemo<ResearchCompareRow[]>(
    () => (snapshotDetail?.rows as ResearchCompareRow[] | undefined) || buildResearchCompareRows(entries),
    [entries, snapshotDetail],
  );
  const regionOptions = useMemo(
    () => ["", ...new Set(rows.map((row) => row.region).filter(Boolean))],
    [rows],
  );
  const industryOptions = useMemo(
    () => ["", ...new Set(rows.map((row) => row.industry).filter(Boolean))],
    [rows],
  );

  const visibleRows = useMemo(
    () =>
      rows.filter((row) => {
        if (roleFilter !== "all" && row.role !== roleFilter) return false;
        if (regionFilter && row.region !== regionFilter) return false;
        if (industryFilter && row.industry !== industryFilter) return false;
        if (query) {
          const haystack = [
            row.name,
            row.clue,
            row.keyword,
            row.sourceEntryTitle,
            ...(row.targetDepartments || []),
            ...(row.publicContacts || []),
            ...(row.competitorHighlights || []),
            ...(row.partnerHighlights || []),
            ...(row.benchmarkCases || []),
          ]
            .join(" ")
            .toLowerCase();
          if (!haystack.includes(query.toLowerCase())) return false;
        }
        return true;
      }),
    [rows, roleFilter, regionFilter, industryFilter, query],
  );
  const evidenceSummary = useMemo(() => summarizeResearchCompareEvidence(visibleRows), [visibleRows]);
  const derivedSectionDiagnosticsSummary = useMemo(
    () => summarizeResearchCompareSectionDiagnostics(visibleRows),
    [visibleRows],
  );
  const snapshotOfflineEvaluation = useMemo(
    () => parseSnapshotOfflineEvaluation(snapshotDetail?.metadata_payload),
    [snapshotDetail],
  );
  const snapshotSectionDiagnosticsSummary = useMemo(
    () => parseSnapshotSectionDiagnosticsSummary(snapshotDetail?.metadata_payload),
    [snapshotDetail],
  );
  const snapshotMetadata = useMemo(() => asRecord(snapshotDetail?.metadata_payload), [snapshotDetail]);
  const snapshotMetadataOrigin = asCleanString(snapshotMetadata.snapshot_metadata_origin);
  const snapshotMetadataBackfilledAt = asCleanString(snapshotMetadata.snapshot_metadata_backfilled_at) || null;
  const snapshotMetadataBackfilledAtLabel = formatSnapshotMetadataTime(snapshotMetadataBackfilledAt);
  const isLegacyBackfilledSnapshot = snapshotMetadataOrigin === "legacy_backfill";
  const effectiveOfflineEvaluation = snapshotOfflineEvaluation || offlineEvaluation;
  const effectiveSectionDiagnosticsSummary = snapshotSectionDiagnosticsSummary || derivedSectionDiagnosticsSummary;
  const hasFrozenSnapshotMetadata = Boolean(snapshotOfflineEvaluation || snapshotSectionDiagnosticsSummary);

  const roleStats = useMemo(
    () =>
      ["甲方", "中标方", "竞品", "伙伴"].map((role) => ({
        role,
        count: rows.filter((row) => row.role === role).length,
      })),
    [rows],
  );

  const activeTopicId = snapshotDetail?.tracking_topic_id || initialTopicId || "";
  const liveCompareHref = useMemo(() => {
    const params = new URLSearchParams();
    if (query.trim()) params.set("query", query.trim());
    if (regionFilter) params.set("region", regionFilter);
    if (industryFilter) params.set("industry", industryFilter);
    if (activeTopicId) params.set("topicId", activeTopicId);
    const queryString = params.toString();
    return queryString ? `/research/compare?${queryString}` : "/research/compare";
  }, [activeTopicId, industryFilter, query, regionFilter]);

  const buildExportBundle = (generatedAt: Date) => {
    const exportOptions = {
      query,
      region: regionFilter,
      industry: industryFilter,
      role: roleFilter,
      generatedAt,
      snapshotName: snapshotDetail?.name,
      linkedVersionTitle: snapshotDetail?.report_version_title || undefined,
      linkedVersionRefreshedAt: snapshotDetail?.report_version_refreshed_at || null,
      linkedDiff: snapshotDetail?.linked_report_diff || null,
      offlineEvaluation: effectiveOfflineEvaluation,
      hasFrozenSnapshotMetadata,
      snapshotMetadataOrigin,
      snapshotMetadataBackfilledAt,
    };
    return {
      markdownFilename: buildResearchCompareExportFilename(exportOptions),
      pdfFilename: buildResearchComparePdfFilename(exportOptions),
      execBriefFilename: buildResearchCompareExecBriefFilename(exportOptions),
      markdown: buildResearchCompareMarkdown(visibleRows, exportOptions),
      plainText: buildResearchComparePlainText(visibleRows, exportOptions),
      execBrief: buildResearchCompareExecBrief(visibleRows, exportOptions),
      evidenceSummary,
      sectionDiagnosticsSummary: effectiveSectionDiagnosticsSummary,
      offlineEvaluationSnapshot: effectiveOfflineEvaluation,
    };
  };

  const handleExportMarkdown = () => {
    const generatedAt = new Date();
    const bundle = buildExportBundle(generatedAt);
    triggerFileDownload(bundle.markdownFilename, bundle.markdown, "text/markdown;charset=utf-8");
    setStatusTone("success");
    setStatusNotice(t("research.compareExported", "对比矩阵 Markdown 已导出"));
  };

  const handleExportPdf = () => {
    const generatedAt = new Date();
    const bundle = buildExportBundle(generatedAt);
    triggerFileDownload(bundle.pdfFilename, buildSimplePdfFromText(bundle.plainText), "application/pdf");
    setStatusTone("success");
    setStatusNotice(t("research.comparePdfExported", "对比矩阵 PDF 已导出"));
  };

  const handleExportExecBrief = () => {
    const generatedAt = new Date();
    const bundle = buildExportBundle(generatedAt);
    triggerFileDownload(bundle.execBriefFilename, bundle.execBrief, "text/markdown;charset=utf-8");
    setStatusTone("success");
    setStatusNotice(t("research.compareExecBriefExported", "Compare Exec Brief 已导出"));
  };

  const handleArchiveMarkdown = async () => {
    if (!visibleRows.length) return;
    const generatedAt = new Date();
    const bundle = buildExportBundle(generatedAt);
    const defaultName = snapshotDetail?.name
      ? `${snapshotDetail.name} · Markdown 归档`
      : `${query.trim() || "对比矩阵"} · Markdown 归档`;
    const name = window.prompt(
      t("research.compareArchivePrompt", "输入一个归档名称，便于在商机情报中心回看"),
      defaultName,
    )?.trim();
    if (!name) return;
    const summary =
      snapshotDetail?.summary ||
      snapshotDetail?.linked_report_diff?.summary_lines?.[0] ||
      `${visibleRows.length} 个实体，覆盖 ${
        ["甲方", "中标方", "竞品", "伙伴"].filter((role) => visibleRows.some((row) => row.role === role)).join(" / ") || "当前筛选角色"
      }`;
    setArchivingMarkdown(true);
    try {
      const saved = await createResearchMarkdownArchive({
        archive_kind: "compare_markdown",
        name,
        filename: bundle.markdownFilename,
        query: query.trim(),
        region_filter: regionFilter,
        industry_filter: industryFilter,
        tracking_topic_id: activeTopicId || undefined,
        compare_snapshot_id: snapshotDetail?.id || undefined,
        report_version_id: snapshotDetail?.report_version_id || undefined,
        summary,
        content: bundle.markdown,
        metadata_payload: {
          row_count: visibleRows.length,
          role_filter: roleFilter,
          snapshot_name: snapshotDetail?.name || "",
          linked_report_diff_status: snapshotDetail?.linked_report_diff?.status || "unavailable",
          evidence_appendix_summary: bundle.evidenceSummary,
          section_diagnostics_summary: bundle.sectionDiagnosticsSummary,
          offline_evaluation_snapshot: bundle.offlineEvaluationSnapshot || {},
          snapshot_metadata_origin: snapshotMetadataOrigin,
          snapshot_metadata_backfilled_at: snapshotMetadataBackfilledAt,
        },
      });
      setStatusTone("success");
      setStatusNotice(t("research.compareArchiveSaved", `已保存 Markdown 归档：${saved.name}`));
    } catch {
      setStatusTone("error");
      setStatusNotice(t("research.compareArchiveSaveFailed", "保存 Markdown 归档失败，请稍后重试"));
    } finally {
      setArchivingMarkdown(false);
    }
  };

  const handleSaveSnapshot = async () => {
    if (!visibleRows.length) return;
    const defaultName = `${query.trim() || snapshotDetail?.name || "对比矩阵"} · ${new Date().toLocaleDateString()}`;
    const name = window.prompt(
      t("research.compareSnapshotPrompt", "输入一个快照名称，便于后续回访"),
      defaultName,
    )?.trim();
    if (!name) return;
    setSavingSnapshot(true);
    try {
      const savedAt = new Date().toISOString();
      const saved = await createResearchCompareSnapshot({
        name,
        query: query.trim(),
        region_filter: regionFilter,
        industry_filter: industryFilter,
        role_filter: roleFilter,
        tracking_topic_id: activeTopicId || undefined,
        summary: `${visibleRows.length} 个实体，覆盖 ${
          ["甲方", "中标方", "竞品", "伙伴"]
            .filter((role) => visibleRows.some((row) => row.role === role))
            .join(" / ") || "当前筛选角色"
        }`,
        rows: serializeSnapshotRows(visibleRows),
        metadata_payload: {
          evidence_appendix_summary: evidenceSummary,
          section_diagnostics_summary: derivedSectionDiagnosticsSummary,
          offline_evaluation_snapshot: offlineEvaluation || {},
          snapshot_metadata_origin: "saved",
          snapshot_metadata_saved_at: savedAt,
        },
      });
      setStatusTone("success");
      setStatusNotice(t("research.compareSnapshotSaved", `已保存对比快照：${saved.name}`));
      const params = new URLSearchParams({ snapshot: saved.id });
      if (activeTopicId) params.set("topicId", activeTopicId);
      router.replace(`/research/compare?${params.toString()}`);
    } catch {
      setStatusTone("error");
      setStatusNotice(t("research.compareSnapshotSaveFailed", "保存对比快照失败，请稍后重试"));
    } finally {
      setSavingSnapshot(false);
    }
  };

  return (
    <div className="space-y-5">
      {snapshotDetail ? (
        <section className="af-glass rounded-[30px] p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <p className="af-kicker">{t("research.compareSnapshotKicker", "Saved Snapshot")}</p>
              <h3 className="mt-2 text-xl font-semibold text-slate-900">{snapshotDetail.name}</h3>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                {snapshotDetail.summary || t("research.compareSnapshotDesc", "当前正在查看已保存的对比结果快照，内容不会随实时研报刷新自动变化。")}
              </p>
              <div className="mt-3 flex flex-wrap gap-2 text-xs">
                <span className="rounded-full bg-white/75 px-2.5 py-1 text-slate-600">
                  {t("research.compareSnapshotRows", "实体数")} · {snapshotDetail.row_count}
                </span>
                <span className="rounded-full bg-white/75 px-2.5 py-1 text-slate-600">
                  {t("research.compareSnapshotSources", "来源研报")} · {snapshotDetail.source_entry_count}
                </span>
                <span className="rounded-full bg-white/75 px-2.5 py-1 text-slate-600">
                  {t("research.compareUpdated", "更新")} · {new Date(snapshotDetail.updated_at).toLocaleString()}
                </span>
                {snapshotDetail.tracking_topic_name ? (
                  <span className="rounded-full bg-sky-50 px-2.5 py-1 text-sky-700">
                    {t("research.compareSnapshotTopic", "关联专题")} · {snapshotDetail.tracking_topic_name}
                  </span>
                ) : null}
                {snapshotDetail.report_version_title ? (
                  <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">
                    {t("research.compareSnapshotVersion", "关联版本")} · {snapshotDetail.report_version_title}
                  </span>
                ) : null}
                {isLegacyBackfilledSnapshot ? (
                  <span className="rounded-full bg-amber-50 px-2.5 py-1 text-amber-700">
                    旧快照已补冻结
                  </span>
                ) : hasFrozenSnapshotMetadata ? (
                  <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">
                    指标时点已冻结
                  </span>
                ) : null}
              </div>
              {isLegacyBackfilledSnapshot ? (
                <div className="mt-4 rounded-[22px] border border-amber-200 bg-amber-50/80 px-4 py-3 text-sm leading-6 text-amber-800">
                  旧快照已补冻结：该快照原始 metadata 缺失，系统已
                  {snapshotMetadataBackfilledAtLabel ? `于 ${snapshotMetadataBackfilledAtLabel} ` : ""}
                  补写章节证据诊断和离线回归快照；当前页面和导出文件都会固定使用这份补冻结时点。
                </div>
              ) : null}
            </div>
            <div className="flex flex-wrap gap-3">
              <Link href={liveCompareHref} className="af-btn af-btn-secondary border px-4 py-2 text-sm">
                {t("research.compareOpenLive", "查看实时结果")}
              </Link>
              {snapshotDetail.tracking_topic_id ? (
                <Link href={`/research/topics/${snapshotDetail.tracking_topic_id}`} className="af-btn af-btn-secondary border px-4 py-2 text-sm">
                  {t("research.openTopicWorkspace", "专题工作台")}
                </Link>
              ) : null}
            </div>
          </div>
        </section>
      ) : null}

      {snapshotDetail?.linked_report_diff && snapshotDetail.linked_report_diff.status !== "unavailable" ? (
        <section className="af-glass rounded-[30px] p-5">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div className="max-w-3xl">
              <p className="af-kicker">{t("research.compareSnapshotDiffKicker", "Snapshot vs Version")}</p>
              <div className="mt-2 flex flex-wrap items-center gap-2">
                <h3 className="text-xl font-semibold text-slate-900">{snapshotDetail.linked_report_diff.headline}</h3>
                <span className={`rounded-full px-2.5 py-1 text-xs ${diffStatusTone(snapshotDetail.linked_report_diff.status)}`}>
                  {diffStatusLabel(snapshotDetail.linked_report_diff.status, t)}
                </span>
              </div>
              <ul className="mt-4 space-y-2 text-sm leading-6 text-slate-600">
                {snapshotDetail.linked_report_diff.summary_lines.map((line) => (
                  <li key={line} className="flex gap-2">
                    <span className="mt-[7px] h-1.5 w-1.5 rounded-full bg-sky-300" />
                    <span>{line}</span>
                  </li>
                ))}
              </ul>
            </div>
          </div>
          {snapshotDetail.linked_report_diff.axes.length ? (
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {snapshotDetail.linked_report_diff.axes.map((axis) => (
                <article key={axis.key} className="rounded-[22px] border border-white/60 bg-white/70 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="text-sm font-semibold text-slate-900">{axis.label}</p>
                    <span className="rounded-full bg-white/80 px-2.5 py-1 text-xs text-slate-500">
                      {axis.snapshot_count} vs {axis.linked_count}
                    </span>
                  </div>
                  <div className="mt-3 space-y-2 text-xs leading-5 text-slate-500">
                    <p>
                      快照独有: {axis.snapshot_only.length ? axis.snapshot_only.join(" / ") : "无"}
                    </p>
                    <p>
                      关联版本独有: {axis.linked_only.length ? axis.linked_only.join(" / ") : "无"}
                    </p>
                    <p>交集: {axis.overlap_count}</p>
                  </div>
                </article>
              ))}
            </div>
          ) : null}
        </section>
      ) : null}

      <section className="af-glass rounded-[34px] p-5 md:p-7">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="max-w-3xl">
            <p className="af-kicker">{t("research.compareKicker", "Compare Matrix")}</p>
            <h2 className="mt-2 text-3xl font-semibold tracking-[-0.04em] text-slate-900 md:text-[2rem]">
              {t("research.compareTitle", "甲方 / 中标方 / 竞品 / 伙伴 对比矩阵")}
            </h2>
            <p className="mt-3 text-sm leading-6 text-slate-500 md:text-[15px]">
              {t(
                "research.compareDesc",
                "把多份研报里的甲方、中标方、竞品和伙伴线索拉平对比，优先看预算、项目、战略和竞争压力。",
              )}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <button
              type="button"
              onClick={() => void handleSaveSnapshot()}
              disabled={!visibleRows.length || savingSnapshot}
              className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {savingSnapshot
                ? t("research.compareSavingSnapshot", "保存中...")
                : t("research.compareSaveSnapshot", "保存对比快照")}
            </button>
            <button
              type="button"
              onClick={() => void handleArchiveMarkdown()}
              disabled={!visibleRows.length || archivingMarkdown}
              className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {archivingMarkdown
                ? t("research.compareArchiving", "归档中...")
                : t("research.compareArchiveMarkdown", "保存到历史归档")}
            </button>
            <button
              type="button"
              onClick={handleExportMarkdown}
              disabled={!visibleRows.length}
              className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {t("research.compareExport", "导出 Markdown")}
            </button>
            <button
              type="button"
              onClick={handleExportPdf}
              disabled={!visibleRows.length}
              className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {t("research.compareExportPdf", "导出 PDF")}
            </button>
            <button
              type="button"
              onClick={handleExportExecBrief}
              disabled={!visibleRows.length}
              className="af-btn af-btn-secondary border px-4 py-2 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {t("research.compareExportExecBrief", "导出 Exec Brief")}
            </button>
            <Link href="/research" className="af-btn af-btn-secondary border px-4 py-2">
              {t("research.compareBack", "返回商机情报中心")}
            </Link>
          </div>
        </div>
        {isLegacyBackfilledSnapshot ? (
          <div className="mt-5 rounded-[24px] border border-amber-200 bg-amber-50/80 p-4 text-sm leading-6 text-amber-800">
            导出说明 · 旧快照已补冻结。导出 Markdown / PDF / Exec Brief 会在文件头部写入补冻结说明，并沿用补冻结时点的 evidence appendix、section diagnostics 与 offline regression snapshot。
          </div>
        ) : null}
        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {roleStats.map((item) => (
            <div key={item.role} className="rounded-[24px] border border-white/60 bg-white/72 p-4 shadow-[0_14px_32px_rgba(15,23,42,0.06)]">
              <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-400">{item.role}</p>
              <p className="mt-3 text-3xl font-semibold tracking-[-0.05em] text-slate-900">{item.count}</p>
            </div>
          ))}
        </div>

        <div className="mt-5 grid gap-4 xl:grid-cols-[1.05fr,0.95fr]">
          <article className="rounded-[26px] border border-white/70 bg-white/78 p-5 shadow-[0_14px_32px_rgba(15,23,42,0.05)]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-400">Section Diagnostics</p>
                <h3 className="mt-2 text-lg font-semibold text-slate-900">章节证据诊断</h3>
              </div>
              <span className="rounded-full bg-white/80 px-2.5 py-1 text-xs text-slate-500">
                来源研报 · {effectiveSectionDiagnosticsSummary.sourceReportCount}
              </span>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              <div className="rounded-[20px] border border-amber-100 bg-amber-50/80 p-3">
                <p className="text-[11px] uppercase tracking-[0.16em] text-amber-600">待补证章节</p>
                <p className="mt-2 text-2xl font-semibold text-amber-700">{effectiveSectionDiagnosticsSummary.weakSectionCount}</p>
              </div>
              <div className="rounded-[20px] border border-rose-100 bg-rose-50/80 p-3">
                <p className="text-[11px] uppercase tracking-[0.16em] text-rose-600">配额风险</p>
                <p className="mt-2 text-2xl font-semibold text-rose-700">{effectiveSectionDiagnosticsSummary.quotaRiskSectionCount}</p>
              </div>
              <div className="rounded-[20px] border border-slate-200 bg-slate-50/90 p-3">
                <p className="text-[11px] uppercase tracking-[0.16em] text-slate-500">矛盾章节</p>
                <p className="mt-2 text-2xl font-semibold text-slate-900">{effectiveSectionDiagnosticsSummary.contradictionSectionCount}</p>
              </div>
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-600">
              重点章节 · {effectiveSectionDiagnosticsSummary.highlightedSections.length ? effectiveSectionDiagnosticsSummary.highlightedSections.join(" / ") : "当前筛选下没有显著章节风险。"}
            </p>
          </article>

          <article className="rounded-[26px] border border-white/70 bg-white/78 p-5 shadow-[0_14px_32px_rgba(15,23,42,0.05)]">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-[11px] font-medium uppercase tracking-[0.22em] text-slate-400">Offline Regression</p>
                <h3 className="mt-2 text-lg font-semibold text-slate-900">
                  {isLegacyBackfilledSnapshot ? "补冻结离线回归" : hasFrozenSnapshotMetadata ? "快照时点离线回归" : "主库离线回归"}
                </h3>
              </div>
              <span className="rounded-full bg-white/80 px-2.5 py-1 text-xs text-slate-500">
                {effectiveOfflineEvaluation ? `已评估 ${effectiveOfflineEvaluation.evaluated_reports} 份` : "暂未加载"}
              </span>
            </div>
            {effectiveOfflineEvaluation?.metrics?.length ? (
              <>
                <div className="mt-4 flex flex-wrap gap-2">
                  {effectiveOfflineEvaluation.metrics.slice(0, 3).map((metric) => (
                    <span
                      key={metric.key}
                      className={`rounded-full px-2.5 py-1 text-xs font-medium ${offlineStatusTone(metric.status)}`}
                    >
                      {metric.label} {metric.percent}% · {offlineStatusLabel(metric.status)}
                    </span>
                  ))}
                </div>
                <div className="mt-4 space-y-2 text-sm leading-6 text-slate-600">
                  {effectiveOfflineEvaluation.summary_lines.slice(0, 2).map((line) => (
                    <p key={line}>{line}</p>
                  ))}
                </div>
                {effectiveOfflineEvaluation.weakest_reports.length ? (
                  <p className="mt-4 text-sm leading-6 text-slate-600">
                    弱样本 · {effectiveOfflineEvaluation.weakest_reports.slice(0, 3).map((item) => item.report_title || item.entry_title).join(" / ")}
                  </p>
                ) : null}
                <p className="mt-3 text-xs text-slate-500">
                  {isLegacyBackfilledSnapshot
                    ? `旧快照已补冻结；该面板展示补冻结时点的回归快照${
                        snapshotMetadataBackfilledAtLabel ? `（${snapshotMetadataBackfilledAtLabel}）` : ""
                      }。`
                    : hasFrozenSnapshotMetadata
                      ? "该面板优先展示 snapshot 保存时冻结的回归快照。"
                      : "该面板反映的是当前主库离线回归结果；老 snapshot 若未冻结 metadata，仍会读取当前值。"}
                </p>
              </>
            ) : (
              <p className="mt-4 text-sm text-slate-500">当前没有可展示的离线回归结果。</p>
            )}
          </article>
        </div>
      </section>

      <section className="af-glass rounded-[30px] p-5">
        <div className="grid gap-3 md:grid-cols-[minmax(0,1.4fr),repeat(3,minmax(0,0.8fr))]">
          <div className="flex items-center gap-2 rounded-[20px] border border-white/60 bg-white/70 px-3 py-2 shadow-[0_10px_30px_rgba(15,23,42,0.05)]">
            <AppIcon name="search" className="h-4 w-4 text-slate-400" />
            <input
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("research.compareSearchPlaceholder", "搜索公司名、甲方、竞品、伙伴...")}
              className="min-w-0 flex-1 bg-transparent text-sm text-slate-700 outline-none placeholder:text-slate-400"
            />
          </div>
          <select value={roleFilter} onChange={(event) => setRoleFilter(event.target.value as CompareRoleFilter)} className="af-input bg-white/70">
            <option value="all">{t("research.compareRoleAll", "全部角色")}</option>
            <option value="甲方">甲方</option>
            <option value="中标方">中标方</option>
            <option value="竞品">竞品</option>
            <option value="伙伴">伙伴</option>
          </select>
          <select value={regionFilter} onChange={(event) => setRegionFilter(event.target.value)} className="af-input bg-white/70">
            <option value="">{t("research.centerRegionAll", "全部区域")}</option>
            {regionOptions.filter(Boolean).map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
          <select value={industryFilter} onChange={(event) => setIndustryFilter(event.target.value)} className="af-input bg-white/70">
            <option value="">{t("research.centerIndustryAll", "全部行业")}</option>
            {industryOptions.filter(Boolean).map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
        {statusNotice ? (
          <p className={`mt-3 text-sm ${statusTone === "error" ? "text-rose-600" : "text-emerald-700"}`}>{statusNotice}</p>
        ) : null}
        {snapshotError ? (
          <p className="mt-3 text-sm text-rose-600">{snapshotError}</p>
        ) : null}
      </section>

      {loading ? (
        <section className="af-glass rounded-[30px] p-5 text-sm text-slate-500">{t("common.loading", "加载中")}</section>
      ) : null}

      {!loading && visibleRows.length === 0 ? (
        <section className="af-glass rounded-[30px] p-5 text-sm text-slate-500">
          {t("research.compareEmpty", "当前没有可用于对比的实体线索。")}
        </section>
      ) : null}

      {!loading && visibleRows.length ? (
        <section className="space-y-3">
          {visibleRows.map((row) => (
            <article
              key={row.id}
              className="af-glass rounded-[28px] p-5 transition duration-200 hover:-translate-y-0.5 hover:shadow-[0_20px_45px_rgba(15,23,42,0.08)]"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="rounded-full bg-slate-900 px-2.5 py-1 text-[11px] font-semibold text-white/90">
                      {row.role}
                    </span>
                    {row.region ? <span className="rounded-full bg-white/70 px-2.5 py-1 text-[11px] text-slate-500">{row.region}</span> : null}
                    {row.industry ? <span className="rounded-full bg-white/70 px-2.5 py-1 text-[11px] text-slate-500">{row.industry}</span> : null}
                  </div>
                  <h3 className="mt-3 text-xl font-semibold tracking-[-0.03em] text-slate-900">{row.name}</h3>
                  <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-600">{row.clue}</p>
                </div>
                <Link href={`/knowledge/${row.sourceEntryId}`} className="af-btn af-btn-secondary border px-3 py-1.5 text-sm">
                  {t("research.compareOpenSource", "打开来源研报")}
                </Link>
              </div>
              <div className="mt-4 grid gap-3 lg:grid-cols-4">
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{t("research.compareBudget", "预算信号")}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{row.budgetSignal}</p>
                  <p className="mt-3 text-xs text-slate-500">
                    {t("research.compareBudgetRange", "预算区间")} · {row.budgetRange}
                  </p>
                </div>
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{t("research.compareProject", "项目/招采")}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{row.projectSignal}</p>
                </div>
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{t("research.compareStrategy", "战略/讲话")}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{row.strategySignal}</p>
                </div>
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{t("research.compareCompetition", "竞合压力")}</p>
                  <p className="mt-2 text-sm leading-6 text-slate-700">{row.competitionSignal}</p>
                </div>
              </div>
              <div className="mt-4 grid gap-3 xl:grid-cols-5">
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    {t("research.compareDepartments", "高概率决策部门")}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {row.targetDepartments.length ? (
                      row.targetDepartments.map((item) => (
                        <span key={item} className="rounded-full bg-white/75 px-3 py-1.5 text-xs text-slate-600">
                          {item}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">{t("research.compareNoDepartments", "暂无明确部门线索")}</span>
                    )}
                  </div>
                </div>
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    {t("research.compareContacts", "公开业务联系方式")}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {row.publicContacts.length ? (
                      row.publicContacts.map((item) => (
                        <span key={item} className="rounded-full bg-white/75 px-3 py-1.5 text-xs text-slate-600">
                          {item}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">{t("research.compareNoContacts", "暂无公开联系方式")}</span>
                    )}
                  </div>
                  {row.candidateProfileCompanies.length || row.candidateProfileHitCount > 0 ? (
                    <div className="mt-3 flex flex-wrap gap-2">
                      {row.candidateProfileCompanies.length ? (
                        <span className="rounded-full bg-sky-50 px-3 py-1.5 text-xs text-sky-700">
                          候选补证公司 {row.candidateProfileCompanies.length}
                        </span>
                      ) : null}
                      {row.candidateProfileHitCount > 0 ? (
                        <span className="rounded-full bg-sky-50 px-3 py-1.5 text-xs text-sky-700">
                          补证公开源 {row.candidateProfileHitCount}
                        </span>
                      ) : null}
                      {row.candidateProfileOfficialHitCount > 0 ? (
                        <span className="rounded-full bg-cyan-50 px-3 py-1.5 text-xs text-cyan-700">
                          其中官方源 {row.candidateProfileOfficialHitCount}
                        </span>
                      ) : null}
                      {row.candidateProfileCompanies.map((item) => (
                        <span key={`candidate-${row.id}-${item}`} className="rounded-full bg-sky-50 px-3 py-1.5 text-xs text-sky-700">
                          候选公司 · {item}
                        </span>
                      ))}
                    </div>
                  ) : null}
                </div>
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    {t("research.compareCompetitorSet", "竞品公司")}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {row.competitorHighlights.length ? (
                      row.competitorHighlights.map((item) => (
                        <span key={item} className="rounded-full bg-white/75 px-3 py-1.5 text-xs text-slate-600">
                          {item}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">{t("research.compareNoCompetitors", "暂无明确竞品线索")}</span>
                    )}
                  </div>
                </div>
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    {t("research.comparePartnerSet", "生态伙伴")}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {row.partnerHighlights.length ? (
                      row.partnerHighlights.map((item) => (
                        <span key={item} className="rounded-full bg-white/75 px-3 py-1.5 text-xs text-slate-600">
                          {item}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">{t("research.compareNoPartners", "暂无明确伙伴线索")}</span>
                    )}
                  </div>
                </div>
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    {t("research.compareBenchmarks", "标杆案例")}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {row.benchmarkCases.length ? (
                      row.benchmarkCases.map((item) => (
                        <span key={item} className="rounded-full bg-white/75 px-3 py-1.5 text-xs text-slate-600">
                          {item}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">{t("research.compareNoBenchmarks", "暂无明确标杆案例")}</span>
                    )}
                  </div>
                </div>
              </div>
              <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr),minmax(0,1.1fr)]">
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    {t("research.compareBenchmarks", "标杆案例证据摘要")}
                  </p>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {row.benchmarkCases.length ? (
                      row.benchmarkCases.map((item) => (
                        <span key={item} className="rounded-full bg-white/75 px-3 py-1.5 text-xs text-slate-600">
                          {item}
                        </span>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">{t("research.compareNoBenchmarks", "暂无明确标杆案例")}</span>
                    )}
                  </div>
                </div>
                <div className="rounded-[20px] border border-white/60 bg-white/65 p-4">
                  <p className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                    {t("research.compareEvidence", "证据链接")}
                  </p>
                  <div className="mt-3 space-y-2">
                    {row.evidenceLinks.length ? (
                      row.evidenceLinks.map((item) => (
                        <div
                          key={item.url}
                          className="rounded-[16px] border border-white/60 bg-white/70 px-3 py-2 text-sm text-slate-700 transition hover:bg-white"
                        >
                          <div className="flex items-start justify-between gap-3">
                            <div className="min-w-0">
                              <a
                                href={normalizeExternalUrl(item.url)}
                                target="_blank"
                                rel="noreferrer"
                                className="line-clamp-1 block underline-offset-4 hover:text-sky-700 hover:underline"
                              >
                                {item.title}
                              </a>
                              <div className="mt-1 flex flex-wrap gap-2">
                                <span className="rounded-full bg-sky-50 px-2 py-0.5 text-[10px] font-medium text-sky-700">
                                  {sourceTierLabel(item.sourceTier, t)}
                                </span>
                                {item.sourceLabel ? (
                                  <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">
                                    {item.sourceLabel}
                                  </span>
                                ) : null}
                                {row.candidateProfileSourceLabels.map((label) => (
                                  <span key={`${item.url}-${label}`} className="rounded-full bg-cyan-50 px-2 py-0.5 text-[10px] text-cyan-700">
                                    {label}
                                  </span>
                                ))}
                              </div>
                            </div>
                            <AppIcon name="external" className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
                          </div>
                          <ExternalLinkActions url={item.url} className="mt-2" openLabel={t("research.openEvidenceLink", "网页打开")} />
                        </div>
                      ))
                    ) : (
                      <span className="text-sm text-slate-500">{t("research.compareNoEvidence", "暂无可直接打开的证据链接")}</span>
                    )}
                  </div>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-3 text-xs text-slate-500">
                <span>{t("research.compareKeyword", "关键词")} · {row.keyword || "—"}</span>
                <span>{t("research.compareSourceCount", "来源数")} · {row.sourceCount || 0}</span>
                <span>{t("research.compareUpdated", "更新")} · {new Date(row.updatedAt).toLocaleDateString()}</span>
              </div>
            </article>
          ))}
        </section>
      ) : null}
    </div>
  );
}
