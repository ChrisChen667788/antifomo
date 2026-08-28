"use client";

import { useState } from "react";
import { submitResearchExperienceFeedback } from "@/lib/api";

const reasons = [
  ["helpful", "有帮助"],
  ["missing_sources", "来源不足"],
  ["question_unclear", "问题不清楚"],
  ["too_technical", "说明太技术化"],
  ["result_quality", "结果质量不佳"],
  ["recovery_failed", "续跑未解决"],
] as const;

export function ResearchExperienceFeedback({ jobId }: { jobId: string }) {
  const [score, setScore] = useState(0);
  const [reason, setReason] = useState<(typeof reasons)[number][0]>("helpful");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const [error, setError] = useState("");

  if (submitted) {
    return (
      <p className="rounded-lg border border-[var(--af-border-subtle)] px-4 py-3 text-sm text-[var(--af-text-secondary)]">
        反馈已记录。
      </p>
    );
  }

  return (
    <section className="rounded-lg border border-[var(--af-border-subtle)] bg-[var(--af-surface-elevated)] p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-[var(--af-text-primary)]">这次结果是否帮到你？</p>
          <p className="mt-1 text-xs text-[var(--af-text-tertiary)]">反馈会进入澄清质量校准，不改变当前研报。</p>
        </div>
        <div className="flex gap-1" aria-label="体验评分">
          {[1, 2, 3, 4, 5].map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setScore(value)}
              aria-label={`${value} 分`}
              className={`h-8 w-8 rounded-md border text-sm ${
                score >= value
                  ? "border-[var(--af-info)] bg-[color-mix(in_srgb,var(--af-info)_10%,var(--af-surface-muted))] text-[var(--af-info)]"
                  : "border-[var(--af-border-subtle)] text-[var(--af-text-tertiary)]"
              }`}
            >
              {value}
            </button>
          ))}
        </div>
      </div>
      {score ? (
        <div className="mt-3 flex flex-wrap gap-2">
          {reasons.map(([value, label]) => (
            <button
              key={value}
              type="button"
              onClick={() => setReason(value)}
              className={`rounded-md border px-3 py-1.5 text-xs ${
                reason === value
                  ? "border-[var(--af-info)] text-[var(--af-info)]"
                  : "border-[var(--af-border-subtle)] text-[var(--af-text-secondary)]"
              }`}
            >
              {label}
            </button>
          ))}
          <button
            type="button"
            disabled={submitting}
            onClick={async () => {
              setSubmitting(true);
              setError("");
              try {
                await submitResearchExperienceFeedback(jobId, { score, reason });
                setSubmitted(true);
              } catch (cause) {
                setError(cause instanceof Error ? cause.message : "反馈提交失败。");
              } finally {
                setSubmitting(false);
              }
            }}
            className="af-btn af-btn-primary ml-auto disabled:cursor-not-allowed disabled:opacity-60"
          >
            {submitting ? "提交中..." : "提交反馈"}
          </button>
        </div>
      ) : null}
      {error ? <p className="mt-2 text-xs text-[var(--af-danger)]">{error}</p> : null}
    </section>
  );
}
