"use client";

import { useEffect, useState } from "react";
import {
  type ApiResearchSourceSettings,
  getResearchSourceSettings,
  updateResearchSourceSettings,
} from "@/lib/api";

const DEFAULT_SOURCE_SETTINGS: ApiResearchSourceSettings = {
  enable_jianyu_tender_feed: true,
  enable_yuntoutiao_feed: true,
  enable_ggzy_feed: true,
  enable_cecbid_feed: true,
  enable_ccgp_feed: true,
  enable_gov_policy_feed: true,
  enable_local_ggzy_feed: true,
  enable_curated_wechat_channels: true,
  enabled_source_labels: ["剑鱼标讯", "云头条", "全国公共资源交易平台", "中国招标投标网", "政府采购合规聚合", "中国政府网政策/讲话", "地方公共资源交易平台", "精选公众号观察池"],
  connector_statuses: [
    {
      key: "public_open_source_adapters",
      label: "公开招采与行业源适配器",
      status: "active",
      detail: "当前已接入公开招投标、政策讲话、行业媒体与聚合源；不绕过登录墙和付费墙。",
      requires_authorization: false,
    },
    {
      key: "curated_wechat_channels",
      label: "精选公众号观察池",
      status: "active",
      detail: "优先补充公众号观察池，当前包含 云技术 / 智能超参数 / 数说123之算力大模型。",
      requires_authorization: false,
    },
  ],
  updated_at: null,
};

export type SourceToggleKey =
  | "enable_jianyu_tender_feed"
  | "enable_yuntoutiao_feed"
  | "enable_ggzy_feed"
  | "enable_cecbid_feed"
  | "enable_ccgp_feed"
  | "enable_gov_policy_feed"
  | "enable_local_ggzy_feed"
  | "enable_curated_wechat_channels";

export function useResearchCenterSourceSettingsController() {
  const [sourceSettings, setSourceSettings] = useState<ApiResearchSourceSettings | null>(null);
  const [sourceSaving, setSourceSaving] = useState(false);
  const [sourceError, setSourceError] = useState("");

  useEffect(() => {
    let active = true;
    getResearchSourceSettings()
      .then((res) => {
        if (!active) return;
        setSourceSettings(res);
        setSourceError("");
      })
      .catch(() => {
        if (!active) return;
        setSourceError("研究来源设置暂时无法读取，当前先使用默认来源。");
        setSourceSettings(DEFAULT_SOURCE_SETTINGS);
      });
    return () => {
      active = false;
    };
  }, []);

  const toggleResearchSource = async (key: SourceToggleKey) => {
    if (!sourceSettings || sourceSaving) return;
    const previousSettings = sourceSettings;
    const nextPayload: ApiResearchSourceSettings = {
      ...sourceSettings,
      [key]: !sourceSettings[key],
    };
    setSourceSaving(true);
    setSourceError("");
    setSourceSettings((current) =>
      current
        ? {
            ...current,
            ...nextPayload,
          }
        : current,
    );
    try {
      const next = await updateResearchSourceSettings(nextPayload);
      setSourceSettings(next);
      setSourceError("");
    } catch {
      setSourceSettings(previousSettings);
      setSourceError("研究来源设置保存失败，请稍后重试。");
    } finally {
      setSourceSaving(false);
    }
  };

  return {
    sourceSettings,
    sourceSaving,
    sourceError,
    toggleResearchSource,
  };
}
