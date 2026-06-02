"use client";

import Link from "next/link";
import type { ApiResearchExperimentPlan } from "@/lib/api";
import type { useResearchCenterController } from "@/components/research/use-research-center-controller";
import {
  experimentGateDecisionLabel,
  experimentGateDecisionTone,
  experimentLaneStatusLabel,
  experimentLaneStatusTone,
  experimentPlanStatusLabel,
  experimentPlanStatusTone,
  experimentRuntimeStatusLabel,
  experimentRuntimeStatusTone,
  exportDeltaTrendTone,
  formatWatchlistTime,
  offlineEvaluationStatusLabel,
  offlineEvaluationStatusTone,
  runtimeCacheHealthLabel,
  runtimeCacheHealthTone,
} from "@/components/research/research-center-utils";
import { sanitizeExternalDisplayText } from "@/lib/commercial-risk-copy";

type ResearchCenterController = ReturnType<typeof useResearchCenterController>;
type ResearchCenterExperimentControlSectionProps = ResearchCenterController["experimentControlSectionProps"];

export function ResearchCenterExperimentControlSection({
  t,
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
}: ResearchCenterExperimentControlSectionProps) {
  return (
      <section className="af-glass rounded-[30px] p-5 md:p-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="max-w-3xl">
            <p className="af-kicker">质量复核</p>
            <h3 className="mt-2 text-xl font-semibold text-[var(--af-text-primary)]">质量复核评估</h3>
            <p className="mt-2 text-sm leading-6 text-[var(--af-text-tertiary)]">
              将检索、账户支撑、章节依据和方案/项目建议书交付质量集中展示，方便每轮修订后快速回看质量变化。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-1 text-xs font-medium text-[var(--af-text-tertiary)]">
              扫描研报 · {offlineEvaluation?.total_reports ?? 0}
            </div>
            <div className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-1 text-xs font-medium text-[var(--af-text-tertiary)]">
              可评估 · {offlineEvaluation?.evaluated_reports ?? 0}
            </div>
            <div className="rounded-full border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-1 text-xs font-medium text-[var(--af-text-tertiary)]">
              Follow-up · {followupDeltaEvaluation?.followup_reports ?? 0}
            </div>
            {(offlineEvaluation?.invalid_payloads ?? 0) > 0 ? (
              <div className="rounded-full border border-[color-mix(in_srgb,var(--af-warning)_30%,var(--af-border-subtle))] bg-[color-mix(in_srgb,var(--af-warning)_10%,var(--af-surface-muted))] px-3 py-1 text-xs font-medium text-[var(--af-warning)]">
                schema 异常 · {offlineEvaluation?.invalid_payloads ?? 0}
              </div>
            ) : null}
            <button
              type="button"
              onClick={() => void refreshOfflineEvaluation()}
              disabled={offlineEvaluationRefreshing}
              className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
            >
              {offlineEvaluationRefreshing ? "刷新中..." : "刷新评估"}
            </button>
            <button
              type="button"
              onClick={() => void refreshControlPlaneDiagnostics()}
              disabled={controlPlaneRefreshing}
              className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
            >
              {controlPlaneRefreshing ? "刷新中..." : "刷新控制面"}
            </button>
          </div>
        </div>

        {offlineEvaluationLoading ? (
          <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">{t("common.loading", "加载中")}</p>
        ) : (
          <>
            {offlineEvaluation?.generated_at ? (
              <p className="mt-3 text-xs text-[var(--af-text-tertiary)]">更新于 · {formatWatchlistTime(offlineEvaluation.generated_at)}</p>
            ) : null}

            <div className="mt-4 rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-[var(--af-text-primary)]">Retrieval index 增量重建</p>
                  <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">
                    统一查看 rebuild / cache / recovery 的运行时状态，辅助断点续建和异常恢复。
                  </p>
                </div>
                <span
                  className={`rounded-full px-3 py-1 text-[11px] font-semibold ${runtimeCacheHealthTone(
                    retrievalIndexStatus?.cache_health,
                  )}`}
                >
                  {runtimeCacheHealthLabel(retrievalIndexStatus?.cache_health)}
                </span>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => void refreshRetrievalIndexStatus()}
                    className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                    disabled={retrievalIndexLoading || retrievalIndexRebuilding}
                  >
                    刷新状态
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleRebuildRetrievalIndex(false)}
                    className="af-btn af-btn-primary px-3 py-1.5 text-xs"
                    disabled={retrievalIndexRebuilding}
                  >
                    {retrievalIndexRebuilding ? "重建中..." : "继续增量重建"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void handleRebuildRetrievalIndex(true)}
                    className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                    disabled={retrievalIndexRebuilding}
                  >
                    重置重建
                  </button>
                </div>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-3 xl:grid-cols-6">
                {[
                  { label: "断点状态", value: retrievalIndexStatus?.checkpoint_status || "idle" },
                  { label: "已持久化", value: String(retrievalIndexStatus?.persisted_chunk_count ?? 0) },
                  { label: "父块路由", value: String(retrievalIndexStatus?.parent_link_count ?? 0) },
                  { label: "孤儿子块", value: String(retrievalIndexStatus?.orphan_child_count ?? 0) },
                  { label: "待处理", value: String(retrievalIndexStatus?.remaining_chunks ?? 0) },
                  { label: "缓存复用", value: `${retrievalIndexStatus?.persisted_reuse_percent ?? 0}%` },
                ].map((item) => (
                  <div key={item.label} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">{item.label}</p>
                    <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{item.value}</p>
                  </div>
                ))}
              </div>
              <div className="mt-4">
                <div className="flex items-center justify-between gap-3 text-xs text-[var(--af-text-tertiary)]">
                  <span>
                    {retrievalIndexStatus?.indexed_chunks ?? 0}/{retrievalIndexStatus?.total_chunks ?? 0} chunks
                  </span>
                  <span>{retrievalIndexStatus?.progress_percent ?? 0}%</span>
                </div>
                <div className="mt-2 h-2 overflow-hidden rounded-full bg-[var(--af-surface-inset)]">
                  <div
                    className="h-full rounded-full bg-[var(--af-success)]"
                    style={{ width: `${Math.max(0, Math.min(retrievalIndexStatus?.progress_percent ?? 0, 100))}%` }}
                  />
                </div>
              </div>
              <div className="mt-4 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-3 text-xs leading-5 text-[var(--af-text-secondary)]">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-semibold text-[var(--af-text-primary)]">Recovery</span>
                  <span className="rounded-full bg-[var(--af-surface-elevated)] px-2 py-0.5 font-medium text-[var(--af-text-secondary)]">
                    {retrievalIndexStatus?.recovery_mode || "none"}
                  </span>
                  {retrievalIndexStatus?.checkpoint_resume_ready ? (
                    <span className="rounded-full bg-[color-mix(in_srgb,var(--af-info)_12%,var(--af-surface-muted))] px-2 py-0.5 font-medium text-[var(--af-info)]">
                      resume ready
                    </span>
                  ) : null}
                </div>
                <p className="mt-2">
                  {retrievalIndexStatus?.recovery_recommendation || "当前暂无恢复建议。"}
                </p>
              </div>
              {retrievalIndexMessage ? <p className="mt-3 text-sm text-[var(--af-success)]">{retrievalIndexMessage}</p> : null}
              {retrievalIndexError ? <p className="mt-3 text-sm text-[var(--af-danger)]">{retrievalIndexError}</p> : null}
            </div>

            <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr),minmax(0,1fr)]">
              <div className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-[var(--af-text-primary)]">Query / routing / reranker A/B 控制面</p>
                    <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">
                      同屏比较 shadow cohort 与同样本 reranker 离线对照，方便判断下一轮默认策略。
                    </p>
                  </div>
                  <span className="text-[11px] uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">Control Plane</span>
                </div>
                {controlPlaneLoading ? (
                  <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">{t("common.loading", "加载中")}</p>
                ) : experimentControlPlane?.lanes?.length ? (
                  <div className="mt-4 space-y-3">
                    {experimentControlPlane.lanes.map((lane) => (
                      <div key={lane.key} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div>
                            <p className="text-sm font-semibold text-[var(--af-text-primary)]">{lane.label}</p>
                            <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">{lane.metric_label}</p>
                          </div>
                          <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${experimentLaneStatusTone(lane.status)}`}>
                            {experimentLaneStatusLabel(lane.status)}
                          </span>
                        </div>
                        <div className="mt-3 grid gap-2 md:grid-cols-2">
                          {[lane.baseline, lane.candidate].map((arm) => (
                            <div key={arm.key} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                              <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">
                                {arm.role === "baseline" ? "Baseline" : "Candidate"}
                              </p>
                              <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{arm.label}</p>
                              <p className="mt-2 text-2xl font-semibold tracking-[-0.04em] text-[var(--af-text-primary)]">{arm.percent}%</p>
                              <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
                                {arm.numerator}/{arm.denominator}
                              </p>
                            </div>
                          ))}
                        </div>
                        <p className="mt-3 text-xs leading-5 text-[var(--af-text-secondary)]">
                          候选相对基线 {lane.uplift_points >= 0 ? "+" : ""}
                          {lane.uplift_points} pt。{lane.interpretation}
                        </p>
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">当前暂无可比较控制面样本。</p>
                )}
              </div>

              <div className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-[var(--af-text-primary)]">Follow-up delta 离线评估</p>
                    <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">
                      检查标题/摘要 delta、影响章节路由和官方证据支撑是否真正闭环。
                    </p>
                  </div>
                  <span className="text-[11px] uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">Delta Eval</span>
                </div>
                {controlPlaneLoading ? (
                  <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">{t("common.loading", "加载中")}</p>
                ) : followupDeltaEvaluation?.metrics?.length ? (
                  <>
                    <div className="mt-4 grid gap-3 md:grid-cols-2">
                      {followupDeltaEvaluation.metrics.map((metric) => (
                        <div
                          key={metric.key}
                          className={`rounded-2xl border px-3 py-3 ${offlineEvaluationStatusTone(metric.status)}`}
                        >
                          <p className="text-sm font-semibold">{metric.label}</p>
                          <p className="mt-2 text-2xl font-semibold tracking-[-0.04em]">{metric.percent}%</p>
                          <p className="mt-1 text-xs">
                            当前 {metric.numerator}/{metric.denominator} · 基准 {Math.round(metric.benchmark * 100)}%
                          </p>
                        </div>
                      ))}
                    </div>
                    {followupDeltaEvaluation.weakest_reports?.length ? (
                      <div className="mt-4 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">待补样本</p>
                        <div className="mt-2 space-y-2">
                          {followupDeltaEvaluation.weakest_reports.slice(0, 3).map((item) => (
                            <div key={item.entry_id} className="text-sm leading-6 text-[var(--af-text-secondary)]">
                              《{sanitizeExternalDisplayText(item.report_title || item.entry_title)}》 ·{" "}
                              {item.weak_reasons.slice(0, 2).map(sanitizeExternalDisplayText).join(" / ")}
                            </div>
                          ))}
                        </div>
                      </div>
                    ) : null}
                  </>
                ) : (
                  <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">当前暂无 follow-up delta 样本。</p>
                )}
              </div>
            </div>

            <div
              className="mt-4 rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4"
              data-screenshot-anchor="research-experiment-control-plane"
            >
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-[var(--af-text-primary)]">实验编排层</p>
                  <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">
                    固化 cohort、锁定版本 baseline，并用 rollout gate 决定候选策略是否进入默认路径。
                  </p>
                </div>
                <span className="text-[11px] uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">Orchestration</span>
              </div>
              <div className="mt-4 grid gap-3 md:grid-cols-5 xl:grid-cols-10">
                {[
                  { label: "实验计划", value: String(experimentOrchestration?.total_plans ?? 0) },
                  { label: "已冻结", value: String(experimentOrchestration?.frozen_plan_count ?? 0) },
                  { label: "已锁定", value: String(experimentOrchestration?.locked_plan_count ?? 0) },
                  { label: "Gate 放行", value: String(experimentOrchestration?.allowed_plan_count ?? 0) },
                  { label: "Gate 阻塞", value: String(experimentOrchestration?.blocked_plan_count ?? 0) },
                  { label: "待观察", value: String(experimentOrchestration?.hold_plan_count ?? 0) },
                  { label: "已确认", value: String(experimentOrchestration?.promoted_plan_count ?? 0) },
                  { label: "已撤回", value: String(experimentOrchestration?.revoked_plan_count ?? 0) },
                  { label: "生效策略", value: String(experimentOrchestration?.active_policy_count ?? 0) },
                  { label: "冲突策略", value: String(experimentOrchestration?.active_policy_conflict_count ?? 0) },
                ].map((item) => (
                  <div key={item.label} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                    <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">{item.label}</p>
                    <p className="mt-1 text-lg font-semibold text-[var(--af-text-primary)]">{item.value}</p>
                  </div>
                ))}
              </div>

              <div className="mt-4 grid gap-3 xl:grid-cols-[minmax(0,1.1fr),minmax(0,0.9fr)]">
                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">新实验计划</p>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <label className="block text-xs font-medium text-[var(--af-text-secondary)]">
                      计划名称
                      <input
                        value={experimentPlanName}
                        onChange={(event) => setExperimentPlanName(event.target.value)}
                        className="af-input mt-1 w-full bg-[var(--af-surface-elevated)]"
                        placeholder="例：CrossEncoder reranker rollout"
                      />
                    </label>
                    <label className="block text-xs font-medium text-[var(--af-text-secondary)]">
                      候选策略标签
                      <input
                        value={experimentCandidateLabel}
                        onChange={(event) => setExperimentCandidateLabel(event.target.value)}
                        className="af-input mt-1 w-full bg-[var(--af-surface-elevated)]"
                        placeholder="例：cross-encoder-v1"
                      />
                    </label>
                    <label className="block text-xs font-medium text-[var(--af-text-secondary)]">
                      Lane
                      <select
                        value={experimentLaneKey}
                        onChange={(event) => {
                          const nextLane = event.target.value as ApiResearchExperimentPlan["lane_key"];
                          setExperimentLaneKey(nextLane);
                          setExperimentStrategyFamily(
                            nextLane === "query_recovery"
                              ? "query_plan"
                              : nextLane === "routing_followup"
                                ? "routing_policy"
                                : "reranker",
                          );
                        }}
                        className="af-input mt-1 w-full bg-[var(--af-surface-elevated)]"
                      >
                        <option value="query_recovery">Query recovery</option>
                        <option value="routing_followup">Routing follow-up</option>
                        <option value="reranker_official_recall">Reranker official recall</option>
                      </select>
                    </label>
                    <label className="block text-xs font-medium text-[var(--af-text-secondary)]">
                      策略族
                      <select
                        value={experimentStrategyFamily}
                        onChange={(event) => setExperimentStrategyFamily(event.target.value as ApiResearchExperimentPlan["strategy_family"])}
                        className="af-input mt-1 w-full bg-[var(--af-surface-elevated)]"
                      >
                        <option value="query_plan">Query plan</option>
                        <option value="routing_policy">Routing policy</option>
                        <option value="reranker">Reranker</option>
                      </select>
                    </label>
                    <label className="block text-xs font-medium text-[var(--af-text-secondary)]">
                      最小样本量
                      <input
                        type="number"
                        min={1}
                        max={500}
                        value={experimentMinSampleSize}
                        onChange={(event) => setExperimentMinSampleSize(event.target.value)}
                        className="af-input mt-1 w-full bg-[var(--af-surface-elevated)]"
                      />
                    </label>
                    <label className="block text-xs font-medium text-[var(--af-text-secondary)]">
                      最小 uplift
                      <input
                        type="number"
                        min={-100}
                        max={100}
                        value={experimentMinUpliftPoints}
                        onChange={(event) => setExperimentMinUpliftPoints(event.target.value)}
                        className="af-input mt-1 w-full bg-[var(--af-surface-elevated)]"
                      />
                    </label>
                  </div>
                  <div className="mt-3 flex flex-wrap items-center gap-3">
                    <button
                      type="button"
                      onClick={() => void handleCreateExperimentPlan()}
                      className="af-btn af-btn-primary px-4 py-2 text-sm"
                      disabled={experimentPlanActionKey === "create"}
                    >
                      创建实验计划
                    </button>
                    {experimentPlanMessage ? <span className="text-sm text-[var(--af-success)]">{experimentPlanMessage}</span> : null}
                    {experimentPlanError ? <span className="text-sm text-[var(--af-danger)]">{experimentPlanError}</span> : null}
                  </div>
                </div>

                <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                  <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">编排摘要</p>
                  {experimentOrchestration?.summary_lines?.length ? (
                    <div className="mt-3 space-y-2">
                      {experimentOrchestration.summary_lines.map((line) => (
                        <p key={line} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                          {sanitizeExternalDisplayText(line)}
                        </p>
                      ))}
                    </div>
                  ) : (
                    <p className="mt-3 text-sm text-[var(--af-text-tertiary)]">创建计划后会在这里显示冻结、锁定和 gate 结果。</p>
                  )}
                  {experimentOrchestration?.active_policies?.length ? (
                    <div className="mt-3 space-y-2">
                      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">Active policy registry</p>
                      {experimentOrchestration.active_policies.map((policy) => (
                        <div key={`${policy.lane_key}-${policy.plan_id}`} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-sm font-semibold text-[var(--af-text-primary)]">{sanitizeExternalDisplayText(policy.candidate_label)}</p>
                            <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${policy.conflict_plan_ids.length ? "af-chip af-chip-danger" : "af-chip af-chip-success"}`}>
                              {policy.conflict_plan_ids.length ? "同 lane 冲突" : "当前生效"}
                            </span>
                          </div>
                          <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">
                            {policy.lane_key} · {policy.promoted_version_label || "local-dev"} · {policy.candidate_percent}% · uplift{" "}
                            {policy.observed_uplift_points >= 0 ? "+" : ""}
                            {policy.observed_uplift_points} pt
                          </p>
                        </div>
                      ))}
                    </div>
                  ) : null}
                  {experimentRuntimeSnapshot ? (
                    <div className="mt-3 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">
                          Runtime strategy snapshot
                        </p>
                        <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${experimentRuntimeStatusTone(experimentRuntimeSnapshot.status)}`}>
                          {experimentRuntimeStatusLabel(experimentRuntimeSnapshot.status)}
                        </span>
                      </div>
                      <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                        {experimentRuntimeSnapshot.summary_lines[0] || "当前没有可接入的运行时策略。"}
                      </p>
                      {experimentRuntimeAllConfig ? (() => {
                        const queryRuntime = (experimentRuntimeAllConfig.effective_config["query_generation"] || {}) as Record<string, unknown>;
                        const rerankerRuntime = (experimentRuntimeAllConfig.effective_config["source_reranker"] || {}) as Record<string, unknown>;
                        return (
                          <div className="mt-2 grid gap-2 md:grid-cols-4">
                            {[
                              {
                                label: "report query",
                                value: String(queryRuntime["query_recovery_enabled"] ?? false),
                              },
                              {
                                label: "corrective",
                                value: String(queryRuntime["corrective_query_limit"] ?? 0),
                              },
                              {
                                label: "source reranker",
                                value: String(rerankerRuntime["reranker_adapter"] ?? "local_rrf"),
                              },
                              {
                                label: "top k",
                                value: String(rerankerRuntime["recall_at_k"] ?? 5),
                              },
                            ].map((item) => (
                              <div key={item.label} className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-2.5 py-2">
                                <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">{item.label}</p>
                                <p className="mt-1 truncate text-xs font-semibold text-[var(--af-text-secondary)]">{sanitizeExternalDisplayText(item.value)}</p>
                              </div>
                            ))}
                          </div>
                        );
                      })() : null}
                      {experimentRuntimeSnapshot.strategies.length ? (
                        <div className="mt-2 space-y-2">
                          {experimentRuntimeSnapshot.strategies.slice(0, 3).map((strategy) => {
                            const configPreview = Object.entries(strategy.runtime_config)
                              .slice(0, 4)
                              .map(([key, value]) => `${key}: ${String(value)}`)
                              .join(" / ");
                            return (
                              <div key={`${strategy.lane_key}-${strategy.plan_id}`} className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <p className="text-sm font-semibold text-[var(--af-text-primary)]">{sanitizeExternalDisplayText(strategy.candidate_label)}</p>
                                  <span className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">{strategy.lane_key}</span>
                                </div>
                                <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">{sanitizeExternalDisplayText(configPreview)}</p>
                              </div>
                            );
                          })}
                        </div>
                      ) : null}
                      {experimentRuntimeConfig ? (
                        <div className="mt-2 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">
                              Effective retrieval config
                            </p>
                            <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${experimentRuntimeStatusTone(experimentRuntimeConfig.status)}`}>
                              {experimentRuntimeStatusLabel(experimentRuntimeConfig.status)}
                            </span>
                          </div>
                          <div className="mt-2 grid gap-2 md:grid-cols-2">
                            {[
                              {
                                label: "parent boost",
                                value: String(experimentRuntimeConfig.effective_config["parent_block_boost"] ?? "1"),
                              },
                              {
                                label: "official bias",
                                value: String(experimentRuntimeConfig.effective_config["official_source_bias"] ?? true),
                              },
                              {
                                label: "reranker",
                                value: String(experimentRuntimeConfig.effective_config["reranker_adapter"] ?? "local_rrf"),
                              },
                              {
                                label: "applied lanes",
                                value: experimentRuntimeConfig.applied_lanes.length
                                  ? experimentRuntimeConfig.applied_lanes.join(" / ")
                                  : "fallback",
                              },
                            ].map((item) => (
                              <div key={item.label} className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-2.5 py-2">
                                <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">{item.label}</p>
                                <p className="mt-1 truncate text-xs font-semibold text-[var(--af-text-secondary)]">{sanitizeExternalDisplayText(item.value)}</p>
                              </div>
                            ))}
                          </div>
                          <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">
                            {experimentRuntimeConfig.summary_lines[0] || "检索调用路径保持本地默认策略。"}
                          </p>
                        </div>
                      ) : null}
                      {experimentRuntimeAllConfig ? (() => {
                        const queryRuntime = (experimentRuntimeAllConfig.effective_config["query_generation"] || {}) as Record<string, unknown>;
                        const rerankerRuntime = (experimentRuntimeAllConfig.effective_config["source_reranker"] || {}) as Record<string, unknown>;
                        return (
                          <div className="mt-2 rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">
                                Report generation runtime
                              </p>
                              <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${experimentRuntimeStatusTone(experimentRuntimeAllConfig.status)}`}>
                                {experimentRuntimeStatusLabel(experimentRuntimeAllConfig.status)}
                              </span>
                            </div>
                            <div className="mt-2 grid gap-2 md:grid-cols-2">
                              {[
                                {
                                  label: "query recovery",
                                  value: String(queryRuntime["query_recovery_enabled"] ?? false),
                                },
                                {
                                  label: "corrective limit",
                                  value: String(queryRuntime["corrective_query_limit"] ?? 0),
                                },
                                {
                                  label: "source reranker",
                                  value: String(rerankerRuntime["reranker_adapter"] ?? "local_rrf"),
                                },
                                {
                                  label: "reranker top k",
                                  value: String(rerankerRuntime["recall_at_k"] ?? 5),
                                },
                              ].map((item) => (
                                <div key={item.label} className="rounded-xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-2.5 py-2">
                                  <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">{item.label}</p>
                                  <p className="mt-1 truncate text-xs font-semibold text-[var(--af-text-secondary)]">{sanitizeExternalDisplayText(item.value)}</p>
                                </div>
                              ))}
                            </div>
                            <p className="mt-2 text-xs leading-5 text-[var(--af-text-tertiary)]">
                              {experimentRuntimeAllConfig.summary_lines[0] || "研报生成保持本地默认策略。"}
                            </p>
                          </div>
                        );
                      })() : null}
                      {experimentRuntimeSnapshot.warnings.length ? (
                        <p className="mt-2 text-xs leading-5 text-[var(--af-warning)]">
                          {experimentRuntimeSnapshot.warnings.slice(0, 2).map(sanitizeExternalDisplayText).join("；")}
                        </p>
                      ) : null}
                    </div>
                  ) : null}
                </div>
              </div>

              {controlPlaneLoading ? (
                <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">{t("common.loading", "加载中")}</p>
              ) : experimentOrchestration?.plans?.length ? (
                <div className="mt-4 space-y-3">
                  {experimentOrchestration.plans.map((plan) => {
                    const latestGate = plan.latest_gate;
                    const actionBusy = experimentPlanActionKey.startsWith(`${plan.id}:`);
                    const canFreeze = !plan.baseline_locked_at;
                    const canLock = Boolean(plan.cohort_frozen_at) && !plan.baseline_locked_at;
                    const canEvaluate = Boolean(plan.baseline_locked_at);
                    const activeRollout = plan.rollout_manifest?.decision === "promoted";
                    const canPromote = latestGate?.decision === "allow" && !activeRollout;
                    const canRevoke = activeRollout;
                    return (
                      <div key={plan.id} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
                        <div className="flex flex-wrap items-start justify-between gap-3">
                          <div className="min-w-0 flex-1">
                            <p className="text-sm font-semibold text-[var(--af-text-primary)]">{sanitizeExternalDisplayText(plan.name)}</p>
                            <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">
                              {sanitizeExternalDisplayText(plan.candidate_label)} · {plan.lane_key} · {plan.strategy_family}
                            </p>
                          </div>
                          <div className="flex flex-wrap items-center gap-2">
                            <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${experimentPlanStatusTone(plan.status)}`}>
                              {experimentPlanStatusLabel(plan.status)}
                            </span>
                            <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${experimentGateDecisionTone(latestGate?.decision)}`}>
                              {experimentGateDecisionLabel(latestGate?.decision)}
                            </span>
                          </div>
                        </div>
                        <div className="mt-3 grid gap-2 md:grid-cols-4">
                          {[
                            { label: "Cohort", value: `${plan.cohort_size} 条` },
                            { label: "Baseline", value: plan.baseline_version_label || "未锁定" },
                            { label: "候选表现", value: latestGate ? `${latestGate.candidate_percent}%` : `${plan.baseline_lane?.candidate.percent ?? 0}%` },
                            { label: "Uplift", value: latestGate ? `${latestGate.observed_uplift_points >= 0 ? "+" : ""}${latestGate.observed_uplift_points} pt` : "未判定" },
                            { label: "Gate 历史", value: `${plan.gate_history_count} 次` },
                          ].map((item) => (
                            <div key={item.label} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                              <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">{item.label}</p>
                              <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{item.value}</p>
                            </div>
                          ))}
                        </div>
                        {plan.cohort_preview_titles.length ? (
                          <p className="mt-3 text-xs leading-5 text-[var(--af-text-tertiary)]">
                            样本预览：{plan.cohort_preview_titles.map(sanitizeExternalDisplayText).join(" / ")}
                          </p>
                        ) : null}
                        {latestGate?.reasons?.length ? (
                          <div className="mt-3 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                            <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">Gate reason</p>
                            <p className="mt-1 text-sm leading-6 text-[var(--af-text-secondary)]">
                              {latestGate.reasons.map(sanitizeExternalDisplayText).join("；")}
                            </p>
                          </div>
                        ) : null}
                        {plan.rollout_manifest ? (
                          <div className="mt-3 rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">
                                Rollout manifest
                              </p>
                              <span className={`rounded-full px-2.5 py-1 text-[11px] font-semibold ${plan.rollout_manifest.decision === "promoted" ? "af-chip af-chip-success" : "af-chip"}`}>
                                {plan.rollout_manifest.decision === "promoted" ? "已确认" : "已撤回"}
                              </span>
                            </div>
                            <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                              {sanitizeExternalDisplayText(plan.rollout_manifest.promoted_version_label || "local-dev")} ·{" "}
                              {plan.rollout_manifest.candidate_percent}% · uplift{" "}
                              {plan.rollout_manifest.observed_uplift_points >= 0 ? "+" : ""}
                              {plan.rollout_manifest.observed_uplift_points} pt · 样本 {plan.rollout_manifest.sample_size}
                            </p>
                            <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">
                              {plan.rollout_manifest.revoked_at
                                ? `撤回于 ${formatWatchlistTime(plan.rollout_manifest.revoked_at)}`
                                : plan.rollout_manifest.promoted_at
                                  ? `确认于 ${formatWatchlistTime(plan.rollout_manifest.promoted_at)}`
                                  : "尚未写入确认时间"}
                            </p>
                          </div>
                        ) : null}
                        <div className="mt-3 flex flex-wrap items-center gap-2">
                          <button
                            type="button"
                            onClick={() => void handleExperimentPlanAction(plan, "freeze")}
                            className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                            disabled={!canFreeze || actionBusy}
                          >
                            冻结 cohort
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleExperimentPlanAction(plan, "lock")}
                            className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                            disabled={!canLock || actionBusy}
                          >
                            锁定 baseline
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleExperimentPlanAction(plan, "gate")}
                            className="af-btn af-btn-primary px-3 py-1.5 text-xs"
                            disabled={!canEvaluate || actionBusy}
                          >
                            判定 rollout gate
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleExperimentPlanAction(plan, "promote")}
                            className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                            disabled={!canPromote || actionBusy}
                          >
                            确认 rollout
                          </button>
                          <button
                            type="button"
                            onClick={() => void handleExperimentPlanAction(plan, "revoke")}
                            className="af-btn af-btn-secondary border px-3 py-1.5 text-xs"
                            disabled={!canRevoke || actionBusy}
                          >
                            撤回 rollout
                          </button>
                          <span className="text-xs text-[var(--af-text-tertiary)]">
                            {plan.baseline_locked_at ? `锁定于 ${formatWatchlistTime(plan.baseline_locked_at)}` : "baseline 锁定后 cohort 不再变更"}
                          </span>
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">当前暂无实验计划。</p>
              )}
            </div>

            <div className="mt-4 rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <div className="flex flex-wrap items-center justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-[var(--af-text-primary)]">Delivery export diagnostics</p>
                  <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">
                    汇总导出归档的质量快照、追问影响摘要和相邻版本差异，观察趋势而不是只看单点结果。
                  </p>
                </div>
                <span className="text-[11px] uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">Export Trend</span>
              </div>
              {controlPlaneLoading ? (
                <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">{t("common.loading", "加载中")}</p>
              ) : deliveryExportDiagnostics ? (
                <>
                  <div className="mt-4 grid gap-3 md:grid-cols-4">
                    {[
                      { label: "导出归档", value: String(deliveryExportDiagnostics.total_archives) },
                      { label: "可比较样本", value: String(deliveryExportDiagnostics.analyzed_archives) },
                      { label: "质量快照", value: String(deliveryExportDiagnostics.archives_with_quality_snapshot) },
                      { label: "追问摘要", value: String(deliveryExportDiagnostics.archives_with_followup_summary) },
                    ].map((item) => (
                      <div key={item.label} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2">
                        <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">{item.label}</p>
                        <p className="mt-1 text-lg font-semibold text-[var(--af-text-primary)]">{item.value}</p>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1.05fr),minmax(0,0.95fr)]">
                    <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">历史趋势</p>
                      <div className="mt-3 space-y-2">
                        {deliveryExportDiagnostics.trend_points.slice(0, 5).map((point) => (
                          <div key={point.archive_id} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                            <div className="flex flex-wrap items-center justify-between gap-2">
                              <p className="text-sm font-semibold text-[var(--af-text-primary)]">{sanitizeExternalDisplayText(point.archive_name)}</p>
                              <span className="text-xs text-[var(--af-text-tertiary)]">{formatWatchlistTime(point.updated_at)}</span>
                            </div>
                            <p className="mt-2 text-xs leading-5 text-[var(--af-text-secondary)]">
                              方案/建议书 {point.solution_quality_percent}/{point.proposal_quality_percent} · 自修订{" "}
                              {point.self_review_gain_percent}% · 追问章节 {point.followup_impacted_section_count} · 差异章节{" "}
                              {point.changed_section_count}
                            </p>
                          </div>
                        ))}
                        {!deliveryExportDiagnostics.trend_points.length ? (
                          <p className="text-sm text-[var(--af-text-tertiary)]">当前暂无带诊断字段的导出归档。</p>
                        ) : null}
                      </div>
                    </div>
                    <div className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-3">
                      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">版本对比</p>
                      <div className="mt-3 space-y-2">
                        {deliveryExportDiagnostics.version_deltas.map((item) => (
                          <div key={item.key} className="rounded-2xl border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
                            <div className="flex items-center justify-between gap-3">
                              <p className="text-sm font-semibold text-[var(--af-text-primary)]">{item.label}</p>
                              <span className={`text-sm font-semibold ${exportDeltaTrendTone(item.trend)}`}>
                                {item.delta_value >= 0 ? "+" : ""}
                                {item.delta_value}
                              </span>
                            </div>
                            <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">{item.summary}</p>
                          </div>
                        ))}
                        {!deliveryExportDiagnostics.version_deltas.length ? (
                          <p className="text-sm text-[var(--af-text-tertiary)]">至少需要两份带诊断的导出归档，才能形成版本对比。</p>
                        ) : null}
                      </div>
                    </div>
                  </div>
                </>
              ) : (
                <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">导出诊断暂时无法读取。</p>
              )}
            </div>

            {offlineEvaluation?.metrics?.length ? (
              <div className="mt-4 grid gap-3 md:grid-cols-3">
                {offlineEvaluation.metrics.map((metric) => (
                  <div
                    key={metric.key}
                    className={`rounded-[24px] border p-4 shadow-[0_12px_30px_rgba(15,23,42,0.05)] ${offlineEvaluationStatusTone(metric.status)}`}
                  >
                    <div className="flex items-center justify-between gap-3">
                      <p className="text-sm font-semibold">{sanitizeExternalDisplayText(metric.label)}</p>
                      <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1 text-[11px] font-medium text-[var(--af-text-secondary)]">
                        {offlineEvaluationStatusLabel(metric.status)}
                      </span>
                    </div>
                    <p className="mt-3 text-3xl font-semibold tracking-[-0.05em]">{metric.percent}%</p>
                    <p className="mt-2 text-xs text-[var(--af-text-tertiary)]">
                      当前 {metric.numerator}/{metric.denominator} · 基准 {Math.round(metric.benchmark * 100)}%
                    </p>
                    <p className="mt-3 text-sm leading-6 text-[var(--af-text-secondary)]">
                      {sanitizeExternalDisplayText(metric.summary)}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">当前暂无质量复核样本。</p>
            )}

            <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,0.95fr),minmax(0,1.05fr)]">
              <div className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm font-semibold text-[var(--af-text-primary)]">回归摘要</p>
                  <span className="text-[11px] uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">Regression Notes</span>
                </div>
                {offlineEvaluation?.summary_lines?.length ? (
                  <div className="mt-3 space-y-2">
                    {offlineEvaluation.summary_lines.map((line) => (
                      <div key={line} className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2 text-sm leading-6 text-[var(--af-text-secondary)]">
                        {sanitizeExternalDisplayText(line)}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-[var(--af-text-tertiary)]">当前没有额外摘要。</p>
                )}
              </div>

              <div className="rounded-[24px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-[var(--af-text-primary)]">弱样本回归列表</p>
                    <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">优先处理目标账户缺支撑、章节配额未达标、检索命中偏弱和交付质量未过线的旧报告。</p>
                  </div>
                  <span className="text-[11px] uppercase tracking-[0.14em] text-[var(--af-text-tertiary)]">
                    Top {Math.min(offlineEvaluation?.weakest_reports?.length ?? 0, 4)}
                  </span>
                </div>
                {offlineEvaluation?.weakest_reports?.length ? (
                  <div className="mt-3 space-y-3">
                    {offlineEvaluation.weakest_reports.slice(0, 4).map((item) => {
                      const quotaGap = Math.max(item.quota_total_section_count - item.quota_passed_section_count, 0);
                      const reportTitle = sanitizeExternalDisplayText(item.report_title || item.entry_title || "知识卡片");
                      return (
                        <div key={item.entry_id} className="rounded-[20px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] p-4">
                          <div className="flex flex-wrap items-start justify-between gap-3">
                            <div className="min-w-0 flex-1">
                              <Link href={`/knowledge/${item.entry_id}`} className="block">
                                <p className="text-sm font-semibold text-[var(--af-text-primary)] transition hover:text-[var(--af-info)]">{reportTitle}</p>
                              </Link>
                              <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">
                                {sanitizeExternalDisplayText(item.keyword || "未标注关键词")}
                              </p>
                            </div>
                            <span className="rounded-full bg-[color-mix(in_srgb,var(--af-danger)_12%,var(--af-surface-muted))] px-2.5 py-1 text-[11px] font-medium text-[var(--af-danger)]">
                              弱度 {item.weakness_score}
                            </span>
                          </div>
                          <div className="mt-3 flex flex-wrap gap-2 text-[11px] text-[var(--af-text-secondary)]">
                            <span className={`rounded-full px-2.5 py-1 font-medium ${item.retrieval_hit ? "af-chip af-chip-success" : "af-chip af-chip-danger"}`}>
                              {item.retrieval_hit ? "检索命中已过线" : "检索命中偏弱"}
                            </span>
                            <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1">
                              目标支撑 {item.supported_target_accounts}/{item.supported_target_accounts + item.unsupported_target_accounts}
                            </span>
                            <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1">
                              章节配额 {item.quota_passed_section_count}/{item.quota_total_section_count}
                            </span>
                            <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1">
                              官方源 {Math.round(item.official_source_ratio * 100)}%
                            </span>
                            <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1">
                              严格命中 {Math.round(item.strict_match_ratio * 100)}%
                            </span>
                            <span className={`rounded-full px-2.5 py-1 ${
                              item.delivery_quality_status === "pass"
                                ? "af-chip af-chip-success"
                                : item.delivery_quality_status === "watch"
                                  ? "af-chip af-chip-warning"
                                  : "af-chip af-chip-danger"
                            }`}>
                              交付质量 {item.delivery_quality_status === "pass" ? "通过" : item.delivery_quality_status === "watch" ? "待补强" : "待重审"}
                            </span>
                            <span className="rounded-full bg-[var(--af-surface-elevated)] px-2.5 py-1">
                              方案/建议书 {item.solution_delivery_quality_score}/{item.project_proposal_quality_score}
                            </span>
                          </div>
                          {(item.unsupported_targets.length || item.failing_sections.length || item.delivery_missing_axes.length) ? (
                            <div className="mt-3 space-y-2">
                              {item.unsupported_targets.length ? (
                                <p className="text-sm leading-6 text-[var(--af-text-secondary)]">
                                  待核验账户 · {sanitizeExternalDisplayText(item.unsupported_targets.join(" / "))}
                                </p>
                              ) : null}
                              {item.failing_sections.length ? (
                                <p className="text-sm leading-6 text-[var(--af-text-secondary)]">
                                  未过配额章节 · {sanitizeExternalDisplayText(item.failing_sections.join(" / "))} {quotaGap > 0 ? `(${quotaGap} 处待补)` : ""}
                                </p>
                              ) : null}
                              {item.delivery_missing_axes.length ? (
                                <p className="text-sm leading-6 text-[var(--af-text-secondary)]">
                                  交付缺口 · {sanitizeExternalDisplayText(item.delivery_missing_axes.join(" / "))}
                                </p>
                              ) : null}
                            </div>
                          ) : null}
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <p className="mt-3 text-sm text-[var(--af-text-tertiary)]">当前没有需要优先回归的弱样本。</p>
                )}
              </div>
            </div>
          </>
        )}
      </section>
  );
}
