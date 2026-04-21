from __future__ import annotations

from app.api import collector as collector_api
from app.services.wechat_pc_agent_daemon import WechatAgentBatchStatus


def _status(**overrides) -> WechatAgentBatchStatus:
    base = {
        "running": False,
        "total_items": 12,
        "segment_items": 6,
        "start_batch_index": 0,
        "current_segment_index": 2,
        "total_segments": 2,
        "current_batch_index": 1,
        "started_at": None,
        "finished_at": None,
        "submitted": 8,
        "submitted_new": 5,
        "submitted_url": 6,
        "submitted_url_direct": 3,
        "submitted_url_share_copy": 2,
        "submitted_url_resolved": 1,
        "submitted_ocr": 1,
        "deduplicated_existing": 2,
        "deduplicated_existing_url": 1,
        "deduplicated_existing_url_direct": 1,
        "deduplicated_existing_url_share_copy": 0,
        "deduplicated_existing_url_resolved": 0,
        "deduplicated_existing_ocr": 0,
        "skipped_invalid_article": 0,
        "skipped_seen": 1,
        "failed": 0,
        "validation_retries": 1,
        "duplicate_escape_count": 1,
        "route_backoff_count": 0,
        "route_circuit_breaker_count": 0,
        "recovery_action_count": 0,
        "url_only_skip_count": 0,
        "ocr_preview_seen_count": 0,
        "ocr_title_seen_count": 0,
        "accessibility_action_hits": 5,
        "template_match_hits": 1,
        "perceptual_duplicate_count": 1,
        "new_item_ids": [],
        "last_message": None,
        "last_error": None,
        "live_report_running": False,
        "live_report_batch": None,
        "live_report_row": None,
        "live_report_stage": None,
        "live_report_detail": None,
        "live_report_clicked": 0,
        "live_report_submitted": 0,
        "live_report_submitted_url": 0,
        "live_report_submitted_url_direct": 0,
        "live_report_submitted_url_share_copy": 0,
        "live_report_submitted_url_resolved": 0,
        "live_report_submitted_ocr": 0,
        "live_report_skipped_seen": 0,
        "live_report_skipped_invalid_article": 0,
        "live_report_failed": 0,
        "live_report_duplicate_escape_count": 0,
        "live_report_route_backoff_count": 0,
        "live_report_route_circuit_breaker_count": 0,
        "live_report_recovery_action_count": 0,
        "live_report_url_only_skip_count": 0,
        "live_report_ocr_preview_seen_count": 0,
        "live_report_ocr_title_seen_count": 0,
        "live_report_accessibility_action_hits": 0,
        "live_report_template_match_hits": 0,
        "live_report_perceptual_duplicate_count": 0,
        "live_report_checkpoint_at": None,
    }
    base.update(overrides)
    return WechatAgentBatchStatus(**base)


def test_route_quality_reports_good_when_url_first_dominates() -> None:
    quality = collector_api._to_wechat_agent_route_quality_response(_status())

    assert quality.route_stability == "good"
    assert quality.url_first_share >= 80
    assert quality.ocr_share <= 20


def test_route_quality_reports_poor_when_ocr_and_backoff_dominate() -> None:
    quality = collector_api._to_wechat_agent_route_quality_response(
        _status(
            submitted_url_direct=1,
            submitted_url_share_copy=0,
            submitted_url_resolved=1,
            submitted_ocr=4,
            route_backoff_count=3,
            route_circuit_breaker_count=1,
            ocr_preview_seen_count=2,
        )
    )

    assert quality.route_stability == "poor"
    assert quality.ocr_share >= 50
    assert "OCR" in quality.recommendation or "浏览器" in quality.recommendation
