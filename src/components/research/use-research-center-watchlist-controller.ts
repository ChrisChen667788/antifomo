"use client";

import { useEffect, useState } from "react";
import {
  type ApiResearchTrackingTopic,
  type ApiResearchWatchlist,
  type ApiResearchWatchlistAutomationStatus,
  type ApiResearchWatchlistDigestExport,
  type ApiResearchWatchlistOpsSummary,
  type ApiResearchWatchlistRun,
  type ApiResearchWatchlistRunDueResponse,
  createResearchWatchlist,
  getResearchWatchlistAutomationStatus,
  getResearchWatchlistDigestExport,
  getResearchWatchlistOpsSummary,
  getResearchWatchlistRunHistory,
  listResearchWatchlists,
  refreshResearchWatchlist,
  runDueResearchWatchlists,
  updateResearchWatchlist,
} from "@/lib/api";
import { triggerMarkdownDownload } from "@/components/research/research-center-utils";

export function useResearchCenterWatchlistController({
  refreshWorkspace,
}: {
  refreshWorkspace: () => Promise<unknown>;
}) {
  const [watchlists, setWatchlists] = useState<ApiResearchWatchlist[]>([]);
  const [watchlistAutomation, setWatchlistAutomation] = useState<ApiResearchWatchlistAutomationStatus | null>(null);
  const [watchlistOpsSummary, setWatchlistOpsSummary] = useState<ApiResearchWatchlistOpsSummary | null>(null);
  const [refreshingWatchlistId, setRefreshingWatchlistId] = useState<string>("");
  const [runningDueWatchlists, setRunningDueWatchlists] = useState(false);
  const [watchlistActionKey, setWatchlistActionKey] = useState("");
  const [watchlistMessage, setWatchlistMessage] = useState("");
  const [watchlistError, setWatchlistError] = useState("");
  const [lastRunDueResult, setLastRunDueResult] = useState<ApiResearchWatchlistRunDueResponse | null>(null);
  const [watchlistRunHistory, setWatchlistRunHistory] = useState<ApiResearchWatchlistRun[]>([]);
  const [watchlistDigestExport, setWatchlistDigestExport] = useState<ApiResearchWatchlistDigestExport | null>(null);

  const refreshWatchlistOpsSummary = async () => {
    const summary = await getResearchWatchlistOpsSummary();
    setWatchlistOpsSummary(summary);
    return summary;
  };

  useEffect(() => {
    let active = true;
    listResearchWatchlists()
      .then((res) => {
        if (!active) return;
        setWatchlists(res || []);
      })
      .catch(() => {
        if (!active) return;
        setWatchlists([]);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    Promise.all([
      getResearchWatchlistAutomationStatus().catch(() => null),
      getResearchWatchlistOpsSummary().catch(() => null),
      getResearchWatchlistRunHistory({ limit: 8 }).catch(() => []),
      getResearchWatchlistDigestExport({ since_hours: 24, limit: 20 }).catch(() => null),
    ])
      .then(([automation, opsSummary, runHistory, digestExport]) => {
        if (!active) return;
        setWatchlistAutomation(automation);
        setWatchlistOpsSummary(opsSummary);
        setWatchlistRunHistory(runHistory || []);
        setWatchlistDigestExport(digestExport);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleCreateWatchlist = async (topic: ApiResearchTrackingTopic) => {
    setWatchlistActionKey(`${topic.id}:create`);
    setWatchlistError("");
    try {
      const saved = await createResearchWatchlist({
        name: `${topic.name} Watchlist`,
        watch_type: "topic",
        query: topic.keyword,
        tracking_topic_id: topic.id,
        research_focus: topic.research_focus,
        perspective: topic.perspective,
        region_filter: topic.region_filter,
        industry_filter: topic.industry_filter,
        alert_level: "medium",
        schedule: "daily",
      });
      setWatchlists((current) => [saved, ...current.filter((item) => item.id !== saved.id)]);
      void refreshWatchlistOpsSummary().catch(() => undefined);
    } finally {
      setWatchlistActionKey("");
    }
  };

  const handleUpdateWatchlistSchedule = async (watchlistId: string, schedule: string) => {
    const currentWatchlist = watchlists.find((item) => item.id === watchlistId);
    if (!currentWatchlist || currentWatchlist.schedule === schedule) return;
    setWatchlistActionKey(`${watchlistId}-schedule`);
    setWatchlistError("");
    try {
      const saved = await updateResearchWatchlist(watchlistId, { schedule });
      setWatchlists((current) => current.map((item) => (item.id === watchlistId ? saved : item)));
      void refreshWatchlistOpsSummary().catch(() => undefined);
      setWatchlistMessage(`已更新 ${saved.name} 的刷新频率`);
    } catch {
      setWatchlistError("更新监控频率失败，请稍后重试。");
    } finally {
      setWatchlistActionKey("");
    }
  };

  const handleToggleWatchlistStatus = async (watchlist: ApiResearchWatchlist) => {
    const nextStatus = watchlist.status === "paused" ? "active" : "paused";
    setWatchlistActionKey(`${watchlist.id}-status`);
    setWatchlistError("");
    try {
      const saved = await updateResearchWatchlist(watchlist.id, { status: nextStatus });
      setWatchlists((current) => current.map((item) => (item.id === watchlist.id ? saved : item)));
      void refreshWatchlistOpsSummary().catch(() => undefined);
      setWatchlistMessage(nextStatus === "paused" ? `已暂停 ${saved.name}` : `已恢复 ${saved.name}`);
    } catch {
      setWatchlistError("更新监控状态失败，请稍后重试。");
    } finally {
      setWatchlistActionKey("");
    }
  };

  const handleRefreshWatchlist = async (watchlistId: string) => {
    setRefreshingWatchlistId(watchlistId);
    setWatchlistError("");
    try {
      const result = await refreshResearchWatchlist(watchlistId, {
        output_language: "zh-CN",
        include_wechat: true,
        max_sources: 12,
        save_to_knowledge: true,
      });
      setWatchlists((current) =>
        current.map((item) => (item.id === watchlistId ? result.watchlist : item)),
      );
      await refreshWorkspace();
      void refreshWatchlistOpsSummary().catch(() => undefined);
      setWatchlistMessage(
        result.changes?.length
          ? `${result.watchlist.name} 已刷新，识别到 ${result.changes.length} 条变化`
          : `${result.watchlist.name} 已刷新，暂无新增变化`,
      );
    } catch {
      setWatchlistError("手动刷新监控失败，请稍后重试。");
    } finally {
      setRefreshingWatchlistId("");
    }
  };

  const handleRunDueWatchlists = async () => {
    setRunningDueWatchlists(true);
    setWatchlistError("");
    try {
      const result = await runDueResearchWatchlists({
        output_language: "zh-CN",
        include_wechat: true,
        max_sources: 12,
        save_to_knowledge: true,
        limit: 6,
        retry_failed: true,
        max_retry_attempts: 1,
      });
      setLastRunDueResult(result);
      setWatchlistMessage(
        result.due_count
          ? `本轮检查 ${result.due_count} 个到期监控，已刷新 ${result.refreshed_count} 个，失败 ${result.failed_count} 个，重试 ${result.retry_count} 次。`
          : "当前没有到期监控。",
      );
      const [nextWatchlists, automation, opsSummary, runHistory, digestExport] = await Promise.all([
        listResearchWatchlists(),
        getResearchWatchlistAutomationStatus().catch(() => null),
        getResearchWatchlistOpsSummary().catch(() => null),
        getResearchWatchlistRunHistory({ limit: 8 }).catch(() => []),
        getResearchWatchlistDigestExport({ since_hours: 24, limit: 20 }).catch(() => null),
        refreshWorkspace(),
      ]);
      setWatchlists(nextWatchlists || []);
      if (automation) {
        setWatchlistAutomation(automation);
      }
      if (opsSummary) {
        setWatchlistOpsSummary(opsSummary);
      }
      setWatchlistRunHistory(runHistory || []);
      if (digestExport) {
        setWatchlistDigestExport(digestExport);
      }
    } catch {
      setWatchlistError("执行到期监控失败，请稍后重试或查看本地巡检状态。");
    } finally {
      setRunningDueWatchlists(false);
    }
  };

  const handleDownloadWatchlistDigest = async () => {
    try {
      const digest = await getResearchWatchlistDigestExport({ since_hours: 24, limit: 50 });
      setWatchlistDigestExport(digest);
      triggerMarkdownDownload(`watchlist-digest-${new Date().toISOString().slice(0, 10)}.md`, digest.export_markdown);
      setWatchlistMessage("监控摘要已导出");
      setWatchlistError("");
    } catch {
      setWatchlistError("导出监控摘要失败，请稍后重试。");
    }
  };

  const copyWatchlistOpsText = async (value: string, label: string) => {
    try {
      await navigator.clipboard.writeText(value);
      setWatchlistMessage(`${label}已复制`);
      setWatchlistError("");
    } catch {
      setWatchlistError("复制失败，请稍后重试。");
    }
  };

  return {
    watchlists,
    watchlistAutomation,
    watchlistOpsSummary,
    watchlistDigestExport,
    watchlistMessage,
    watchlistError,
    lastRunDueResult,
    watchlistRunHistory,
    runningDueWatchlists,
    watchlistActionKey,
    refreshingWatchlistId,
    handleCreateWatchlist,
    handleDownloadWatchlistDigest,
    handleRunDueWatchlists,
    copyWatchlistOpsText,
    handleUpdateWatchlistSchedule,
    handleToggleWatchlistStatus,
    handleRefreshWatchlist,
  };
}
