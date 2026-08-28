"use client";

import { useEffect, useMemo, useState } from "react";
import {
  submitResearchJobClarification,
  type ApiResearchClarificationAction,
  type ApiResearchJob,
  type ApiResearchSupplementalDocument,
} from "@/lib/api";

type ResearchRecoveryCardProps = {
  job: ApiResearchJob;
  onParentUpdated: (job: ApiResearchJob) => void;
  onRecoveryStarted: (job: ApiResearchJob) => void;
};

function newIdempotencyKey(jobId: string) {
  const nonce = typeof crypto !== "undefined" && "randomUUID" in crypto
    ? crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(16).slice(2)}`;
  return `research-recovery-${jobId}-${nonce}`;
}

function fileToBase64(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error(`无法读取 ${file.name}`));
    reader.onload = () => {
      const value = String(reader.result || "");
      resolve(value.includes(",") ? value.slice(value.indexOf(",") + 1) : value);
    };
    reader.readAsDataURL(file);
  });
}

export function ResearchRecoveryCard({
  job,
  onParentUpdated,
  onRecoveryStarted,
}: ResearchRecoveryCardProps) {
  const packet = job.clarification_packet;
  const [answers, setAnswers] = useState<Record<string, string[]>>({});
  const [urlText, setUrlText] = useState("");
  const [supplementalText, setSupplementalText] = useState("");
  const [files, setFiles] = useState<File[]>([]);
  const [submittingAction, setSubmittingAction] = useState<ApiResearchClarificationAction | "">("");
  const [error, setError] = useState("");
  const [idempotencyKey, setIdempotencyKey] = useState(() => newIdempotencyKey(job.id));

  useEffect(() => {
    setAnswers({});
    setUrlText("");
    setSupplementalText("");
    setFiles([]);
    setError("");
    setSubmittingAction("");
    setIdempotencyKey(newIdempotencyKey(job.id));
  }, [job.id]);

  const evidenceProgress = useMemo(() => {
    const minimum = Math.max(1, packet?.minimum_source_count || 1);
    return Math.min(100, Math.round(((packet?.accepted_source_count || 0) / minimum) * 100));
  }, [packet?.accepted_source_count, packet?.minimum_source_count]);

  if (!packet?.active) return null;

  const updateSingleAnswer = (questionId: string, value: string) => {
    setAnswers((current) => ({ ...current, [questionId]: value.trim() ? [value] : [] }));
  };

  const toggleAnswer = (questionId: string, value: string) => {
    setAnswers((current) => {
      const existing = current[questionId] || [];
      const next = existing.includes(value)
        ? existing.filter((item) => item !== value)
        : [...existing, value];
      return { ...current, [questionId]: next };
    });
  };

  const runAction = async (action: ApiResearchClarificationAction) => {
    setError("");
    setSubmittingAction(action);
    try {
      const supplementalUrls = urlText
        .split(/[\s,，;；]+/)
        .map((value) => value.trim())
        .filter(Boolean);
      const supplementalDocuments: ApiResearchSupplementalDocument[] = await Promise.all(
        files.map(async (file) => ({
          file_name: file.name,
          mime_type: file.type || "application/octet-stream",
          file_base64: await fileToBase64(file),
        })),
      );
      const response = await submitResearchJobClarification(job.id, {
        action,
        idempotency_key: idempotencyKey,
        answers: Object.entries(answers).map(([question_id, values]) => ({ question_id, values })),
        supplemental_urls: supplementalUrls,
        supplemental_text: supplementalText,
        supplemental_documents: supplementalDocuments,
      });
      onParentUpdated(response.parent_job);
      if (response.child_job) {
        onRecoveryStarted(response.child_job);
      } else if (action === "view_provisional") {
        document.querySelector("[data-testid='research-report-card']")?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }
      setIdempotencyKey(newIdempotencyKey(job.id));
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "续跑失败，请检查补充内容后重试。");
    } finally {
      setSubmittingAction("");
    }
  };

  return (
    <section
      className="mt-5 scroll-mt-24 rounded-lg border border-[color-mix(in_srgb,var(--af-info)_34%,var(--af-border-subtle))] bg-[var(--af-surface-elevated)] p-4 md:p-5"
      aria-labelledby={`research-recovery-${job.id}`}
      data-testid="research-recovery-card"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="max-w-3xl">
          <p className="af-kicker">继续完成这份研报</p>
          <h2 id={`research-recovery-${job.id}`} className="mt-2 text-xl font-semibold text-[var(--af-text-primary)]">
            {packet.title}
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{packet.summary}</p>
        </div>
        <span className="rounded-full border border-[var(--af-border-subtle)] px-3 py-1 text-xs font-medium text-[var(--af-text-secondary)]">
          已保留 {packet.accepted_source_count} 条有效来源
        </span>
      </div>

      {packet.minimum_source_count > 0 ? (
        <div className="mt-4" aria-label={`证据进度 ${evidenceProgress}%`}>
          <div className="h-1.5 overflow-hidden rounded-full bg-[var(--af-surface-muted)]">
            <div
              className="h-full rounded-full bg-[var(--af-info)] transition-[width]"
              style={{ width: `${evidenceProgress}%` }}
            />
          </div>
        </div>
      ) : null}

      {packet.questions.length ? (
        <div className="mt-5 space-y-4">
          {packet.questions.map((question, index) => (
            <fieldset key={question.question_id} className="rounded-lg border border-[var(--af-border-subtle)] p-4">
              <legend className="px-1 text-sm font-semibold text-[var(--af-text-primary)]">
                {index + 1}. {question.prompt}
              </legend>
              {question.reason ? (
                <p className="mt-1 text-xs leading-5 text-[var(--af-text-tertiary)]">{question.reason}</p>
              ) : null}
              {question.options.length ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {question.options.map((option) => {
                    const checked = (answers[question.question_id] || []).includes(option.value);
                    return (
                      <label
                        key={option.value}
                        className={`cursor-pointer rounded-md border px-3 py-2 text-sm ${
                          checked
                            ? "border-[var(--af-info)] bg-[color-mix(in_srgb,var(--af-info)_9%,var(--af-surface-muted))] text-[var(--af-info)]"
                            : "border-[var(--af-border-subtle)] text-[var(--af-text-secondary)]"
                        }`}
                      >
                        <input
                          type={question.input_kind === "single_choice" ? "radio" : "checkbox"}
                          name={question.question_id}
                          checked={checked}
                          onChange={() => {
                            if (question.input_kind === "single_choice") {
                              updateSingleAnswer(question.question_id, option.value);
                            } else {
                              toggleAnswer(question.question_id, option.value);
                            }
                          }}
                          className="mr-2"
                        />
                        {option.label}
                      </label>
                    );
                  })}
                </div>
              ) : question.input_kind !== "file_or_url" && question.input_kind !== "url_list" ? (
                <textarea
                  rows={2}
                  value={(answers[question.question_id] || [])[0] || ""}
                  onChange={(event) => updateSingleAnswer(question.question_id, event.target.value)}
                  placeholder={question.placeholder}
                  className="af-input mt-3 resize-none leading-6"
                />
              ) : null}
            </fieldset>
          ))}
        </div>
      ) : null}

      {packet.interaction_state !== "system_degraded" ? (
        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2">
          <label className="text-sm font-medium text-[var(--af-text-primary)]">
            补充网址
            <textarea
              rows={3}
              value={urlText}
              onChange={(event) => setUrlText(event.target.value)}
              placeholder="每行一个官网、政策、采购公告或项目链接"
              className="af-input mt-2 resize-none text-sm leading-6"
            />
          </label>
          <label className="text-sm font-medium text-[var(--af-text-primary)]">
            补充说明
            <textarea
              rows={3}
              value={supplementalText}
              onChange={(event) => setSupplementalText(event.target.value)}
              placeholder="会议背景、范围、约束或必须回答的问题"
              className="af-input mt-2 resize-none text-sm leading-6"
            />
          </label>
          <label className="text-sm font-medium text-[var(--af-text-primary)] md:col-span-2">
            上传材料
            <input
              type="file"
              multiple
              accept={packet.questions.flatMap((question) => question.accepted_file_types).join(",") || ".pdf,.docx,.txt,.md,.csv,.json"}
              onChange={(event) => {
                const selected = Array.from(event.target.files || []).slice(0, 4);
                const oversized = selected.find((file) => file.size > 10 * 1024 * 1024);
                if (oversized) {
                  setError(`${oversized.name} 超过 10MB 限制。`);
                  return;
                }
                setFiles(selected);
              }}
              className="mt-2 block w-full rounded-md border border-[var(--af-border-subtle)] bg-[var(--af-surface-muted)] px-3 py-2 text-sm text-[var(--af-text-secondary)]"
            />
            {files.length ? (
              <span className="mt-2 block text-xs text-[var(--af-text-tertiary)]">
                已选择 {files.map((file) => file.name).join("、")}
              </span>
            ) : null}
          </label>
        </div>
      ) : null}

      {error ? <p className="mt-3 text-sm text-[var(--af-danger)]">{error}</p> : null}

      <div className="mt-5 flex flex-wrap gap-2">
        {packet.recovery_options.map((option) => (
          <button
            key={option.action}
            type="button"
            onClick={() => void runAction(option.action)}
            disabled={Boolean(submittingAction)}
            title={option.description}
            className={`${option.recommended ? "af-btn af-btn-primary" : "af-btn af-btn-secondary border"} disabled:cursor-not-allowed disabled:opacity-60`}
          >
            {submittingAction === option.action ? "处理中..." : option.label}
          </button>
        ))}
      </div>

      <details className="mt-4 text-xs text-[var(--af-text-tertiary)]">
        <summary className="cursor-pointer font-medium">本次续跑如何处理已有结果</summary>
        <ul className="mt-2 space-y-1.5 leading-5">
          {packet.next_steps.map((step) => <li key={step}>• {step}</li>)}
        </ul>
      </details>
    </section>
  );
}
