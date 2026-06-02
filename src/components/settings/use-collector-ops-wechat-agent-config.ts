"use client";

import { useEffect, useState } from "react";
import {
  updateWechatAgentConfig,
  type WechatAgentConfig,
} from "@/lib/api";
import {
  formatPointPairs,
  parsePointPairs,
} from "@/components/settings/collector-ops-panel-utils";

type CollectorOpsPanelText = (key: string) => string;

type SetWechatAgentConfig = (
  value:
    | WechatAgentConfig
    | null
    | ((prev: WechatAgentConfig | null) => WechatAgentConfig | null),
) => void;

type UseCollectorOpsWechatAgentConfigParams = {
  refreshStatus: () => Promise<void>;
  setMessage: (value: string) => void;
  setWechatAgentConfig: SetWechatAgentConfig;
  text: CollectorOpsPanelText;
  wechatAgentConfig: WechatAgentConfig | null;
};

export function useCollectorOpsWechatAgentConfig({
  refreshStatus,
  setMessage,
  setWechatAgentConfig,
  text,
  wechatAgentConfig,
}: UseCollectorOpsWechatAgentConfigParams) {
  const [savingWechatAgentConfig, setSavingWechatAgentConfig] = useState(false);
  const [wechatHotspotsText, setWechatHotspotsText] = useState("");
  const [wechatMenuOffsetsText, setWechatMenuOffsetsText] = useState("");

  useEffect(() => {
    setWechatHotspotsText(
      formatPointPairs(wechatAgentConfig?.article_link_hotspots, "right_inset", "top_offset"),
    );
    setWechatMenuOffsetsText(
      formatPointPairs(wechatAgentConfig?.article_link_menu_offsets, "dx", "dy"),
    );
  }, [wechatAgentConfig]);

  const handleSaveWechatAgentConfig = async () => {
    if (!wechatAgentConfig) return;
    setSavingWechatAgentConfig(true);
    try {
      const parsedHotspots = parsePointPairs(wechatHotspotsText, {
        xKey: "right_inset",
        yKey: "top_offset",
      });
      const parsedMenuOffsets = parsePointPairs(wechatMenuOffsetsText, {
        xKey: "dx",
        yKey: "dy",
      });
      if (!parsedHotspots || !parsedMenuOffsets) {
        throw new Error(text("wechatAgentConfigMenuHint"));
      }
      const saved = await updateWechatAgentConfig({
        ...wechatAgentConfig,
        article_link_profile: wechatAgentConfig.article_link_profile,
        article_link_hotspots: parsedHotspots as WechatAgentConfig["article_link_hotspots"],
        article_link_menu_offsets: parsedMenuOffsets as WechatAgentConfig["article_link_menu_offsets"],
      });
      setWechatAgentConfig(saved);
      setMessage("微信采集配置已保存");
      await refreshStatus();
    } catch (error) {
      setMessage(String(error instanceof Error ? error.message : error));
    } finally {
      setSavingWechatAgentConfig(false);
    }
  };

  const updateWechatAgentIntField = (
    key:
      | "rows_per_batch"
      | "batches_per_cycle"
      | "article_row_height"
      | "min_capture_file_size_kb"
      | "loop_interval_sec"
      | "health_stale_minutes",
    value: string,
  ) => {
    setWechatAgentConfig((prev) => {
      if (!prev) return prev;
      const parsed = Number.parseInt(value, 10);
      if (Number.isNaN(parsed)) return prev;
      return { ...prev, [key]: parsed };
    });
  };

  return {
    savingWechatAgentConfig,
    wechatHotspotsText,
    setWechatHotspotsText,
    wechatMenuOffsetsText,
    setWechatMenuOffsetsText,
    handleSaveWechatAgentConfig,
    updateWechatAgentIntField,
  };
}
