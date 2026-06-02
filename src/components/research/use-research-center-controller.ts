"use client";

import { useState } from "react";
import type { ResearchPerspective } from "@/lib/research-facets";
import {
  buildMarkdownArchiveHref,
  buildTopicWorkspaceHref,
  type ResearchFilter,
  type ResearchRetrievalLens,
} from "@/components/research/research-center-utils";
import { useResearchCenterArchiveController } from "@/components/research/use-research-center-archive-controller";
import { useResearchCenterCardsController } from "@/components/research/use-research-center-cards-controller";
import { useResearchCenterDailyBriefController } from "@/components/research/use-research-center-daily-brief-controller";
import { useResearchCenterExperimentController } from "@/components/research/use-research-center-experiment-controller";
import { useResearchCenterLowQualityController } from "@/components/research/use-research-center-low-quality-controller";
import { useResearchCenterSourceSettingsController } from "@/components/research/use-research-center-source-settings-controller";
import { useResearchCenterViewModel } from "@/components/research/use-research-center-view-model";
import { useResearchCenterWatchlistController } from "@/components/research/use-research-center-watchlist-controller";
import { useResearchCenterWorkspaceController } from "@/components/research/use-research-center-workspace-controller";

type TranslationFn = (key: string, fallback: string) => string;

export function useResearchCenterController({ t }: { t: TranslationFn }) {
  const [filter, setFilter] = useState<ResearchFilter>("all");
  const [retrievalLens, setRetrievalLens] = useState<ResearchRetrievalLens>("all");
  const [perspective, setPerspective] = useState<ResearchPerspective>("all");
  const [focusOnly, setFocusOnly] = useState(false);
  const [queryDraft, setQueryDraft] = useState("");
  const [query, setQuery] = useState("");
  const [regionFilter, setRegionFilter] = useState("");
  const [industryFilter, setIndustryFilter] = useState("");
  const [actionTypeFilter, setActionTypeFilter] = useState("");

  const sourceSettingsController = useResearchCenterSourceSettingsController();
  const dailyBriefController = useResearchCenterDailyBriefController();
  const cardsController = useResearchCenterCardsController({
    t,
    focusOnly,
    query,
  });
  const experimentController = useResearchCenterExperimentController();
  const lowQualityController = useResearchCenterLowQualityController({
    refreshResearchCards: cardsController.refreshResearchCards,
    refreshOfflineEvaluation: experimentController.refreshOfflineEvaluation,
    refreshControlPlaneDiagnostics: experimentController.refreshControlPlaneDiagnostics,
  });

  const { reports, actions, loading, error } = cardsController;

  const viewModel = useResearchCenterViewModel({
    t,
    reports,
    actions,
    filter,
    retrievalLens,
    perspective,
    focusOnly,
    query,
    regionFilter,
    industryFilter,
    actionTypeFilter,
  });
  const {
    activeFilterLabels,
    activePerspective,
    actionTypeOptions,
    filterMeta,
    industryOptions,
    overviewStats,
    perspectiveMeta,
    regionOptions,
    retrievalLensMeta,
    visibleItems,
  } = viewModel;

  const workspaceController = useResearchCenterWorkspaceController({
    t,
    query,
    filter,
    perspective,
    regionFilter,
    industryFilter,
    actionTypeFilter,
    focusOnly,
    activePerspectiveLabel: activePerspective.label,
    activeFilterLabels,
    visibleItems,
    reports,
    actions,
    setFilter,
    setPerspective,
    setRegionFilter,
    setIndustryFilter,
    setActionTypeFilter,
    setFocusOnly,
    setQuery,
    setQueryDraft,
  });

  const archiveController = useResearchCenterArchiveController({
    t,
    markdownArchives: workspaceController.markdownArchives,
    onMarkdownArchiveDeleted: workspaceController.removeMarkdownArchive,
    onAfterMarkdownArchiveDeleted: experimentController.refreshControlPlaneDiagnostics,
  });

  const watchlistController = useResearchCenterWatchlistController({
    refreshWorkspace: workspaceController.refreshWorkspace,
  });

  const handleSearchSubmit = () => {
    setQuery(queryDraft.trim());
  };

  const clearFacetFilters = () => {
    setRegionFilter("");
    setIndustryFilter("");
    setActionTypeFilter("");
    setFocusOnly(false);
    setQuery("");
    setQueryDraft("");
    setPerspective("all");
    setRetrievalLens("all");
  };

  const buildCompareHref = (overrides?: {
    query?: string;
    region?: string;
    industry?: string;
    topicId?: string;
  }) => {
    const params = new URLSearchParams();
    const compareQuery = (overrides?.query ?? query).trim();
    const compareRegion = overrides?.region ?? regionFilter;
    const compareIndustry = overrides?.industry ?? industryFilter;
    const compareTopicId = overrides?.topicId || "";
    if (compareQuery) params.set("query", compareQuery);
    if (compareRegion) params.set("region", compareRegion);
    if (compareIndustry) params.set("industry", compareIndustry);
    if (compareTopicId) params.set("topicId", compareTopicId);
    const queryString = params.toString();
    return queryString ? `/research/compare?${queryString}` : "/research/compare";
  };

  const buildCompareSnapshotHref = (snapshotId: string) =>
    `/research/compare?snapshot=${encodeURIComponent(snapshotId)}`;

  return {
    heroProps: {
      compareHref: buildCompareHref(),
      enabledSourceCount: sourceSettingsController.sourceSettings?.enabled_source_labels?.length || 0,
      overviewStats,
    },
    consolePanelProps: {
      trackingTopics: workspaceController.trackingTopics.map((item) => ({
        id: item.id,
        name: item.name,
        keyword: item.keyword,
      })),
    },
    sourceSettingsSectionProps: {
      t,
      sourceSettings: sourceSettingsController.sourceSettings,
      sourceSaving: sourceSettingsController.sourceSaving,
      sourceError: sourceSettingsController.sourceError,
      toggleResearchSource: sourceSettingsController.toggleResearchSource,
    },
    experimentControlSectionProps: {
      t,
      ...experimentController,
    },
    sidebarControlsProps: {
      t,
      dailyBrief: dailyBriefController.dailyBrief,
      dailyBriefLoading: dailyBriefController.dailyBriefLoading,
      dailyBriefRefreshing: dailyBriefController.dailyBriefRefreshing,
      dailyBriefError: dailyBriefController.dailyBriefError,
      filter,
      setFilter,
      filterMeta,
      queryDraft,
      setQueryDraft,
      focusOnly,
      setFocusOnly,
      retrievalLens,
      setRetrievalLens,
      retrievalLensMeta,
      perspective,
      setPerspective,
      perspectiveMeta,
      activePerspective,
      regionFilter,
      setRegionFilter,
      regionOptions,
      industryFilter,
      setIndustryFilter,
      industryOptions,
      actionTypeFilter,
      setActionTypeFilter,
      actionTypeOptions,
      visibleItems,
      handleRefreshDailyBrief: dailyBriefController.handleRefreshDailyBrief,
      handleSearchSubmit,
      clearFacetFilters,
    },
    markdownArchivesSectionProps: {
      archiveDeliveryFilter: archiveController.archiveDeliveryFilter,
      archiveFilterMeta: archiveController.archiveFilterMeta,
      archiveLinkMessage: archiveController.archiveLinkMessage,
      archiveSortMeta: archiveController.archiveSortMeta,
      archiveSortMode: archiveController.archiveSortMode,
      buildCompareSnapshotHref,
      buildMarkdownArchiveHref,
      buildTopicWorkspaceHref,
      onArchiveDeliveryFilterChange: archiveController.setArchiveDeliveryFilter,
      onArchiveLinkMessage: archiveController.setArchiveLinkMessage,
      onArchiveSortModeChange: archiveController.setArchiveSortMode,
      onDeleteMarkdownArchive: archiveController.handleDeleteMarkdownArchive,
      onDownloadMarkdownArchive: archiveController.handleDownloadMarkdownArchive,
      t,
      visibleMarkdownArchives: archiveController.visibleMarkdownArchives,
      workspaceSaving: workspaceController.workspaceSaving || archiveController.archiveSaving,
    },
    workspaceSectionsProps: {
      t,
      compareSnapshots: workspaceController.compareSnapshots,
      savedViews: workspaceController.savedViews,
      trackingTopics: workspaceController.trackingTopics,
      workspaceSaving: workspaceController.workspaceSaving,
      refreshingTopicId: workspaceController.refreshingTopicId,
      buildCompareHref,
      buildCompareSnapshotHref,
      handleDeleteCompareSnapshot: workspaceController.handleDeleteCompareSnapshot,
      handleSaveCurrentView: workspaceController.handleSaveCurrentView,
      handleDeleteSavedView: workspaceController.handleDeleteSavedView,
      applySavedView: workspaceController.applySavedView,
      handleSaveTrackingTopic: workspaceController.handleSaveTrackingTopic,
      handleDeleteTrackingTopic: workspaceController.handleDeleteTrackingTopic,
      handleRefreshTrackingTopic: workspaceController.handleRefreshTrackingTopic,
      applyTrackingTopic: workspaceController.applyTrackingTopic,
      handleCreateWatchlist: watchlistController.handleCreateWatchlist,
    },
    lowQualityReviewSectionProps: {
      t,
      lowQualityQueue: lowQualityController.lowQualityQueue,
      lowQualityLoading: lowQualityController.lowQualityLoading,
      lowQualityActionKey: lowQualityController.lowQualityActionKey,
      lowQualityMessage: lowQualityController.lowQualityMessage,
      lowQualityError: lowQualityController.lowQualityError,
      handleRewriteLowQualityItem: lowQualityController.handleRewriteLowQualityItem,
      handleResolveLowQualityItem: lowQualityController.handleResolveLowQualityItem,
    },
    watchlistSectionProps: {
      t,
      watchlists: watchlistController.watchlists,
      watchlistAutomation: watchlistController.watchlistAutomation,
      watchlistOpsSummary: watchlistController.watchlistOpsSummary,
      watchlistDigestExport: watchlistController.watchlistDigestExport,
      watchlistMessage: watchlistController.watchlistMessage,
      watchlistError: watchlistController.watchlistError,
      lastRunDueResult: watchlistController.lastRunDueResult,
      watchlistRunHistory: watchlistController.watchlistRunHistory,
      runningDueWatchlists: watchlistController.runningDueWatchlists,
      watchlistActionKey: watchlistController.watchlistActionKey,
      refreshingWatchlistId: watchlistController.refreshingWatchlistId,
      handleDownloadWatchlistDigest: watchlistController.handleDownloadWatchlistDigest,
      handleRunDueWatchlists: watchlistController.handleRunDueWatchlists,
      copyWatchlistOpsText: watchlistController.copyWatchlistOpsText,
      handleUpdateWatchlistSchedule: watchlistController.handleUpdateWatchlistSchedule,
      handleToggleWatchlistStatus: watchlistController.handleToggleWatchlistStatus,
      handleRefreshWatchlist: watchlistController.handleRefreshWatchlist,
    },
    resultsSectionProps: {
      t,
      activePerspective,
      activeFilterLabels,
      visibleItems,
      loading,
      error,
    },
  };
}
