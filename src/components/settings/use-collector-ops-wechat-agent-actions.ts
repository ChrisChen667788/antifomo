"use client";

import { useState } from "react";
import {
  getWechatAgentCapturePreview,
  getWechatAgentHealth,
  getWechatAgentOCRPreview,
  resetWechatAgentDedupSummary,
  runWechatAgentBatch,
  runWechatAgentOnce,
  runWechatAgentSelfHeal,
  startWechatAgent,
  stopWechatAgent,
  type WechatAgentBatchStatus,
  type WechatAgentCapturePreview,
  type WechatAgentConfig,
  type WechatAgentDedupSummary,
  type WechatAgentHealth,
  type WechatAgentOCRPreview,
  type WechatAgentStatus,
} from "@/lib/api";
import type { AppLanguage } from "@/lib/preferences";
import { formatBytes } from "@/components/settings/collector-ops-panel-utils";

type CollectorOpsPanelText = (key: string) => string;

type UseCollectorOpsWechatAgentActionsParams = {
  language: AppLanguage;
  refreshStatus: () => Promise<void>;
  setMessage: (value: string) => void;
  setWechatAgentBatchStatus: (value: WechatAgentBatchStatus | null) => void;
  setWechatAgentCapturePreview: (value: WechatAgentCapturePreview | null) => void;
  setWechatAgentDedupSummary: (value: WechatAgentDedupSummary | null) => void;
  setWechatAgentHealth: (value: WechatAgentHealth | null) => void;
  setWechatAgentOCRPreview: (value: WechatAgentOCRPreview | null) => void;
  setWechatAgentOutput: (value: string) => void;
  setWechatAgentStatus: (value: WechatAgentStatus | null) => void;
  text: CollectorOpsPanelText;
  wechatAgentConfig: WechatAgentConfig | null;
};

export function useCollectorOpsWechatAgentActions({
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
}: UseCollectorOpsWechatAgentActionsParams) {
  const [startingWechatAgent, setStartingWechatAgent] = useState(false);
  const [stoppingWechatAgent, setStoppingWechatAgent] = useState(false);
  const [runningWechatAgentOnce, setRunningWechatAgentOnce] = useState(false);
  const [runningWechatAgentBatch, setRunningWechatAgentBatch] = useState(false);
  const [checkingWechatAgentHealth, setCheckingWechatAgentHealth] = useState(false);
  const [healingWechatAgent, setHealingWechatAgent] = useState(false);
  const [capturingWechatPreview, setCapturingWechatPreview] = useState(false);
  const [runningWechatOCRPreview, setRunningWechatOCRPreview] = useState(false);
  const [resettingWechatDedup, setResettingWechatDedup] = useState(false);
  const [resettingWechatDedupHard, setResettingWechatDedupHard] = useState(false);

  const handleStartWechatAgent = async () => {
    setStartingWechatAgent(true);
    try {
      const result = await startWechatAgent();
      setMessage(result.message);
      setWechatAgentOutput(result.output || "");
      setWechatAgentStatus(result.status);
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setStartingWechatAgent(false);
    }
  };

  const handleStopWechatAgent = async () => {
    setStoppingWechatAgent(true);
    try {
      const result = await stopWechatAgent();
      setMessage(result.message);
      setWechatAgentOutput(result.output || "");
      setWechatAgentStatus(result.status);
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setStoppingWechatAgent(false);
    }
  };

  const handleRunWechatAgentOnce = async () => {
    setRunningWechatAgentOnce(true);
    try {
      const result = await runWechatAgentOnce({
        output_language: language,
        max_items: 36,
        wait: false,
      });
      setMessage(result.message);
      setWechatAgentOutput(result.output || "");
      setWechatAgentStatus(result.status);
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setRunningWechatAgentOnce(false);
    }
  };

  const handleRunWechatAgentBatch = async () => {
    setRunningWechatAgentBatch(true);
    try {
      const result = await runWechatAgentBatch({
        output_language: language,
        total_items: 18,
        segment_items: 6,
      });
      setMessage(result.message);
      setWechatAgentBatchStatus(result.batch_status);
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setRunningWechatAgentBatch(false);
    }
  };

  const handleResetWechatDedup = async (clearRuns: boolean) => {
    const confirmed = window.confirm(
      clearRuns
        ? `${text("wechatAgentDedupResetHard")}？`
        : `${text("wechatAgentDedupReset")}？`,
    );
    if (!confirmed) {
      return;
    }
    if (clearRuns) {
      setResettingWechatDedupHard(true);
    } else {
      setResettingWechatDedup(true);
    }
    try {
      const result = await resetWechatAgentDedupSummary({ clear_runs: clearRuns });
      setWechatAgentDedupSummary(result);
      setMessage(
        `${clearRuns ? text("wechatAgentDedupResetHard") : text("wechatAgentDedupReset")} ok`,
      );
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      if (clearRuns) {
        setResettingWechatDedupHard(false);
      } else {
        setResettingWechatDedup(false);
      }
    }
  };

  const handleCheckWechatAgentHealth = async () => {
    setCheckingWechatAgentHealth(true);
    try {
      const health = await getWechatAgentHealth({
        stale_minutes: wechatAgentConfig?.health_stale_minutes ?? undefined,
      });
      setWechatAgentHealth(health);
      setWechatAgentStatus(health.status);
      setMessage(
        `wechat agent health=${health.healthy ? "ok" : "bad"} reasons=${health.reasons.join(",") || "-"}`,
      );
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setCheckingWechatAgentHealth(false);
    }
  };

  const handleWechatAgentSelfHeal = async () => {
    setHealingWechatAgent(true);
    try {
      const result = await runWechatAgentSelfHeal();
      setWechatAgentOutput(result.output || "");
      setWechatAgentHealth(result.health_after);
      setWechatAgentStatus(result.health_after.status);
      setMessage(result.message);
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setHealingWechatAgent(false);
    }
  };

  const handleWechatPreviewCapture = async () => {
    setCapturingWechatPreview(true);
    try {
      const preview = await getWechatAgentCapturePreview();
      setWechatAgentCapturePreview(preview);
      setMessage(
        `${text("wechatAgentPreviewImage")}: ${preview.region.width}x${preview.region.height}, ${formatBytes(preview.image_size_bytes)}`,
      );
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setCapturingWechatPreview(false);
    }
  };

  const handleWechatPreviewOCR = async () => {
    setRunningWechatOCRPreview(true);
    try {
      const preview = await getWechatAgentOCRPreview({ output_language: language });
      setWechatAgentOCRPreview(preview);
      setMessage(`${text("wechatAgentPreviewOCRTitle")}已生成。`);
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setRunningWechatOCRPreview(false);
    }
  };

  return {
    startingWechatAgent,
    stoppingWechatAgent,
    runningWechatAgentOnce,
    runningWechatAgentBatch,
    checkingWechatAgentHealth,
    healingWechatAgent,
    capturingWechatPreview,
    runningWechatOCRPreview,
    resettingWechatDedup,
    resettingWechatDedupHard,
    handleStartWechatAgent,
    handleStopWechatAgent,
    handleRunWechatAgentOnce,
    handleRunWechatAgentBatch,
    handleResetWechatDedup,
    handleCheckWechatAgentHealth,
    handleWechatAgentSelfHeal,
    handleWechatPreviewCapture,
    handleWechatPreviewOCR,
  };
}
