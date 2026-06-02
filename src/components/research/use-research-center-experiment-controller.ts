"use client";

import { useEffect, useState } from "react";
import {
  type ApiResearchDeliveryExportDiagnostics,
  type ApiResearchExperimentControlPlane,
  type ApiResearchExperimentEffectiveRuntimeConfig,
  type ApiResearchExperimentOrchestration,
  type ApiResearchExperimentPlan,
  type ApiResearchExperimentRuntimeSnapshot,
  type ApiResearchFollowupDeltaEvaluation,
  type ApiResearchOfflineEvaluation,
  type ApiResearchRetrievalIndexStatus,
  createResearchExperimentPlan,
  evaluateResearchExperimentGate,
  freezeResearchExperimentCohort,
  getResearchDeliveryExportDiagnostics,
  getResearchExperimentControlPlane,
  getResearchExperimentOrchestration,
  getResearchExperimentRuntimeConfig,
  getResearchExperimentRuntimeSnapshot,
  getResearchFollowupDeltaEvaluation,
  getResearchOfflineEvaluation,
  getResearchRetrievalIndexStatus,
  lockResearchExperimentBaseline,
  promoteResearchExperimentRollout,
  rebuildResearchRetrievalIndex,
  revokeResearchExperimentRollout,
} from "@/lib/api";

export function useResearchCenterExperimentController() {
  const [offlineEvaluation, setOfflineEvaluation] = useState<ApiResearchOfflineEvaluation | null>(null);
  const [offlineEvaluationLoading, setOfflineEvaluationLoading] = useState(true);
  const [offlineEvaluationRefreshing, setOfflineEvaluationRefreshing] = useState(false);
  const [experimentControlPlane, setExperimentControlPlane] = useState<ApiResearchExperimentControlPlane | null>(null);
  const [followupDeltaEvaluation, setFollowupDeltaEvaluation] = useState<ApiResearchFollowupDeltaEvaluation | null>(null);
  const [deliveryExportDiagnostics, setDeliveryExportDiagnostics] = useState<ApiResearchDeliveryExportDiagnostics | null>(null);
  const [experimentOrchestration, setExperimentOrchestration] = useState<ApiResearchExperimentOrchestration | null>(null);
  const [experimentRuntimeSnapshot, setExperimentRuntimeSnapshot] = useState<ApiResearchExperimentRuntimeSnapshot | null>(null);
  const [experimentRuntimeConfig, setExperimentRuntimeConfig] = useState<ApiResearchExperimentEffectiveRuntimeConfig | null>(null);
  const [experimentRuntimeAllConfig, setExperimentRuntimeAllConfig] = useState<ApiResearchExperimentEffectiveRuntimeConfig | null>(null);
  const [controlPlaneLoading, setControlPlaneLoading] = useState(true);
  const [controlPlaneRefreshing, setControlPlaneRefreshing] = useState(false);
  const [experimentPlanName, setExperimentPlanName] = useState("");
  const [experimentLaneKey, setExperimentLaneKey] = useState<ApiResearchExperimentPlan["lane_key"]>("query_recovery");
  const [experimentStrategyFamily, setExperimentStrategyFamily] = useState<ApiResearchExperimentPlan["strategy_family"]>("query_plan");
  const [experimentCandidateLabel, setExperimentCandidateLabel] = useState("");
  const [experimentMinSampleSize, setExperimentMinSampleSize] = useState("6");
  const [experimentMinUpliftPoints, setExperimentMinUpliftPoints] = useState("0");
  const [experimentPlanActionKey, setExperimentPlanActionKey] = useState("");
  const [experimentPlanMessage, setExperimentPlanMessage] = useState("");
  const [experimentPlanError, setExperimentPlanError] = useState("");
  const [retrievalIndexStatus, setRetrievalIndexStatus] = useState<ApiResearchRetrievalIndexStatus | null>(null);
  const [retrievalIndexLoading, setRetrievalIndexLoading] = useState(true);
  const [retrievalIndexRebuilding, setRetrievalIndexRebuilding] = useState(false);
  const [retrievalIndexMessage, setRetrievalIndexMessage] = useState("");
  const [retrievalIndexError, setRetrievalIndexError] = useState("");

  const refreshOfflineEvaluation = async () => {
    setOfflineEvaluationRefreshing(true);
    try {
      const evaluation = await getResearchOfflineEvaluation(6);
      setOfflineEvaluation(evaluation);
      return evaluation;
    } finally {
      setOfflineEvaluationLoading(false);
      setOfflineEvaluationRefreshing(false);
    }
  };

  const refreshRetrievalIndexStatus = async () => {
    const status = await getResearchRetrievalIndexStatus();
    setRetrievalIndexStatus(status);
    setRetrievalIndexLoading(false);
    return status;
  };

  const refreshControlPlaneDiagnostics = async () => {
    setControlPlaneRefreshing(true);
    try {
      const [
        controlPlane,
        followupDelta,
        exportDiagnostics,
        orchestration,
        runtimeSnapshot,
        runtimeConfig,
        runtimeAllConfig,
      ] = await Promise.all([
        getResearchExperimentControlPlane(),
        getResearchFollowupDeltaEvaluation(6),
        getResearchDeliveryExportDiagnostics(8),
        getResearchExperimentOrchestration(),
        getResearchExperimentRuntimeSnapshot(),
        getResearchExperimentRuntimeConfig("retrieval_search"),
        getResearchExperimentRuntimeConfig("all"),
      ]);
      setExperimentControlPlane(controlPlane);
      setFollowupDeltaEvaluation(followupDelta);
      setDeliveryExportDiagnostics(exportDiagnostics);
      setExperimentOrchestration(orchestration);
      setExperimentRuntimeSnapshot(runtimeSnapshot);
      setExperimentRuntimeConfig(runtimeConfig);
      setExperimentRuntimeAllConfig(runtimeAllConfig);
      return [controlPlane, followupDelta, exportDiagnostics, orchestration, runtimeSnapshot, runtimeConfig, runtimeAllConfig] as const;
    } finally {
      setControlPlaneLoading(false);
      setControlPlaneRefreshing(false);
    }
  };

  useEffect(() => {
    let active = true;
    setOfflineEvaluationLoading(true);
    getResearchOfflineEvaluation(6)
      .then((res) => {
        if (!active) return;
        setOfflineEvaluation(res);
      })
      .catch(() => {
        if (!active) return;
        setOfflineEvaluation(null);
      })
      .finally(() => {
        if (!active) return;
        setOfflineEvaluationLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setControlPlaneLoading(true);
    Promise.all([
      getResearchExperimentControlPlane(),
      getResearchFollowupDeltaEvaluation(6),
      getResearchDeliveryExportDiagnostics(8),
      getResearchExperimentOrchestration(),
      getResearchExperimentRuntimeSnapshot(),
      getResearchExperimentRuntimeConfig("retrieval_search"),
      getResearchExperimentRuntimeConfig("all"),
    ])
      .then(([controlPlane, followupDelta, exportDiagnostics, orchestration, runtimeSnapshot, runtimeConfig, runtimeAllConfig]) => {
        if (!active) return;
        setExperimentControlPlane(controlPlane);
        setFollowupDeltaEvaluation(followupDelta);
        setDeliveryExportDiagnostics(exportDiagnostics);
        setExperimentOrchestration(orchestration);
        setExperimentRuntimeSnapshot(runtimeSnapshot);
        setExperimentRuntimeConfig(runtimeConfig);
        setExperimentRuntimeAllConfig(runtimeAllConfig);
      })
      .finally(() => {
        if (!active) return;
        setControlPlaneLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    let active = true;
    setRetrievalIndexLoading(true);
    getResearchRetrievalIndexStatus()
      .then((res) => {
        if (!active) return;
        setRetrievalIndexStatus(res);
        setRetrievalIndexError("");
      })
      .catch(() => {
        if (!active) return;
        setRetrievalIndexStatus(null);
        setRetrievalIndexError("Retrieval index 状态暂时无法读取。");
      })
      .finally(() => {
        if (!active) return;
        setRetrievalIndexLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  const handleCreateExperimentPlan = async () => {
    const name = experimentPlanName.trim();
    const candidateLabel = experimentCandidateLabel.trim();
    if (!name || !candidateLabel) {
      setExperimentPlanError("请先补齐实验计划名称和候选策略标签。");
      return;
    }
    setExperimentPlanActionKey("create");
    setExperimentPlanError("");
    setExperimentPlanMessage("");
    try {
      const parsedSampleSize = Number(experimentMinSampleSize);
      const parsedUplift = Number(experimentMinUpliftPoints);
      await createResearchExperimentPlan({
        name,
        lane_key: experimentLaneKey,
        strategy_family: experimentStrategyFamily,
        candidate_label: candidateLabel,
        gate_config: {
          minimum_sample_size: Number.isFinite(parsedSampleSize)
            ? Math.min(500, Math.max(1, Math.round(parsedSampleSize)))
            : 6,
          minimum_uplift_points: Number.isFinite(parsedUplift)
            ? Math.min(100, Math.max(-100, Math.round(parsedUplift)))
            : 0,
        },
      });
      await refreshControlPlaneDiagnostics();
      setExperimentPlanName("");
      setExperimentCandidateLabel("");
      setExperimentPlanMessage("实验计划已创建，可继续冻结 cohort。");
    } catch {
      setExperimentPlanError("创建实验计划失败，请检查配置后重试。");
    } finally {
      setExperimentPlanActionKey("");
    }
  };

  const handleExperimentPlanAction = async (
    plan: ApiResearchExperimentPlan,
    action: "freeze" | "lock" | "gate" | "promote" | "revoke",
  ) => {
    setExperimentPlanActionKey(`${plan.id}:${action}`);
    setExperimentPlanError("");
    setExperimentPlanMessage("");
    try {
      if (action === "freeze") {
        await freezeResearchExperimentCohort(plan.id);
        setExperimentPlanMessage("Cohort 已冻结。");
      } else if (action === "lock") {
        await lockResearchExperimentBaseline(plan.id);
        setExperimentPlanMessage("Baseline 已锁定。");
      } else if (action === "gate") {
        await evaluateResearchExperimentGate(plan.id);
        setExperimentPlanMessage("Rollout gate 已完成判定。");
      } else if (action === "promote") {
        await promoteResearchExperimentRollout(plan.id, "UI confirmed after rollout gate allowed.");
        setExperimentPlanMessage("Rollout manifest 已确认。");
      } else {
        await revokeResearchExperimentRollout(plan.id, "UI revoked rollout manifest.");
        setExperimentPlanMessage("Rollout manifest 已撤回。");
      }
      await refreshControlPlaneDiagnostics();
    } catch {
      setExperimentPlanError("实验编排动作失败，当前状态可能不满足前置条件。");
    } finally {
      setExperimentPlanActionKey("");
    }
  };

  const handleRebuildRetrievalIndex = async (reset = false) => {
    setRetrievalIndexRebuilding(true);
    setRetrievalIndexMessage("");
    setRetrievalIndexError("");
    try {
      const result = await rebuildResearchRetrievalIndex({
        batch_size: 200,
        max_chunks: reset ? null : 400,
        resume: !reset,
        reset,
      });
      await refreshRetrievalIndexStatus();
      setRetrievalIndexMessage(result.message || (result.completed ? "Retrieval index 已重建完成。" : "Retrieval index 已写入增量断点。"));
    } catch {
      setRetrievalIndexError("Retrieval index 重建失败，请稍后重试。");
    } finally {
      setRetrievalIndexRebuilding(false);
    }
  };

  return {
    offlineEvaluation,
    offlineEvaluationLoading,
    offlineEvaluationRefreshing,
    followupDeltaEvaluation,
    deliveryExportDiagnostics,
    experimentControlPlane,
    experimentOrchestration,
    experimentRuntimeSnapshot,
    experimentRuntimeConfig,
    experimentRuntimeAllConfig,
    controlPlaneLoading,
    controlPlaneRefreshing,
    experimentPlanName,
    setExperimentPlanName,
    experimentLaneKey,
    setExperimentLaneKey,
    experimentStrategyFamily,
    setExperimentStrategyFamily,
    experimentCandidateLabel,
    setExperimentCandidateLabel,
    experimentMinSampleSize,
    setExperimentMinSampleSize,
    experimentMinUpliftPoints,
    setExperimentMinUpliftPoints,
    experimentPlanActionKey,
    experimentPlanMessage,
    experimentPlanError,
    retrievalIndexStatus,
    retrievalIndexLoading,
    retrievalIndexRebuilding,
    retrievalIndexMessage,
    retrievalIndexError,
    refreshOfflineEvaluation,
    refreshRetrievalIndexStatus,
    refreshControlPlaneDiagnostics,
    handleCreateExperimentPlan,
    handleExperimentPlanAction,
    handleRebuildRetrievalIndex,
  };
}
