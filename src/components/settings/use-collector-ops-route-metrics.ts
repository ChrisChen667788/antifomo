"use client";

import type { WechatAgentBatchStatus } from "@/lib/api";

export function useCollectorOpsRouteMetrics(wechatAgentBatchStatus: WechatAgentBatchStatus | null) {
  const batchProgress =
    wechatAgentBatchStatus && wechatAgentBatchStatus.total_segments > 0
      ? wechatAgentBatchStatus.running
        ? Math.max(
            8,
            Math.min(
              96,
              Math.round(
                (Math.max(wechatAgentBatchStatus.current_segment_index, 1) /
                  wechatAgentBatchStatus.total_segments) *
                  100,
              ),
            ),
          )
        : wechatAgentBatchStatus.finished_at
          ? 100
          : 0
      : 0;
  const mergeBatchMetric = (base: number | undefined | null, live: number | undefined | null) =>
    (wechatAgentBatchStatus?.running ? Number(base || 0) + Number(live || 0) : Number(base || 0));
  const submittedUrlDirect = mergeBatchMetric(
    wechatAgentBatchStatus?.submitted_url_direct,
    wechatAgentBatchStatus?.live_report_submitted_url_direct,
  );
  const submittedUrlShareCopy = mergeBatchMetric(
    wechatAgentBatchStatus?.submitted_url_share_copy,
    wechatAgentBatchStatus?.live_report_submitted_url_share_copy,
  );
  const submittedUrlResolved = mergeBatchMetric(
    wechatAgentBatchStatus?.submitted_url_resolved,
    wechatAgentBatchStatus?.live_report_submitted_url_resolved,
  );
  const submittedOcr = mergeBatchMetric(
    wechatAgentBatchStatus?.submitted_ocr,
    wechatAgentBatchStatus?.live_report_submitted_ocr,
  );
  const skippedSeenTotal = mergeBatchMetric(
    wechatAgentBatchStatus?.skipped_seen,
    wechatAgentBatchStatus?.live_report_skipped_seen,
  );
  const failedTotal = mergeBatchMetric(
    wechatAgentBatchStatus?.failed,
    wechatAgentBatchStatus?.live_report_failed,
  );
  const duplicateEscapes = mergeBatchMetric(
    wechatAgentBatchStatus?.duplicate_escape_count,
    wechatAgentBatchStatus?.live_report_duplicate_escape_count,
  );
  const routeBackoffs = mergeBatchMetric(
    wechatAgentBatchStatus?.route_backoff_count,
    wechatAgentBatchStatus?.live_report_route_backoff_count,
  );
  const routeCircuitBreakers = mergeBatchMetric(
    wechatAgentBatchStatus?.route_circuit_breaker_count,
    wechatAgentBatchStatus?.live_report_route_circuit_breaker_count,
  );
  const recoveryActions = mergeBatchMetric(
    wechatAgentBatchStatus?.recovery_action_count,
    wechatAgentBatchStatus?.live_report_recovery_action_count,
  );
  const urlOnlySkips = mergeBatchMetric(
    wechatAgentBatchStatus?.url_only_skip_count,
    wechatAgentBatchStatus?.live_report_url_only_skip_count,
  );
  const previewLoopHits = mergeBatchMetric(
    Number(wechatAgentBatchStatus?.ocr_preview_seen_count || 0) + Number(wechatAgentBatchStatus?.ocr_title_seen_count || 0),
    Number(wechatAgentBatchStatus?.live_report_ocr_preview_seen_count || 0) +
      Number(wechatAgentBatchStatus?.live_report_ocr_title_seen_count || 0),
  );
  const accessibilityHits = mergeBatchMetric(
    wechatAgentBatchStatus?.accessibility_action_hits,
    wechatAgentBatchStatus?.live_report_accessibility_action_hits,
  );
  const templateHits = mergeBatchMetric(
    wechatAgentBatchStatus?.template_match_hits,
    wechatAgentBatchStatus?.live_report_template_match_hits,
  );
  const perceptualDedupHits = mergeBatchMetric(
    wechatAgentBatchStatus?.perceptual_duplicate_count,
    wechatAgentBatchStatus?.live_report_perceptual_duplicate_count,
  );
  const hardEscapes = mergeBatchMetric(
    wechatAgentBatchStatus?.hard_escape_count,
    wechatAgentBatchStatus?.live_report_hard_escape_count,
  );
  const submenuTraps = mergeBatchMetric(
    wechatAgentBatchStatus?.submenu_trap_count,
    wechatAgentBatchStatus?.live_report_submenu_trap_count,
  );
  const totalRouteDecisions = submittedUrlDirect + submittedUrlShareCopy + submittedUrlResolved + submittedOcr;
  const urlFirstShare = totalRouteDecisions
    ? Math.round(((submittedUrlDirect + submittedUrlShareCopy + submittedUrlResolved) / totalRouteDecisions) * 100)
    : 0;
  const ocrShare = totalRouteDecisions ? Math.round((submittedOcr / totalRouteDecisions) * 100) : 0;

  return {
    batchProgress,
    submittedUrlDirect,
    submittedUrlShareCopy,
    submittedUrlResolved,
    submittedOcr,
    skippedSeenTotal,
    failedTotal,
    duplicateEscapes,
    routeBackoffs,
    routeCircuitBreakers,
    recoveryActions,
    urlOnlySkips,
    previewLoopHits,
    accessibilityHits,
    templateHits,
    perceptualDedupHits,
    hardEscapes,
    submenuTraps,
    urlFirstShare,
    ocrShare,
  };
}
