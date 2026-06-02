"use client";

import { useEffect, useMemo, useState } from "react";
import {
  type ApiResearchNormalizedEntity,
  createResearchMarkdownArchive,
  createResearchActionPlan,
  getResearchOfflineEvaluation,
  getResearchTrackingTopicTimeline,
  getResearchTrackingTopicVersions,
  getResearchWorkspace,
  saveResearchActionCards,
  type ApiResearchOfflineEvaluation,
  type ApiResearchTrackingTopicTimelineEvent,
  type ApiResearchTrackingTopic,
  type ApiResearchTrackingTopicVersionDetail,
} from "@/lib/api";
import {
  buildResearchTopicRecapExecBrief,
  buildResearchTopicRecapExecBriefFilename,
  buildResearchTopicRecapExportFilename,
  buildResearchTopicRecapMarkdown,
  buildResearchTopicRecapPdfFilename,
  buildResearchTopicRecapPlainText,
  summarizeResearchTopicRecapEvidence,
  summarizeResearchTopicFollowupImpacts,
  summarizeResearchTopicSectionDiagnostics,
} from "@/lib/research-topic-recap";
import { buildSimplePdfFromText, triggerFileDownload } from "@/lib/research-delivery-export";
import {
  buildAddedRows,
  buildCandidateProfileSummary,
  buildEvidenceLinks,
  buildFollowupImpactPanel,
  buildRankedScorePanels,
  buildRemovedRows,
  buildRewrittenRows,
  buildSourceContributionPanels,
  buildVersionFocusBlocks,
  normalizeList,
  qualityLabel,
  type ResearchFieldDiffRow,
} from "@/components/research/research-topic-workspace-utils";

type TranslationFn = (key: string, fallback: string) => string;

export function useResearchTopicWorkspaceController({
  topicId,
  t,
}: {
  topicId: string;
  t: TranslationFn;
}) {
  const [topic, setTopic] = useState<ApiResearchTrackingTopic | null>(null);
  const [versions, setVersions] = useState<ApiResearchTrackingTopicVersionDetail[]>([]);
  const [timelineEvents, setTimelineEvents] = useState<ApiResearchTrackingTopicTimelineEvent[]>([]);
  const [offlineEvaluation, setOfflineEvaluation] = useState<ApiResearchOfflineEvaluation | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [planningActions, setPlanningActions] = useState(false);
  const [savingActions, setSavingActions] = useState(false);
  const [savingArchive, setSavingArchive] = useState(false);
  const [actionMessage, setActionMessage] = useState("");
  const [timelineMessage, setTimelineMessage] = useState("");
  const [compareLeftId, setCompareLeftId] = useState("");
  const [compareRightId, setCompareRightId] = useState("");
  const [selectedEntityKey, setSelectedEntityKey] = useState("");

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
    let active = true;
    setLoading(true);
    setError("");
    getResearchWorkspace()
      .then(async (workspace) => {
        if (!active) return;
        const found = (workspace.tracking_topics || []).find((item) => item.id === topicId) || null;
        if (!found) {
          setTopic(null);
          setVersions([]);
          setTimelineEvents([]);
          setError(t("research.topicNotFound", "未找到对应长期专题"));
          setLoading(false);
          return;
        }
        setTopic(found);
        const [detailedVersions, timeline] = await Promise.all([
          getResearchTrackingTopicVersions(topicId),
          getResearchTrackingTopicTimeline(topicId),
        ]);
        if (!active) return;
        setVersions(detailedVersions);
        setTimelineEvents(timeline);
        setLoading(false);
      })
      .catch(() => {
        if (!active) return;
        setTimelineEvents([]);
        setError(t("research.topicLoadFailed", "专题工作台加载失败，请稍后重试"));
        setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [topicId, t]);

  const latest = versions[0] || null;
  const previous = versions[1] || null;
  const latestReport = latest?.report || null;
  const latestEntityGroups = useMemo(
    () => [
      {
        key: "target",
        title: "甲方实体",
        items: latestReport?.entity_graph?.target_entities || [],
      },
      {
        key: "competitor",
        title: "竞品实体",
        items: latestReport?.entity_graph?.competitor_entities || [],
      },
      {
        key: "partner",
        title: "伙伴实体",
        items: latestReport?.entity_graph?.partner_entities || [],
      },
    ].filter((group) => group.items.length),
    [latestReport],
  );
  const selectedEntity = useMemo<ApiResearchNormalizedEntity | null>(() => {
    const pool = latestEntityGroups.flatMap((group) => group.items);
    if (!pool.length) return null;
    if (!selectedEntityKey) return pool[0] || null;
    return pool.find((item) => item.canonical_name === selectedEntityKey) || pool[0] || null;
  }, [latestEntityGroups, selectedEntityKey]);

  useEffect(() => {
    if (!versions.length) {
      setCompareLeftId("");
      setCompareRightId("");
      return;
    }
    const validIds = new Set(versions.map((item) => item.id));
    if (!compareRightId || !validIds.has(compareRightId)) {
      setCompareRightId(versions[0]?.id || "");
    }
    if (!compareLeftId || !validIds.has(compareLeftId) || compareLeftId === (versions[0]?.id || "")) {
      setCompareLeftId(versions[1]?.id || versions[0]?.id || "");
    }
  }, [versions, compareLeftId, compareRightId]);

  const compareLeftVersion = versions.find((item) => item.id === compareLeftId) || previous || latest;
  const compareRightVersion = versions.find((item) => item.id === compareRightId) || latest || previous;
  const compareLeftReport = compareLeftVersion?.report || null;
  const compareRightReport = compareRightVersion?.report || null;
  const timelineStats = useMemo(
    () => ({
      versionCount: timelineEvents.filter((item) => item.event_type === "report_version").length,
      snapshotCount: timelineEvents.filter((item) => item.event_type === "compare_snapshot").length,
      archiveCount: timelineEvents.filter((item) => item.event_type === "markdown_archive").length,
    }),
    [timelineEvents],
  );

  const compareSummary = useMemo(() => {
    if (!compareLeftVersion || !compareRightVersion) return [];
    const rows: string[] = [];
    const sourceDelta = compareRightVersion.source_count - compareLeftVersion.source_count;
    if (sourceDelta !== 0) {
      rows.push(`${t("research.centerCardSources", "来源数")} ${sourceDelta > 0 ? "+" : ""}${sourceDelta}`);
    }
    if (compareRightVersion.evidence_density !== compareLeftVersion.evidence_density) {
      rows.push(
        `${t("research.centerEvidenceDensity", "证据密度")} ${qualityLabel(compareLeftVersion.evidence_density)} → ${qualityLabel(compareRightVersion.evidence_density)}`,
      );
    }
    if (compareRightVersion.source_quality !== compareLeftVersion.source_quality) {
      rows.push(
        `${t("research.centerSourceQuality", "来源质量")} ${qualityLabel(compareLeftVersion.source_quality)} → ${qualityLabel(compareRightVersion.source_quality)}`,
      );
    }
    return rows;
  }, [compareLeftVersion, compareRightVersion, t]);

  const diffHighlights = useMemo(() => {
    if (!compareRightReport) {
      return [];
    }
    const rows = [
      {
        title: t("research.diffNewAccounts", "新增甲方"),
        items: buildAddedRows(compareRightReport.target_accounts, compareLeftReport?.target_accounts || []),
      },
      {
        title: t("research.diffNewCompetitors", "新增竞品"),
        items: buildAddedRows(compareRightReport.competitor_profiles, compareLeftReport?.competitor_profiles || []),
      },
      {
        title: t("research.diffNewBudgetSignals", "新增预算线索"),
        items: buildAddedRows(compareRightReport.budget_signals, compareLeftReport?.budget_signals || []),
      },
    ].filter((row) => row.items.length);
    if (rows.length) {
      return rows;
    }
    if (!compareLeftReport) {
      return [
        {
          title: t("research.diffCurrentFocus", "当前重点线索"),
          items: [
            ...(compareRightReport.target_accounts || []).slice(0, 1),
            ...(compareRightReport.competitor_profiles || []).slice(0, 1),
            ...(compareRightReport.budget_signals || []).slice(0, 1),
          ].filter(Boolean),
        },
      ].filter((row) => row.items.length);
    }
    return [];
  }, [compareLeftReport, compareRightReport, t]);

  const fieldDiffRows = useMemo<ResearchFieldDiffRow[]>(() => {
    if (!compareRightReport) return [];
    const fieldConfigs = [
      { key: "target_accounts", title: t("research.diffFieldAccounts", "甲方") },
      { key: "budget_signals", title: t("research.diffFieldBudget", "预算线索") },
      { key: "project_distribution", title: t("research.diffFieldProjects", "项目分布") },
      { key: "strategic_directions", title: t("research.diffFieldStrategy", "战略方向") },
      { key: "tender_timeline", title: t("research.diffFieldTender", "招标节奏") },
      { key: "competitor_profiles", title: t("research.diffFieldCompetitors", "竞品") },
      { key: "ecosystem_partners", title: t("research.diffFieldPartners", "生态伙伴") },
      { key: "client_peer_moves", title: t("research.diffFieldClientPeers", "甲方同行") },
      { key: "winner_peer_moves", title: t("research.diffFieldWinnerPeers", "中标方同行") },
      { key: "benchmark_cases", title: t("research.diffFieldBenchmarks", "标杆案例") },
    ] as const;
    return fieldConfigs
      .map((config) => {
        const baseline = normalizeList(
          ((compareLeftReport as unknown as Record<string, string[] | undefined> | null)?.[config.key] as string[] | undefined) || [],
        );
        const current = normalizeList(
          ((compareRightReport as unknown as Record<string, string[] | undefined>)[config.key] as string[] | undefined) || [],
        );
        return {
          key: config.key,
          title: config.title,
          baseline,
          current,
          added: buildAddedRows(current, baseline),
          removed: buildRemovedRows(current, baseline),
          rewritten: buildRewrittenRows(current, baseline),
          baselineEvidenceLinks: buildEvidenceLinks(
            [...baseline.slice(0, 4), ...buildRemovedRows(current, baseline), ...buildRewrittenRows(current, baseline)].slice(0, 6),
            compareLeftReport,
            t,
          ),
          currentEvidenceLinks: buildEvidenceLinks(
            [...current.slice(0, 4), ...buildAddedRows(current, baseline), ...buildRewrittenRows(current, baseline)].slice(0, 6),
            compareRightReport,
            t,
          ),
        };
      })
      .filter((row) => row.baseline.length || row.current.length);
  }, [compareLeftReport, compareRightReport, t]);

  const compareFocusBlocks = useMemo(
    () => ({
      left: buildVersionFocusBlocks(compareLeftReport),
      right: buildVersionFocusBlocks(compareRightReport),
    }),
    [compareLeftReport, compareRightReport],
  );

  const scorePanels = useMemo(
    () => buildRankedScorePanels(compareLeftReport, compareRightReport, t),
    [compareLeftReport, compareRightReport, t],
  );

  const sourceContributionPanels = useMemo(
    () => buildSourceContributionPanels(compareLeftReport, compareRightReport, t),
    [compareLeftReport, compareRightReport, t],
  );
  const latestCandidateProfileSummary = useMemo(() => buildCandidateProfileSummary(latestReport), [latestReport]);
  const compareLeftCandidateProfileSummary = useMemo(() => buildCandidateProfileSummary(compareLeftReport), [compareLeftReport]);
  const compareRightCandidateProfileSummary = useMemo(() => buildCandidateProfileSummary(compareRightReport), [compareRightReport]);
  const compareLeftFollowupImpactPanel = useMemo(() => buildFollowupImpactPanel(compareLeftReport), [compareLeftReport]);
  const compareRightFollowupImpactPanel = useMemo(() => buildFollowupImpactPanel(compareRightReport), [compareRightReport]);

  const buildVersionRecapBundle = (generatedAt: Date) => {
    if (!topic) {
      return null;
    }
    const sectionDiagnosticsSummary = summarizeResearchTopicSectionDiagnostics(compareLeftVersion, compareRightVersion);
    const followupImpactSummary = summarizeResearchTopicFollowupImpacts(compareLeftVersion, compareRightVersion);
    const exportOptions = {
      topic,
      baselineVersion: compareLeftVersion,
      currentVersion: compareRightVersion,
      compareSummary,
      diffHighlights,
      fieldDiffRows,
      scorePanels,
      sourceContributionPanels,
      timelineEvents,
      generatedAt,
      offlineEvaluation,
    };
    return {
      markdownFilename: buildResearchTopicRecapExportFilename(topic.name, generatedAt),
      pdfFilename: buildResearchTopicRecapPdfFilename(topic.name, generatedAt),
      execBriefFilename: buildResearchTopicRecapExecBriefFilename(topic.name, generatedAt),
      markdown: buildResearchTopicRecapMarkdown(exportOptions),
      plainText: buildResearchTopicRecapPlainText(exportOptions),
      execBrief: buildResearchTopicRecapExecBrief(exportOptions),
      evidenceSummary: summarizeResearchTopicRecapEvidence(fieldDiffRows),
      sectionDiagnosticsSummary,
      followupImpactSummary,
      offlineEvaluationSnapshot: offlineEvaluation,
    };
  };

  const handleRegenerateActions = async (asFocusReference = false) => {
    if (!latestReport || !topic) return;
    setPlanningActions(true);
    setSavingActions(true);
    setActionMessage("");
    try {
      const plan = await createResearchActionPlan({ report: latestReport });
      const saved = await saveResearchActionCards({
        keyword: latestReport.keyword,
        cards: plan.cards,
        collection_name: `${topic.name} 行动卡`,
        is_focus_reference: asFocusReference,
      });
      setActionMessage(
        asFocusReference
          ? t("research.topicActionsSavedToFocus", "已重新生成行动卡并加入 Focus 参考")
          : t("research.topicActionsSaved", `已重新生成并保存 ${saved.created_count} 张行动卡`),
      );
    } catch {
      setActionMessage(t("research.topicActionsFailed", "重新生成行动卡失败，请稍后重试"));
    } finally {
      setPlanningActions(false);
      setSavingActions(false);
    }
  };

  const handleExportVersionRecap = () => {
    if (!topic) return;
    const generatedAt = new Date();
    const bundle = buildVersionRecapBundle(generatedAt);
    if (!bundle) return;
    triggerFileDownload(bundle.markdownFilename, bundle.markdown, "text/markdown;charset=utf-8");
    setActionMessage(t("research.topicVersionRecapExported", "版本复盘 Markdown 已导出"));
  };

  const handleExportVersionRecapPdf = () => {
    const generatedAt = new Date();
    const bundle = buildVersionRecapBundle(generatedAt);
    if (!bundle) return;
    triggerFileDownload(bundle.pdfFilename, buildSimplePdfFromText(bundle.plainText), "application/pdf");
    setActionMessage(t("research.topicVersionRecapPdfExported", "版本复盘 PDF 已导出"));
  };

  const handleExportVersionRecapExecBrief = () => {
    const generatedAt = new Date();
    const bundle = buildVersionRecapBundle(generatedAt);
    if (!bundle) return;
    triggerFileDownload(bundle.execBriefFilename, bundle.execBrief, "text/markdown;charset=utf-8");
    setActionMessage(t("research.topicVersionRecapExecBriefExported", "Topic Exec Brief 已导出"));
  };

  const handleSaveVersionRecapArchive = async () => {
    if (!topic) return;
    const generatedAt = new Date();
    const bundle = buildVersionRecapBundle(generatedAt);
    if (!bundle) return;
    const defaultName = `${topic.name} · 版本复盘归档`;
    const name = window.prompt(
      t("research.topicArchivePrompt", "输入一个复盘归档名称，便于在商机情报中心回看"),
      defaultName,
    )?.trim();
    if (!name) return;
    const summary =
      compareSummary[0] ||
      diffHighlights[0]?.items?.[0] ||
      `${compareLeftVersion?.title || "基线版本"} vs ${compareRightVersion?.title || "对照版本"}`;
    setSavingArchive(true);
    try {
      const saved = await createResearchMarkdownArchive({
        archive_kind: "topic_version_recap",
        name,
        filename: bundle.markdownFilename,
        query: topic.keyword,
        region_filter: topic.region_filter,
        industry_filter: topic.industry_filter,
        tracking_topic_id: topic.id,
        report_version_id: compareRightVersion?.id || undefined,
        summary,
        content: bundle.markdown,
        metadata_payload: {
          baseline_version_id: compareLeftVersion?.id || "",
          baseline_version_title: compareLeftVersion?.title || "",
          current_version_id: compareRightVersion?.id || "",
          current_version_title: compareRightVersion?.title || "",
          evidence_appendix_summary: bundle.evidenceSummary,
          section_diagnostics_summary: bundle.sectionDiagnosticsSummary,
          followup_impact_summary: bundle.followupImpactSummary,
          offline_evaluation_snapshot: bundle.offlineEvaluationSnapshot || {},
        },
      });
      setActionMessage(t("research.topicArchiveSaved", `已保存 Markdown 归档：${saved.name}`));
    } catch {
      setActionMessage(t("research.topicArchiveSaveFailed", "保存 Markdown 归档失败，请稍后重试"));
    } finally {
      setSavingArchive(false);
    }
  };


  return {
    topic,
    versions,
    timelineEvents,
    offlineEvaluation,
    loading,
    error,
    planningActions,
    savingActions,
    savingArchive,
    actionMessage,
    timelineMessage,
    setTimelineMessage,
    compareLeftId,
    setCompareLeftId,
    compareRightId,
    setCompareRightId,
    selectedEntityKey,
    setSelectedEntityKey,
    latest,
    previous,
    latestReport,
    latestEntityGroups,
    selectedEntity,
    compareLeftVersion,
    compareRightVersion,
    compareLeftReport,
    compareRightReport,
    timelineStats,
    compareSummary,
    diffHighlights,
    fieldDiffRows,
    compareFocusBlocks,
    scorePanels,
    sourceContributionPanels,
    latestCandidateProfileSummary,
    compareLeftCandidateProfileSummary,
    compareRightCandidateProfileSummary,
    compareLeftFollowupImpactPanel,
    compareRightFollowupImpactPanel,
    handleRegenerateActions,
    handleExportVersionRecap,
    handleExportVersionRecapPdf,
    handleExportVersionRecapExecBrief,
    handleSaveVersionRecapArchive,
  };
}
