"use client";

import { startTransition, useDeferredValue, useState } from "react";
import {
  getCollectorDailySummary,
  processCollectorPending,
  retryCollectorFailed,
  type CollectorDailySummary,
} from "@/lib/api";

type CollectorOpsPanelText = (key: string) => string;

type UseCollectorOpsGeneralActionsParams = {
  dailySummary: CollectorDailySummary | null;
  refreshStatus: () => Promise<void>;
  setCommandOutput: (value: string) => void;
  setDailySummary: (value: CollectorDailySummary | null) => void;
  setMessage: (value: string) => void;
  text: CollectorOpsPanelText;
};

export function useCollectorOpsGeneralActions({
  dailySummary,
  refreshStatus,
  setCommandOutput,
  setDailySummary,
  setMessage,
  text,
}: UseCollectorOpsGeneralActionsParams) {
  const [processingPending, setProcessingPending] = useState(false);
  const [retryingFailed, setRetryingFailed] = useState(false);
  const [generatingDaily, setGeneratingDaily] = useState(false);
  const deferredMarkdown = useDeferredValue(dailySummary?.markdown || "");

  const handleFlushPending = async () => {
    setProcessingPending(true);
    try {
      const result = await processCollectorPending(80);
      setMessage(
        `pending scanned=${result.scanned}, processed=${result.processed}, failed=${result.failed}, remaining=${result.remaining_pending}`,
      );
      setCommandOutput("");
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setProcessingPending(false);
    }
  };

  const handleRetryFailed = async () => {
    setRetryingFailed(true);
    try {
      const result = await retryCollectorFailed(30);
      setMessage(`retry scanned=${result.scanned}, ready=${result.ready}, failed=${result.failed}`);
      setCommandOutput("");
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setRetryingFailed(false);
    }
  };

  const handleGenerateDaily = async () => {
    setGeneratingDaily(true);
    try {
      const result = await getCollectorDailySummary(24, 12);
      startTransition(() => {
        setDailySummary(result);
      });
      setMessage(
        `daily generated: total=${result.total_ingested}, ready=${result.ready_count}, failed=${result.failed_count}`,
      );
      setCommandOutput("");
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setGeneratingDaily(false);
    }
  };

  const handleCopyMarkdown = async () => {
    if (!deferredMarkdown) return;
    try {
      await navigator.clipboard.writeText(deferredMarkdown);
      setMessage(text("messageCopied"));
    } catch {
      setMessage("copy failed");
    }
  };

  return {
    processingPending,
    retryingFailed,
    generatingDaily,
    deferredMarkdown,
    handleFlushPending,
    handleRetryFailed,
    handleGenerateDaily,
    handleCopyMarkdown,
  };
}
