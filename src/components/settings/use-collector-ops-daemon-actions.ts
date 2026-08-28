"use client";

import { useState } from "react";
import {
  runCollectorDaemonOnce,
  startCollectorDaemon,
  stopCollectorDaemon,
  updateCollectorDaemonConfig,
  verifyCollectorBrowserExtension,
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
  const [updatingClipboardAutoImport, setUpdatingClipboardAutoImport] = useState(false);
  const [updatingExportDirectoryAutoImport, setUpdatingExportDirectoryAutoImport] = useState(false);
  const [verifyingBrowserExtension, setVerifyingBrowserExtension] = useState(false);

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

  const handleToggleClipboardAutoImport = async (enabled: boolean) => {
    setUpdatingClipboardAutoImport(true);
    try {
      await updateCollectorDaemonConfig({
        wechat_clipboard_auto_import: enabled,
      });
      setMessage(enabled ? "已开启剪贴板自动导入" : "已关闭剪贴板自动导入");
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setUpdatingClipboardAutoImport(false);
    }
  };

  const handleUpdateExportDirectoryAutoImport = async (payload: {
    enabled?: boolean;
    path?: string;
  }) => {
    setUpdatingExportDirectoryAutoImport(true);
    try {
      await updateCollectorDaemonConfig({
        wechat_export_directory_auto_import: payload.enabled,
        wechat_export_directory_path: payload.path,
      });
      setMessage("微信收藏导出目录设置已保存");
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setUpdatingExportDirectoryAutoImport(false);
    }
  };

  const handleVerifyBrowserExtension = async () => {
    setVerifyingBrowserExtension(true);
    try {
      const result = await verifyCollectorBrowserExtension();
      setMessage(result.message);
      setCommandOutput(result.output || "");
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setVerifyingBrowserExtension(false);
    }
  };

  return {
    startingDaemon,
    stoppingDaemon,
    runningOnce,
    updatingClipboardAutoImport,
    updatingExportDirectoryAutoImport,
    verifyingBrowserExtension,
    handleStartDaemon,
    handleStopDaemon,
    handleRunOnce,
    handleToggleClipboardAutoImport,
    handleUpdateExportDirectoryAutoImport,
    handleVerifyBrowserExtension,
  };
}
