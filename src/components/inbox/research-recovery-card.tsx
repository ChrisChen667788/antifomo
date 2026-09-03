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

function parseSupplementalUrls(value: string) {
  return value
    .split(/[\s,，;；]+/)
    .map((item) => item.trim())
    .filter((item) => /^https?:\/\//i.test(item));
}

function startsRecoveryJob(action: ApiResearchClarificationAction) {
  return action !== "view_provisional";
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
  const supplementalUrls = useMemo(() => parseSupplementalUrls(urlText), [urlText]);
  const recoveryAttempt = Math.max(0, Number(job.recovery_attempt || 0));
  const recoveryLimit = Math.max(0, Number(job.recovery_limit || 0));
  const recoveryExhausted = Boolean(job.recovery_exhausted);
  const historicalAttemptsExceededLimit = recoveryExhausted
    && recoveryLimit > 0
    && recoveryAttempt > recoveryLimit;
  const requiresEvidenceInput = Boolean(job.requires_evidence_input);
  const hasEvidenceInput = supplementalUrls.length > 0 || files.length > 0;

  if (!packet || (!packet.active && !recoveryExhausted)) return null;

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
    if (startsRecoveryJob(action) && recoveryExhausted) {
      setError("补证复核已达到本任务上限，不会再创建子任务。可先查看受限草稿，或补齐可核验来源后新建调研。");
      return;
    }
    if (startsRecoveryJob(action) && requiresEvidenceInput && !hasEvidenceInput) {
      setError("本轮必须补充至少一个可核验的 http(s) 网址或文件。文字说明会保留，但不能单独解除证据门禁。");
      return;
    }
    setSubmittingAction(action);
    try {
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
      if (response.outcome === "recovery_blocked") {
        setError(response.message || "本次补证没有创建新任务，请按当前证据提示调整后再试。");
      }
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
          <p className="af-kicker">
            {recoveryExhausted
              ? "补证复核已闭环"
              : recoveryAttempt > 0
                ? `第 ${recoveryAttempt}${recoveryLimit > 0 ? `/${recoveryLimit}` : ""} 轮补证复核已完成`
                : "继续完成这份研报"}
          </p>
          <h2 id={`research-recovery-${job.id}`} className="mt-2 text-xl font-semibold text-[var(--af-text-primary)]">
            {packet.title}
          </h2>
          <p className="mt-2 text-sm leading-6 text-[var(--af-text-secondary)]">{packet.summary}</p>
        </div>
        <div className="flex flex-wrap justify-end gap-2">
          {recoveryAttempt > 0 ? (
            <span className="rounded-full border border-sky-200 bg-sky-50 px-3 py-1 text-xs font-medium text-sky-700">
              本轮执行 100% 完成
            </span>
          ) : null}
          <span className="rounded-full border border-[var(--af-border-subtle)] px-3 py-1 text-xs font-medium text-[var(--af-text-secondary)]">
            已保留 {packet.accepted_source_count} 条有效来源
          </span>
        </div>
      </div>

      {recoveryAttempt > 0 ? (
        <div
          className="mt-4 rounded-lg border border-sky-100 bg-sky-50/80 px-3.5 py-3 text-sm leading-6 text-sky-800"
          data-testid="research-recovery-round-summary"
        >
          {historicalAttemptsExceededLimit
            ? `历史任务已执行 ${recoveryAttempt} 轮补证复核；当前规则上限为 ${recoveryLimit} 轮。`
            : `第 ${recoveryAttempt}${recoveryLimit > 0 ? `/${recoveryLimit}` : ""} 轮补证复核已经执行完毕。`}
          这里的证据缺口不是任务进度归零。
          {recoveryExhausted
            ? " 本任务已达到复核上限，系统不会再创建重复子任务。"
            : " 已有任务、输入和证据快照均继续保留。"}
        </div>
      ) : null}

      {recoveryExhausted ? (
        <div
          role="status"
          className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-3 text-sm leading-6 text-amber-900"
          data-testid="research-recovery-exhausted"
        >
          <p className="font-semibold">已完成本任务可用的补证复核轮次</p>
          <p className="mt-1">
            当前证据仍不足以解除正式交付门禁。可查看受限草稿（如已开放），或带官网、政策、采购公告、项目材料等可核验来源重新发起调研。
          </p>
        </div>
      ) : requiresEvidenceInput ? (
        <div
          role="status"
          className="mt-4 rounded-lg border border-amber-200 bg-amber-50 px-3.5 py-3 text-sm leading-6 text-amber-900"
          data-testid="research-recovery-evidence-required"
        >
          <p className="font-semibold">下一轮必须提供可核验证据</p>
          <p className="mt-1">补充说明可保留在表单中并与来源一并提交，但仅填写文字不会再启动重复复核。请至少添加一个 http(s) 网址或上传一个文件。</p>
        </div>
      ) : null}

      {packet.minimum_source_count > 0 ? (
        <div className="mt-4" aria-label={`证据门禁 ${evidenceProgress}%`}>
          <div className="mb-2 flex flex-wrap items-center justify-between gap-2 text-xs text-[var(--af-text-tertiary)]">
            <span>证据门禁：{packet.accepted_source_count}/{packet.minimum_source_count}</span>
            <span>这是来源达标率，不是任务执行进度</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-[var(--af-surface-muted)]">
            <div
              className="h-full rounded-full bg-[var(--af-info)] transition-[width]"
              style={{ width: `${evidenceProgress}%` }}
            />
          </div>
        </div>
      ) : null}

      {!recoveryExhausted && packet.questions.length ? (
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

      {!recoveryExhausted && packet.interaction_state !== "system_degraded" ? (
        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2">
          <label className="text-sm font-medium text-[var(--af-text-primary)]">
            补充网址{requiresEvidenceInput ? "（本轮必填之一）" : ""}
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
            上传材料{requiresEvidenceInput ? "（本轮必填之一）" : ""}
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
        {packet.recovery_options
          .filter((option) => !recoveryExhausted || option.action === "view_provisional")
          .map((option) => {
            const disabledForEvidence = startsRecoveryJob(option.action)
              && requiresEvidenceInput
              && !hasEvidenceInput;
            return (
              <button
                key={option.action}
                type="button"
                onClick={() => void runAction(option.action)}
                disabled={Boolean(submittingAction) || disabledForEvidence}
                title={
                  disabledForEvidence
                    ? "请先添加至少一个 http(s) 网址或文件"
                    : option.description
                }
                className={`${option.recommended ? "af-btn af-btn-primary" : "af-btn af-btn-secondary border"} disabled:cursor-not-allowed disabled:opacity-60`}
              >
                {submittingAction === option.action ? "处理中..." : option.label}
              </button>
            );
          })}
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
