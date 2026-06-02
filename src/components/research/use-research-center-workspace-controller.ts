"use client";

import { useEffect, useState, type Dispatch, type SetStateAction } from "react";
import {
  type ApiKnowledgeEntry,
  type ApiResearchCompareSnapshot,
  type ApiResearchMarkdownArchive,
  type ApiResearchSavedView,
  type ApiResearchTrackingTopic,
  type ApiResearchWorkspace,
  deleteResearchCompareSnapshot,
  deleteResearchTrackingTopic,
  deleteResearchView,
  getResearchWorkspace,
  refreshResearchTrackingTopic,
  saveResearchTrackingTopic,
  saveResearchView,
} from "@/lib/api";
import type { ResearchPerspective } from "@/lib/research-facets";
import {
  getResearchKeyword,
  type ResearchCenterEntry,
  type ResearchFilter,
} from "@/components/research/research-center-utils";

type TranslationFn = (key: string, fallback: string) => string;

type UseResearchCenterWorkspaceControllerParams = {
  t: TranslationFn;
  query: string;
  filter: ResearchFilter;
  perspective: ResearchPerspective;
  regionFilter: string;
  industryFilter: string;
  actionTypeFilter: string;
  focusOnly: boolean;
  activePerspectiveLabel: string;
  activeFilterLabels: string[];
  visibleItems: ResearchCenterEntry[];
  reports: ResearchCenterEntry[];
  actions: ResearchCenterEntry[];
  setFilter: Dispatch<SetStateAction<ResearchFilter>>;
  setPerspective: Dispatch<SetStateAction<ResearchPerspective>>;
  setRegionFilter: Dispatch<SetStateAction<string>>;
  setIndustryFilter: Dispatch<SetStateAction<string>>;
  setActionTypeFilter: Dispatch<SetStateAction<string>>;
  setFocusOnly: Dispatch<SetStateAction<boolean>>;
  setQuery: Dispatch<SetStateAction<string>>;
  setQueryDraft: Dispatch<SetStateAction<string>>;
};

export function useResearchCenterWorkspaceController({
  t,
  query,
  filter,
  perspective,
  regionFilter,
  industryFilter,
  actionTypeFilter,
  focusOnly,
  activePerspectiveLabel,
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
}: UseResearchCenterWorkspaceControllerParams) {
  const [savedViews, setSavedViews] = useState<ApiResearchSavedView[]>([]);
  const [trackingTopics, setTrackingTopics] = useState<ApiResearchTrackingTopic[]>([]);
  const [compareSnapshots, setCompareSnapshots] = useState<ApiResearchCompareSnapshot[]>([]);
  const [markdownArchives, setMarkdownArchives] = useState<ApiResearchMarkdownArchive[]>([]);
  const [workspaceSaving, setWorkspaceSaving] = useState(false);
  const [refreshingTopicId, setRefreshingTopicId] = useState<string>("");

  const applyWorkspace = (workspace: ApiResearchWorkspace) => {
    setSavedViews(workspace.saved_views || []);
    setTrackingTopics(workspace.tracking_topics || []);
    setCompareSnapshots(workspace.compare_snapshots || []);
    setMarkdownArchives(workspace.markdown_archives || []);
  };

  const refreshWorkspace = async () => {
    const workspace = await getResearchWorkspace();
    applyWorkspace(workspace);
    return workspace;
  };

  useEffect(() => {
    let active = true;
    getResearchWorkspace()
      .then((res) => {
        if (!active) return;
        applyWorkspace(res);
      })
      .catch(() => {
        if (!active) return;
        setSavedViews([]);
        setTrackingTopics([]);
        setCompareSnapshots([]);
        setMarkdownArchives([]);
      });
    return () => {
      active = false;
    };
  }, []);

  const removeMarkdownArchive = (archiveId: string) => {
    setMarkdownArchives((current) => current.filter((item) => item.id !== archiveId));
  };

  const applySavedView = (view: ApiResearchSavedView) => {
    setFilter(view.filter_mode);
    setPerspective(view.perspective);
    setRegionFilter(view.region_filter || "");
    setIndustryFilter(view.industry_filter || "");
    setActionTypeFilter(view.action_type_filter || "");
    setFocusOnly(!!view.focus_only);
    setQuery(view.query || "");
    setQueryDraft(view.query || "");
  };

  const handleSaveCurrentView = async () => {
    const trimmedQuery = query.trim();
    const nameSeed = trimmedQuery || activePerspectiveLabel || t("research.centerViewAll", "全部视角");
    setWorkspaceSaving(true);
    try {
      const saved = await saveResearchView({
        name: `${nameSeed} · ${new Date().toLocaleDateString()}`,
        query: trimmedQuery,
        filter_mode: filter,
        perspective,
        region_filter: regionFilter,
        industry_filter: industryFilter,
        action_type_filter: actionTypeFilter,
        focus_only: focusOnly,
      });
      setSavedViews((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
    } finally {
      setWorkspaceSaving(false);
    }
  };

  const handleDeleteSavedView = async (viewId: string) => {
    setWorkspaceSaving(true);
    try {
      await deleteResearchView(viewId);
      setSavedViews((current) => current.filter((item) => item.id !== viewId));
    } finally {
      setWorkspaceSaving(false);
    }
  };

  const handleDeleteCompareSnapshot = async (snapshotId: string) => {
    setWorkspaceSaving(true);
    try {
      await deleteResearchCompareSnapshot(snapshotId);
      setCompareSnapshots((current) => current.filter((item) => item.id !== snapshotId));
    } finally {
      setWorkspaceSaving(false);
    }
  };

  const handleSaveTrackingTopic = async () => {
    const keyword = query.trim() || getResearchKeyword(visibleItems[0] || reports[0] || actions[0] || ({} as ApiKnowledgeEntry));
    if (!keyword) return;
    const focusText = activeFilterLabels.join(" / ");
    setWorkspaceSaving(true);
    try {
      const saved = await saveResearchTrackingTopic({
        name: `${keyword} 跟踪`,
        keyword,
        research_focus: focusText,
        perspective,
        region_filter: regionFilter,
        industry_filter: industryFilter,
        notes: visibleItems[0]?.title || "",
      });
      setTrackingTopics((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
    } finally {
      setWorkspaceSaving(false);
    }
  };

  const applyTrackingTopic = (topic: ApiResearchTrackingTopic) => {
    setPerspective(topic.perspective);
    setRegionFilter(topic.region_filter || "");
    setIndustryFilter(topic.industry_filter || "");
    setQuery(topic.keyword || "");
    setQueryDraft(topic.keyword || "");
    setActionTypeFilter("");
    setFocusOnly(false);
  };

  const handleDeleteTrackingTopic = async (topicId: string) => {
    setWorkspaceSaving(true);
    try {
      await deleteResearchTrackingTopic(topicId);
      setTrackingTopics((current) => current.filter((item) => item.id !== topicId));
    } finally {
      setWorkspaceSaving(false);
    }
  };

  const handleRefreshTrackingTopic = async (topicId: string) => {
    setRefreshingTopicId(topicId);
    setTrackingTopics((current) =>
      current.map((item) =>
        item.id === topicId
          ? {
              ...item,
              last_refresh_status: "running",
              last_refresh_error: "",
              last_refresh_note: "正在刷新专题研报并补充新增情报",
            }
          : item,
      ),
    );
    try {
      const result = await refreshResearchTrackingTopic(topicId, {
        output_language: "zh-CN",
        include_wechat: true,
        max_sources: 12,
        save_to_knowledge: true,
      });
      setTrackingTopics((current) =>
        current.map((item) => (item.id === topicId ? result.topic : item)),
      );
    } catch (error) {
      const message = error instanceof Error ? error.message : "专题刷新失败";
      setTrackingTopics((current) =>
        current.map((item) =>
          item.id === topicId
            ? {
                ...item,
                last_refresh_status: "failed",
                last_refresh_error: message,
                last_refresh_note: "专题刷新失败，请检查当前关键词和公开来源设置",
              }
            : item,
        ),
      );
    } finally {
      setRefreshingTopicId("");
    }
  };

  return {
    savedViews,
    trackingTopics,
    compareSnapshots,
    markdownArchives,
    workspaceSaving,
    setWorkspaceSaving,
    refreshingTopicId,
    refreshWorkspace,
    removeMarkdownArchive,
    handleDeleteCompareSnapshot,
    handleSaveCurrentView,
    handleDeleteSavedView,
    applySavedView,
    handleSaveTrackingTopic,
    handleDeleteTrackingTopic,
    handleRefreshTrackingTopic,
    applyTrackingTopic,
  };
}
