"use client";

import { useEffect, useState } from "react";
import {
  getLowQualityResearchReviewQueue,
  resolveLowQualityResearchReviewItem,
  rewriteLowQualityResearchReviewItem,
} from "@/lib/api";

type LowQualityQueue = Awaited<ReturnType<typeof getLowQualityResearchReviewQueue>>;

export function useResearchCenterLowQualityController({
  refreshResearchCards,
  refreshOfflineEvaluation,
  refreshControlPlaneDiagnostics,
}: {
  refreshResearchCards: () => Promise<unknown>;
  refreshOfflineEvaluation: () => Promise<unknown>;
  refreshControlPlaneDiagnostics: () => Promise<unknown>;
}) {
  const [lowQualityQueue, setLowQualityQueue] = useState<LowQualityQueue | null>(null);
  const [lowQualityLoading, setLowQualityLoading] = useState(true);
  const [lowQualityActionKey, setLowQualityActionKey] = useState("");
  const [lowQualityMessage, setLowQualityMessage] = useState("");
  const [lowQualityError, setLowQualityError] = useState("");

  const refreshLowQualityQueue = async () => {
    const queue = await getLowQualityResearchReviewQueue(12);
    setLowQualityQueue(queue);
    return queue;
  };

  useEffect(() => {
    let active = true;
    setLowQualityLoading(true);
    getLowQualityResearchReviewQueue(12)
      .then((res) => {
        if (!active) return;
        setLowQualityQueue(res);
      })
      .catch(() => {
        if (!active) return;
        setLowQualityQueue(null);
      })
      .finally(() => {
        if (!active) return;
        setLowQualityLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleRewriteLowQualityItem = async (entryId: string) => {
    setLowQualityActionKey(`${entryId}:rewrite`);
    setLowQualityMessage("");
    setLowQualityError("");
    try {
      await rewriteLowQualityResearchReviewItem(entryId);
      await Promise.all([
        refreshLowQualityQueue(),
        refreshResearchCards(),
        refreshOfflineEvaluation(),
        refreshControlPlaneDiagnostics(),
      ]);
      setLowQualityMessage("已生成修订建议，请复核后接受或回退。");
    } catch {
      setLowQualityError("低质量研报重写失败，请稍后重试。");
    } finally {
      setLowQualityActionKey("");
    }
  };

  const handleResolveLowQualityItem = async (entryId: string, action: "accept" | "revert") => {
    setLowQualityActionKey(`${entryId}:${action}`);
    setLowQualityMessage("");
    setLowQualityError("");
    try {
      await resolveLowQualityResearchReviewItem(entryId, action);
      await Promise.all([
        refreshLowQualityQueue(),
        refreshOfflineEvaluation(),
        refreshControlPlaneDiagnostics(),
      ]);
      if (action === "revert") {
        await refreshResearchCards();
        setLowQualityMessage("已回退到修订前版本。");
      } else {
        setLowQualityMessage("已接受当前修订结果。");
      }
    } catch {
      setLowQualityError(action === "accept" ? "接受修订结果失败，请稍后重试。" : "回退失败，当前记录缺少可恢复快照。");
    } finally {
      setLowQualityActionKey("");
    }
  };

  return {
    lowQualityQueue,
    lowQualityLoading,
    lowQualityActionKey,
    lowQualityMessage,
    lowQualityError,
    refreshLowQualityQueue,
    handleRewriteLowQualityItem,
    handleResolveLowQualityItem,
  };
}
