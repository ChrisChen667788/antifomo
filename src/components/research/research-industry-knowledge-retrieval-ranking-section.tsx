"use client";

import { useCallback, useEffect, useState } from "react";
import {
  getResearchIndustryKnowledgeRetrievalBenchmark,
  runResearchIndustryKnowledgeRetrievalBenchmark,
  type ApiResearchIndustryKnowledgeBenchmarkMetric,
  type ApiResearchIndustryKnowledgeRetrievalBenchmark,
} from "@/lib/api";

type TranslationFn = (key: string, fallback: string) => string;

const decisionClass = {
  promote: "af-chip af-chip-success",
  hold: "af-chip af-chip-warning",
  block: "af-chip bg-rose-100 text-rose-700",
} as const;

const decisionLabel = {
  promote: "可上线",
  hold: "保持现状",
  block: "不可运行",
} as const;

function formatMetric(metric: ApiResearchIndustryKnowledgeBenchmarkMetric): string {
  if (metric.value == null) return "待评分";
  if (metric.key === "latency_ms") return `${Math.round(metric.value)} ms`;
  if (metric.key === "human_review_score") return `${metric.value.toFixed(2)}/5`;
  return `${(metric.value * 100).toFixed(1)}%`;
}

function formatDelta(metric: ApiResearchIndustryKnowledgeBenchmarkMetric): string {
  if (metric.delta == null || metric.key === "human_review_score") return "";
  if (metric.key === "latency_ms") {
    const rounded = Math.round(metric.delta);
    return `${rounded > 0 ? "+" : ""}${rounded} ms vs 基线`;
  }
  const value = metric.delta * 100;
  return `${value > 0 ? "+" : ""}${value.toFixed(1)}pp vs 基线`;
}

export function ResearchIndustryKnowledgeRetrievalRankingSection({ t }: { t: TranslationFn }) {
  const [benchmark, setBenchmark] = useState<ApiResearchIndustryKnowledgeRetrievalBenchmark | null>(null);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      setBenchmark(await getResearchIndustryKnowledgeRetrievalBenchmark());
    } catch {
      setError(t("research.retrievalRankingLoadFailed", "读取本地资料检索排序评测失败。"));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  const run = async () => {
    setRunning(true);
    setError("");
    try {
      setBenchmark(await runResearchIndustryKnowledgeRetrievalBenchmark());
    } catch {
      setError(t("research.retrievalRankingRunFailed", "本地资料检索排序评测运行失败。"));
    } finally {
      setRunning(false);
    }
  };

  return (
    <section className="mt-5 rounded-[28px] border border-[var(--af-border-subtle)] bg-[var(--af-surface)] p-4 shadow-[var(--af-shadow-soft)]">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-3xl">
          <p className="text-xs font-semibold uppercase tracking-[0.22em] text-[var(--af-text-tertiary)]">
            {t("research.retrievalRankingKicker", "Local Knowledge Retrieval")}
          </p>
          <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">
            {t(
              "research.retrievalRankingDesc",
              "固定题集对比当前混合检索、范围预过滤与字段加权、以及真实 Cross Encoder 复排；只有通过全部门禁的候选才允许替换默认策略。",
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {benchmark ? (
            <span className={decisionClass[benchmark.promotion.decision]}>
              {decisionLabel[benchmark.promotion.decision]}
            </span>
          ) : null}
          <button type="button" onClick={() => void load()} disabled={loading || running} className="af-btn af-btn-secondary border px-3 py-1.5 text-xs">
            {loading ? "读取中..." : "刷新结果"}
          </button>
          <button type="button" onClick={() => void run()} disabled={running} className="af-btn af-btn-primary px-3 py-1.5 text-xs">
            {running ? "评测中..." : "运行固定题集"}
          </button>
        </div>
      </div>

      {loading && !benchmark ? <p className="mt-4 text-sm text-[var(--af-text-tertiary)]">正在读取检索排序结果...</p> : null}
      {error ? <p className="mt-4 text-sm text-[var(--af-warning)]">{error}</p> : null}

      {benchmark ? (
        <>
          <div className="mt-4 grid grid-cols-2 gap-3 md:grid-cols-4">
            <Metric label="固定题集" value={`${benchmark.case_count} 题`} />
            <Metric label="知识库版本" value={benchmark.knowledge_base_generation_id ? benchmark.knowledge_base_generation_id.slice(0, 8) : "未构建"} />
            <Metric label="人工评分" value={`${benchmark.promotion.completed_human_review_case_count}/${benchmark.promotion.required_human_review_case_count}`} />
            <Metric label="评测状态" value={benchmark.status} />
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-3">
            {benchmark.arms.map((arm) => (
              <article key={arm.strategy} className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="text-sm font-semibold text-[var(--af-text-primary)]">{arm.label}</p>
                    <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">
                      {arm.role === "baseline" ? "当前生产默认路径" : "仅用于固定题集评测，不影响生产默认路径"}
                    </p>
                  </div>
                  <span className={arm.role === "baseline" ? "af-chip" : "af-chip af-chip-warning"}>{arm.role === "baseline" ? "默认" : "候选"}</span>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  {arm.metrics.map((metric) => (
                    <div key={metric.key} className="rounded-[16px] bg-[var(--af-surface-muted)] px-3 py-2">
                      <p className="text-[11px] text-[var(--af-text-tertiary)]">{metric.label}</p>
                      <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{formatMetric(metric)}</p>
                      {formatDelta(metric) ? <p className="mt-1 text-[11px] text-[var(--af-text-tertiary)]">{formatDelta(metric)}</p> : null}
                    </div>
                  ))}
                </div>
                {arm.strategy === "prefilter_weighted_rerank" ? (
                  <p className="mt-3 text-xs leading-5 text-[var(--af-text-tertiary)]">
                    真实复排：{arm.rerank_applied_case_count}/{arm.case_count} · {arm.rerank_backend}
                    {arm.rerank_model ? ` · ${arm.rerank_model}` : " · 模型未记录"}
                  </p>
                ) : null}
              </article>
            ))}
          </div>

          <div className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-[1.1fr_0.9fr]">
            <div className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-sm font-semibold text-[var(--af-text-primary)]">上线判定</p>
              <div className="mt-3 space-y-2">
                {benchmark.promotion.reasons.map((reason) => (
                  <p key={reason} className="rounded-[16px] bg-[var(--af-surface-muted)] px-3 py-2 text-xs leading-5 text-[var(--af-text-secondary)]">
                    {reason}
                  </p>
                ))}
                {!benchmark.promotion.reasons.length ? <p className="text-xs text-[var(--af-text-tertiary)]">暂无阻断原因。</p> : null}
              </div>
            </div>
            <div className="rounded-[22px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
              <p className="text-sm font-semibold text-[var(--af-text-primary)]">评测约束</p>
              <div className="mt-3 space-y-2 text-xs leading-5 text-[var(--af-text-secondary)]">
                {benchmark.strategies.map((strategy) => (
                  <p key={strategy.key} className="rounded-[16px] bg-[var(--af-surface-muted)] px-3 py-2">
                    <span className="font-semibold text-[var(--af-text-primary)]">{strategy.label}</span> · {strategy.description}
                  </p>
                ))}
                <p className="rounded-[16px] bg-[var(--af-surface-muted)] px-3 py-2">
                  人工评分必须关联同策略的完整报告工件；固定证据审阅样本位于 <span className="break-all font-mono text-[11px] text-[var(--af-text-primary)]">{benchmark.review_sample_directory || "待运行评测"}</span>。
                </p>
              </div>
            </div>
          </div>

          {benchmark.warnings.length ? (
            <div className="mt-3 rounded-[18px] border border-amber-200 bg-amber-50 px-3 py-2 text-xs leading-5 text-amber-800">
              {benchmark.warnings.map((warning) => <p key={warning}>{warning}</p>)}
            </div>
          ) : null}
        </>
      ) : null}
    </section>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-[18px] border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] px-3 py-2">
      <p className="text-[11px] uppercase tracking-[0.12em] text-[var(--af-text-tertiary)]">{label}</p>
      <p className="mt-1 text-sm font-semibold text-[var(--af-text-primary)]">{value}</p>
    </div>
  );
}
