from __future__ import annotations

from app.schemas.collector import (
    CollectorDaemonCommandResponse,
    CollectorDaemonRecentRowResponse,
    CollectorDaemonSourceHealthResponse,
    CollectorDaemonStatusResponse,
    WechatAgentBatchCommandResponse,
    WechatAgentBatchStatusResponse,
    WechatAgentCommandResponse,
    WechatAgentConfigResponse,
    WechatAgentDedupSummaryResponse,
    WechatAgentHealthResponse,
    WechatAgentRouteQualityResponse,
    WechatAgentSelfHealResponse,
    WechatAgentStatusResponse,
)
from app.services.collector_daemon import CollectorDaemonCommandResult, CollectorDaemonStatus
from app.services.wechat_pc_agent_daemon import (
    WechatAgentBatchCommandResult,
    WechatAgentBatchStatus,
    WechatAgentCommandResult,
    WechatAgentHealthReport,
    WechatAgentSelfHealResult,
    WechatAgentStatus,
    read_wechat_agent_dedup_summary,
)


def _to_daemon_status_response(status_obj: CollectorDaemonStatus) -> CollectorDaemonStatusResponse:
    return CollectorDaemonStatusResponse(
        running=status_obj.running,
        pid=status_obj.pid,
        pid_from_file=status_obj.pid_from_file,
        pid_file_present=status_obj.pid_file_present,
        uptime_seconds=status_obj.uptime_seconds,
        last_report_at=status_obj.last_report_at,
        last_daily_summary_at=status_obj.last_daily_summary_at,
        log_file=status_obj.log_file,
        log_size_bytes=status_obj.log_size_bytes,
        source_file_count=status_obj.source_file_count,
        last_run_at=status_obj.last_run_at,
        last_run_submit_mode=status_obj.last_run_submit_mode,
        last_run_discovered_count=status_obj.last_run_discovered_count,
        last_run_collected_count=status_obj.last_run_collected_count,
        last_run_plugin_count=status_obj.last_run_plugin_count,
        last_run_url_count=status_obj.last_run_url_count,
        last_run_failed_count=status_obj.last_run_failed_count,
        last_run_skipped_seen_count=status_obj.last_run_skipped_seen_count,
        last_run_handled_count=status_obj.last_run_handled_count,
        last_run_coverage_rate=status_obj.last_run_coverage_rate,
        last_run_body_success_rate=status_obj.last_run_body_success_rate,
        coverage_state=status_obj.coverage_state,
        coverage_recommendation=status_obj.coverage_recommendation,
        poor_source_count=status_obj.poor_source_count,
        watch_source_count=status_obj.watch_source_count,
        favorites_auto_status=status_obj.favorites_auto_status,
        favorites_auto_available=status_obj.favorites_auto_available,
        favorites_auto_last_at=status_obj.favorites_auto_last_at,
        favorites_auto_discovered_count=status_obj.favorites_auto_discovered_count,
        favorites_auto_imported_count=status_obj.favorites_auto_imported_count,
        favorites_auto_deduplicated_count=status_obj.favorites_auto_deduplicated_count,
        favorites_auto_message=status_obj.favorites_auto_message,
        source_health=[
            CollectorDaemonSourceHealthResponse(
                source_url=source.source_url,
                source_token=source.source_token,
                scanned=source.scanned,
                health_state=source.health_state,
                recommendation=source.recommendation,
                discovered_count=source.discovered_count,
                handled_count=source.handled_count,
                collected_count=source.collected_count,
                plugin_count=source.plugin_count,
                url_count=source.url_count,
                skipped_seen_count=source.skipped_seen_count,
                failed_count=source.failed_count,
                coverage_rate=source.coverage_rate,
                body_success_rate=source.body_success_rate,
                last_error=source.last_error,
            )
            for source in status_obj.source_health
        ],
        last_rows=[CollectorDaemonRecentRowResponse.model_validate(row) for row in status_obj.last_rows],
        log_tail=status_obj.log_tail,
    )


def _to_daemon_command_response(result: CollectorDaemonCommandResult) -> CollectorDaemonCommandResponse:
    return CollectorDaemonCommandResponse(
        action=result.action,
        ok=result.ok,
        message=result.message,
        status=_to_daemon_status_response(result.status),
        output=result.output,
    )


def _to_wechat_agent_status_response(status_obj: WechatAgentStatus) -> WechatAgentStatusResponse:
    return WechatAgentStatusResponse(
        running=status_obj.running,
        pid=status_obj.pid,
        pid_from_file=status_obj.pid_from_file,
        pid_file_present=status_obj.pid_file_present,
        run_once_running=status_obj.run_once_running,
        run_once_pid=status_obj.run_once_pid,
        uptime_seconds=status_obj.uptime_seconds,
        config_file=status_obj.config_file,
        config_file_present=status_obj.config_file_present,
        state_file=status_obj.state_file,
        state_file_present=status_obj.state_file_present,
        report_file=status_obj.report_file,
        report_file_present=status_obj.report_file_present,
        processed_hashes=status_obj.processed_hashes,
        last_cycle_at=status_obj.last_cycle_at,
        last_cycle_submitted=status_obj.last_cycle_submitted,
        last_cycle_submitted_new=status_obj.last_cycle_submitted_new,
        last_cycle_deduplicated_existing=status_obj.last_cycle_deduplicated_existing,
        last_cycle_failed=status_obj.last_cycle_failed,
        last_cycle_skipped_seen=status_obj.last_cycle_skipped_seen,
        last_cycle_skipped_low_quality=status_obj.last_cycle_skipped_low_quality,
        last_cycle_error=status_obj.last_cycle_error,
        last_cycle_new_item_ids=status_obj.last_cycle_new_item_ids,
        log_file=status_obj.log_file,
        log_size_bytes=status_obj.log_size_bytes,
        log_tail=status_obj.log_tail,
    )


def _to_wechat_agent_command_response(
    result: WechatAgentCommandResult,
) -> WechatAgentCommandResponse:
    return WechatAgentCommandResponse(
        action=result.action,
        ok=result.ok,
        message=result.message,
        status=_to_wechat_agent_status_response(result.status),
        output=result.output,
    )


def _to_wechat_agent_route_quality_response(
    status_obj: WechatAgentBatchStatus,
) -> WechatAgentRouteQualityResponse:
    submitted_url_direct = int(status_obj.submitted_url_direct or 0) + int(status_obj.live_report_submitted_url_direct or 0)
    submitted_url_share_copy = int(status_obj.submitted_url_share_copy or 0) + int(
        status_obj.live_report_submitted_url_share_copy or 0
    )
    submitted_url_resolved = int(status_obj.submitted_url_resolved or 0) + int(
        status_obj.live_report_submitted_url_resolved or 0
    )
    submitted_ocr = int(status_obj.submitted_ocr or 0) + int(status_obj.live_report_submitted_ocr or 0)
    route_total = submitted_url_direct + submitted_url_share_copy + submitted_url_resolved + submitted_ocr
    url_first_total = submitted_url_direct + submitted_url_share_copy + submitted_url_resolved
    url_first_share = round((url_first_total / route_total) * 100) if route_total else 0
    ocr_share = round((submitted_ocr / route_total) * 100) if route_total else 0

    accessibility_hits = int(status_obj.accessibility_action_hits or 0) + int(
        status_obj.live_report_accessibility_action_hits or 0
    )
    template_hits = int(status_obj.template_match_hits or 0) + int(status_obj.live_report_template_match_hits or 0)
    action_total = accessibility_hits + template_hits
    accessibility_hit_rate = round((accessibility_hits / action_total) * 100) if action_total else 0
    template_hit_rate = round((template_hits / action_total) * 100) if action_total else 0

    route_issue_count = (
        int(status_obj.route_backoff_count or 0)
        + int(status_obj.live_report_route_backoff_count or 0)
        + int(status_obj.route_circuit_breaker_count or 0)
        + int(status_obj.live_report_route_circuit_breaker_count or 0)
        + int(status_obj.ocr_preview_seen_count or 0)
        + int(status_obj.live_report_ocr_preview_seen_count or 0)
    )
    if route_total == 0:
        route_stability = "watch"
        recommendation = "当前还没有足够样本，建议先跑一轮 URL-first 批采再观察路由质量。"
    elif url_first_share >= 70 and ocr_share <= 25 and route_issue_count <= max(2, route_total // 4):
        route_stability = "good"
        recommendation = "当前主链仍以 URL-first 为主，建议继续优先浏览器正文与分享链路。"
    elif (
        ocr_share >= 45
        or int(status_obj.route_circuit_breaker_count or 0) + int(status_obj.live_report_route_circuit_breaker_count or 0) > 0
        or route_issue_count >= max(3, route_total // 2)
    ):
        route_stability = "poor"
        recommendation = "当前链路已明显退化到 OCR/重试，建议先检查分享菜单、浏览器登录态和文章热点配置。"
    else:
        route_stability = "watch"
        recommendation = "当前 URL-first 仍可用，但稳定性一般，建议继续观察 route backoff 和预览循环。"
    return WechatAgentRouteQualityResponse(
        url_first_share=url_first_share,
        ocr_share=ocr_share,
        accessibility_hit_rate=accessibility_hit_rate,
        template_hit_rate=template_hit_rate,
        route_stability=route_stability,
        recommendation=recommendation,
    )


def _to_wechat_agent_batch_status_response(
    status_obj: WechatAgentBatchStatus,
) -> WechatAgentBatchStatusResponse:
    return WechatAgentBatchStatusResponse(
        running=status_obj.running,
        total_items=status_obj.total_items,
        segment_items=status_obj.segment_items,
        start_batch_index=status_obj.start_batch_index,
        current_segment_index=status_obj.current_segment_index,
        total_segments=status_obj.total_segments,
        current_batch_index=status_obj.current_batch_index,
        started_at=status_obj.started_at,
        finished_at=status_obj.finished_at,
        submitted=status_obj.submitted,
        submitted_new=status_obj.submitted_new,
        submitted_url=status_obj.submitted_url,
        submitted_url_direct=status_obj.submitted_url_direct,
        submitted_url_share_copy=status_obj.submitted_url_share_copy,
        submitted_url_resolved=status_obj.submitted_url_resolved,
        submitted_ocr=status_obj.submitted_ocr,
        deduplicated_existing=status_obj.deduplicated_existing,
        deduplicated_existing_url=status_obj.deduplicated_existing_url,
        deduplicated_existing_url_direct=status_obj.deduplicated_existing_url_direct,
        deduplicated_existing_url_share_copy=status_obj.deduplicated_existing_url_share_copy,
        deduplicated_existing_url_resolved=status_obj.deduplicated_existing_url_resolved,
        deduplicated_existing_ocr=status_obj.deduplicated_existing_ocr,
        skipped_invalid_article=status_obj.skipped_invalid_article,
        skipped_seen=status_obj.skipped_seen,
        failed=status_obj.failed,
        validation_retries=status_obj.validation_retries,
        duplicate_escape_count=status_obj.duplicate_escape_count,
        route_backoff_count=status_obj.route_backoff_count,
        route_circuit_breaker_count=status_obj.route_circuit_breaker_count,
        recovery_action_count=status_obj.recovery_action_count,
        url_only_skip_count=status_obj.url_only_skip_count,
        ocr_preview_seen_count=status_obj.ocr_preview_seen_count,
        ocr_title_seen_count=status_obj.ocr_title_seen_count,
        accessibility_action_hits=status_obj.accessibility_action_hits,
        template_match_hits=status_obj.template_match_hits,
        perceptual_duplicate_count=status_obj.perceptual_duplicate_count,
        hard_escape_count=status_obj.hard_escape_count,
        submenu_trap_count=status_obj.submenu_trap_count,
        new_item_ids=status_obj.new_item_ids,
        last_message=status_obj.last_message,
        last_error=status_obj.last_error,
        live_report_running=status_obj.live_report_running,
        live_report_batch=status_obj.live_report_batch,
        live_report_row=status_obj.live_report_row,
        live_report_stage=status_obj.live_report_stage,
        live_report_detail=status_obj.live_report_detail,
        live_report_clicked=status_obj.live_report_clicked,
        live_report_submitted=status_obj.live_report_submitted,
        live_report_submitted_url=status_obj.live_report_submitted_url,
        live_report_submitted_url_direct=status_obj.live_report_submitted_url_direct,
        live_report_submitted_url_share_copy=status_obj.live_report_submitted_url_share_copy,
        live_report_submitted_url_resolved=status_obj.live_report_submitted_url_resolved,
        live_report_submitted_ocr=status_obj.live_report_submitted_ocr,
        live_report_skipped_seen=status_obj.live_report_skipped_seen,
        live_report_skipped_invalid_article=status_obj.live_report_skipped_invalid_article,
        live_report_failed=status_obj.live_report_failed,
        live_report_duplicate_escape_count=status_obj.live_report_duplicate_escape_count,
        live_report_route_backoff_count=status_obj.live_report_route_backoff_count,
        live_report_route_circuit_breaker_count=status_obj.live_report_route_circuit_breaker_count,
        live_report_recovery_action_count=status_obj.live_report_recovery_action_count,
        live_report_url_only_skip_count=status_obj.live_report_url_only_skip_count,
        live_report_ocr_preview_seen_count=status_obj.live_report_ocr_preview_seen_count,
        live_report_ocr_title_seen_count=status_obj.live_report_ocr_title_seen_count,
        live_report_accessibility_action_hits=status_obj.live_report_accessibility_action_hits,
        live_report_template_match_hits=status_obj.live_report_template_match_hits,
        live_report_perceptual_duplicate_count=status_obj.live_report_perceptual_duplicate_count,
        live_report_hard_escape_count=status_obj.live_report_hard_escape_count,
        live_report_submenu_trap_count=status_obj.live_report_submenu_trap_count,
        live_report_checkpoint_at=status_obj.live_report_checkpoint_at,
        route_quality=_to_wechat_agent_route_quality_response(status_obj),
    )


def _to_wechat_agent_dedup_summary_response() -> WechatAgentDedupSummaryResponse:
    summary = read_wechat_agent_dedup_summary()
    return WechatAgentDedupSummaryResponse(
        processed_hashes=summary.processed_hashes,
        run_count=summary.run_count,
        last_run_started_at=summary.last_run_started_at,
        last_run_finished_at=summary.last_run_finished_at,
        last_run_submitted=summary.last_run_submitted,
        last_run_skipped_seen=summary.last_run_skipped_seen,
        last_run_failed=summary.last_run_failed,
        last_run_item_ids=summary.last_run_item_ids,
    )


def _to_wechat_agent_batch_command_response(
    result: WechatAgentBatchCommandResult,
) -> WechatAgentBatchCommandResponse:
    return WechatAgentBatchCommandResponse(
        ok=result.ok,
        message=result.message,
        batch_status=_to_wechat_agent_batch_status_response(result.batch_status),
    )


def _to_wechat_agent_config_response(payload: dict[str, object]) -> WechatAgentConfigResponse:
    return WechatAgentConfigResponse.model_validate(payload)


def _to_wechat_agent_health_response(payload: WechatAgentHealthReport) -> WechatAgentHealthResponse:
    return WechatAgentHealthResponse(
        healthy=payload.healthy,
        checked_at=payload.checked_at,
        stale_threshold_minutes=payload.stale_threshold_minutes,
        running=payload.running,
        last_cycle_at=payload.last_cycle_at,
        minutes_since_last_cycle=payload.minutes_since_last_cycle,
        reasons=payload.reasons,
        recommendation=payload.recommendation,
        status=_to_wechat_agent_status_response(payload.status),
    )


def _to_wechat_agent_self_heal_response(payload: WechatAgentSelfHealResult) -> WechatAgentSelfHealResponse:
    return WechatAgentSelfHealResponse(
        ok=payload.ok,
        action=payload.action,
        message=payload.message,
        health_before=_to_wechat_agent_health_response(payload.health_before),
        health_after=_to_wechat_agent_health_response(payload.health_after),
        output=payload.output,
    )
