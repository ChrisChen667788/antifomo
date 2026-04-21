import type { ApiResearchSourceDiagnostics } from "@/lib/api";

const GUARDED_REWRITE_REASON_LABELS: Record<string, string> = {
  single_source_nonready: "来源过少，当前报告还没达到可推进门槛",
  no_sources: "没有保留到可用来源",
  fallback_low_support: "仍是兜底候选，严格命中或官方源支撑不足",
  low_retrieval_low_official: "检索质量偏低，且官方源覆盖不足",
  source_noise_majority: "保留来源里噪声占比过高",
  no_target_source_support: "目标账户没有被来源正文支撑",
  unsupported_targets: "目标账户只有推断，没有形成正文或官方源共同支撑",
  no_concrete_targets: "当前还没有收敛到可验证的具体账户",
  post_rewrite_low_signal_guard: "重写后仍然低信号，继续留在待核验 backlog",
};

export function isGuardedBacklog(
  diagnostics?:
    | Partial<Pick<ApiResearchSourceDiagnostics, "guarded_backlog" | "guarded_rewrite_reasons">>
    | null,
): boolean {
  return Boolean(diagnostics?.guarded_backlog || diagnostics?.guarded_rewrite_reasons?.length);
}

export function getGuardedRewriteReasonLabels(
  diagnostics?:
    | Partial<Pick<ApiResearchSourceDiagnostics, "guarded_rewrite_reasons" | "guarded_rewrite_reason_labels">>
    | null,
): string[] {
  const explicitLabels = Array.isArray(diagnostics?.guarded_rewrite_reason_labels)
    ? diagnostics.guarded_rewrite_reason_labels.map((value) => String(value || "").trim()).filter(Boolean)
    : [];
  if (explicitLabels.length) {
    return explicitLabels;
  }
  return (Array.isArray(diagnostics?.guarded_rewrite_reasons) ? diagnostics.guarded_rewrite_reasons : [])
    .map((value) => GUARDED_REWRITE_REASON_LABELS[String(value || "").trim()] || String(value || "").trim())
    .filter(Boolean);
}
