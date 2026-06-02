"use client";

import { useState } from "react";
import {
  runCollectorDaemonOnce,
  startCollectorDaemon,
  stopCollectorDaemon,
  type CollectorDaemonStatus,
} from "@/lib/api";
import type { AppLanguage } from "@/lib/preferences";

type UseCollectorOpsDaemonActionsParams = {
  language: AppLanguage;
  refreshStatus: () => Promise<void>;
  setCommandOutput: (value: string) => void;
  setDaemonStatus: (value: CollectorDaemonStatus | null) => void;
  setMessage: (value: string) => void;
};

export function useCollectorOpsDaemonActions({
  language,
  refreshStatus,
  setCommandOutput,
  setDaemonStatus,
  setMessage,
}: UseCollectorOpsDaemonActionsParams) {
  const [startingDaemon, setStartingDaemon] = useState(false);
  const [stoppingDaemon, setStoppingDaemon] = useState(false);
  const [runningOnce, setRunningOnce] = useState(false);

  const handleStartDaemon = async () => {
    setStartingDaemon(true);
    try {
      const result = await startCollectorDaemon();
      setMessage(result.message);
      setCommandOutput(result.output || "");
      setDaemonStatus(result.status);
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setStartingDaemon(false);
    }
  };

  const handleStopDaemon = async () => {
    setStoppingDaemon(true);
    try {
      const result = await stopCollectorDaemon();
      setMessage(result.message);
      setCommandOutput(result.output || "");
      setDaemonStatus(result.status);
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setStoppingDaemon(false);
    }
  };

  const handleRunOnce = async () => {
    setRunningOnce(true);
    try {
      const result = await runCollectorDaemonOnce({
        output_language: language,
        max_collect_per_cycle: 30,
      });
      setMessage(result.message);
      setCommandOutput(result.output || "");
      setDaemonStatus(result.status);
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setRunningOnce(false);
    }
  };

  return {
    startingDaemon,
    stoppingDaemon,
    runningOnce,
    handleStartDaemon,
    handleStopDaemon,
    handleRunOnce,
  };
}
