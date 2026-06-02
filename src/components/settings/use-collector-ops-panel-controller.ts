"use client";

import { startTransition, useEffect, useState } from "react";
import {
  getCollectorDaemonStatus,
  getCollectorStatus,
  getItem,
  getWechatAgentBatchStatus,
  getWechatAgentConfig,
  getWechatAgentDedupSummary,
  getWechatAgentHealth,
  getWechatAgentStatus,
  listCollectorFailed,
  type ApiItem,
  type CollectorDaemonStatus,
  type CollectorDailySummary,
  type CollectorFailedItem,
  type CollectorStatus,
  type WechatAgentBatchStatus,
  type WechatAgentCapturePreview,
  type WechatAgentConfig,
  type WechatAgentDedupSummary,
  type WechatAgentHealth,
  type WechatAgentOCRPreview,
  type WechatAgentStatus,
} from "@/lib/api";
import type { AppLanguage } from "@/lib/preferences";
import { useCollectorOpsDaemonActions } from "@/components/settings/use-collector-ops-daemon-actions";
import { useCollectorOpsGeneralActions } from "@/components/settings/use-collector-ops-general-actions";
import { useCollectorOpsRouteMetrics } from "@/components/settings/use-collector-ops-route-metrics";
import { useCollectorOpsWechatAgentActions } from "@/components/settings/use-collector-ops-wechat-agent-actions";
import { useCollectorOpsWechatAgentConfig } from "@/components/settings/use-collector-ops-wechat-agent-config";

type CollectorOpsPanelText = (key: string) => string;

export function useCollectorOpsPanelController({
  language,
  text,
}: {
  language: AppLanguage;
  text: CollectorOpsPanelText;
}) {
  const [status, setStatus] = useState<CollectorStatus | null>(null);
  const [daemonStatus, setDaemonStatus] = useState<CollectorDaemonStatus | null>(null);
  const [wechatAgentStatus, setWechatAgentStatus] = useState<WechatAgentStatus | null>(null);
  const [wechatAgentBatchStatus, setWechatAgentBatchStatus] = useState<WechatAgentBatchStatus | null>(null);
  const [wechatAgentHealth, setWechatAgentHealth] = useState<WechatAgentHealth | null>(null);
  const [wechatAgentConfig, setWechatAgentConfig] = useState<WechatAgentConfig | null>(null);
  const [wechatAgentDedupSummary, setWechatAgentDedupSummary] = useState<WechatAgentDedupSummary | null>(null);
  const [wechatAgentBatchItems, setWechatAgentBatchItems] = useState<ApiItem[]>([]);
  const [wechatAgentCapturePreview, setWechatAgentCapturePreview] =
    useState<WechatAgentCapturePreview | null>(null);
  const [wechatAgentOCRPreview, setWechatAgentOCRPreview] = useState<WechatAgentOCRPreview | null>(null);
  const [failedItems, setFailedItems] = useState<CollectorFailedItem[]>([]);
  const [dailySummary, setDailySummary] = useState<CollectorDailySummary | null>(null);
  const [message, setMessage] = useState<string>("");
  const [commandOutput, setCommandOutput] = useState<string>("");
  const [wechatAgentOutput, setWechatAgentOutput] = useState<string>("");
  const [loadingState, setLoadingState] = useState(false);

  const refreshStatus = async () => {
    setLoadingState(true);
    setMessage("");
    try {
      const [
        statusRes,
        failedRes,
        daemonRes,
        wechatAgentRes,
        wechatAgentBatchRes,
        wechatAgentHealthRes,
        wechatAgentConfigRes,
        wechatAgentDedupRes,
      ] = await Promise.all([
        getCollectorStatus(),
        listCollectorFailed(12),
        getCollectorDaemonStatus(),
        getWechatAgentStatus(),
        getWechatAgentBatchStatus(),
        getWechatAgentHealth(),
        getWechatAgentConfig(),
        getWechatAgentDedupSummary(),
      ]);
      startTransition(() => {
        setStatus(statusRes);
        setFailedItems(failedRes.items || []);
        setDaemonStatus(daemonRes);
        setWechatAgentStatus(wechatAgentRes);
        setWechatAgentBatchStatus(wechatAgentBatchRes);
        setWechatAgentHealth(wechatAgentHealthRes);
        setWechatAgentConfig(wechatAgentConfigRes);
        setWechatAgentDedupSummary(wechatAgentDedupRes);
      });
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setLoadingState(false);
    }
  };

  useEffect(() => {
    void refreshStatus();
  }, []);

  useEffect(() => {
    if (!wechatAgentBatchStatus?.running) {
      return;
    }
    const timer = window.setInterval(() => {
      void refreshStatus();
    }, 5000);
    return () => {
      window.clearInterval(timer);
    };
  }, [wechatAgentBatchStatus?.running]);

  useEffect(() => {
    const itemIds = Array.isArray(wechatAgentBatchStatus?.new_item_ids)
      ? wechatAgentBatchStatus?.new_item_ids.slice(0, 8)
      : [];
    if (!itemIds.length) {
      setWechatAgentBatchItems([]);
      return;
    }

    let cancelled = false;
    const loadBatchItems = async () => {
      try {
        const results = await Promise.all(itemIds.map((itemId) => getItem(itemId)));
        if (!cancelled) {
          startTransition(() => {
            setWechatAgentBatchItems(results);
          });
        }
      } catch {
        if (!cancelled) {
          setWechatAgentBatchItems([]);
        }
      }
    };

    void loadBatchItems();
    return () => {
      cancelled = true;
    };
  }, [wechatAgentBatchStatus?.new_item_ids]);

  const generalActions = useCollectorOpsGeneralActions({
    dailySummary,
    refreshStatus,
    setCommandOutput,
    setDailySummary,
    setMessage,
    text,
  });
  const daemonActions = useCollectorOpsDaemonActions({
    language,
    refreshStatus,
    setCommandOutput,
    setDaemonStatus,
    setMessage,
  });
  const wechatAgentActions = useCollectorOpsWechatAgentActions({
    language,
    refreshStatus,
    setMessage,
    setWechatAgentBatchStatus,
    setWechatAgentCapturePreview,
    setWechatAgentDedupSummary,
    setWechatAgentHealth,
    setWechatAgentOCRPreview,
    setWechatAgentOutput,
    setWechatAgentStatus,
    text,
    wechatAgentConfig,
  });
  const wechatAgentConfigController = useCollectorOpsWechatAgentConfig({
    refreshStatus,
    setMessage,
    setWechatAgentConfig,
    text,
    wechatAgentConfig,
  });
  const routeMetrics = useCollectorOpsRouteMetrics(wechatAgentBatchStatus);

  return {
    status,
    daemonStatus,
    wechatAgentStatus,
    wechatAgentBatchStatus,
    wechatAgentHealth,
    wechatAgentConfig,
    setWechatAgentConfig,
    wechatAgentDedupSummary,
    wechatAgentBatchItems,
    wechatAgentCapturePreview,
    wechatAgentOCRPreview,
    failedItems,
    message,
    commandOutput,
    wechatAgentOutput,
    loadingState,
    refreshStatus,
    ...generalActions,
    ...daemonActions,
    ...wechatAgentActions,
    ...wechatAgentConfigController,
    ...routeMetrics,
  };
}
