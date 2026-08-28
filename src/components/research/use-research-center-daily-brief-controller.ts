"use client";

import { useEffect, useState } from "react";
import { getResearchDailyBrief } from "@/lib/api";

type ResearchDailyBrief = Awaited<ReturnType<typeof getResearchDailyBrief>>;

export function useResearchCenterDailyBriefController() {
  const [dailyBrief, setDailyBrief] = useState<ResearchDailyBrief | null>(null);
  const [dailyBriefLoading, setDailyBriefLoading] = useState(true);
  const [dailyBriefRefreshing, setDailyBriefRefreshing] = useState(false);
  const [dailyBriefError, setDailyBriefError] = useState("");

  useEffect(() => {
    let active = true;
    getResearchDailyBrief(false)
      .then((res) => {
        if (!active) return;
        setDailyBrief(res);
      })
      .catch(() => {
        if (!active) return;
        setDailyBrief(null);
        setDailyBriefError("今日摘要加载失败，请稍后重试。");
      })
      .finally(() => {
        if (!active) return;
        setDailyBriefLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleRefreshDailyBrief = async () => {
    setDailyBriefRefreshing(true);
    setDailyBriefError("");
    try {
      const brief = await getResearchDailyBrief(true);
      setDailyBrief(brief);
    } catch {
      setDailyBriefError("今日摘要刷新失败，请稍后重试。");
    } finally {
      setDailyBriefRefreshing(false);
      setDailyBriefLoading(false);
    }
  };

  return {
    dailyBrief,
    dailyBriefLoading,
    dailyBriefRefreshing,
    dailyBriefError,
    handleRefreshDailyBrief,
  };
}
