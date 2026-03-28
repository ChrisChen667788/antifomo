from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.items import ItemOut

OutputLanguage = Literal["zh-CN", "zh-TW", "en", "ja", "ko"]


class CollectorOCRIngestRequest(BaseModel):
    image_base64: str = Field(min_length=80)
    mime_type: str = "image/jpeg"
    source_url: str | None = None
    title_hint: str | None = None
    output_language: OutputLanguage = "zh-CN"
    deduplicate: bool = True
    process_immediately: bool = True


class CollectorOCRPreviewRequest(BaseModel):
    image_base64: str = Field(min_length=80)
    mime_type: str = "image/jpeg"
    source_url: str | None = None
    title_hint: str | None = None
    output_language: OutputLanguage = "zh-CN"


class CollectorPluginIngestRequest(BaseModel):
    source_url: str
    title: str | None = None
    raw_content: str = Field(min_length=40)
    output_language: OutputLanguage = "zh-CN"
    deduplicate: bool = True
    process_immediately: bool = True


class CollectorPluginIngestResponse(BaseModel):
    item: ItemOut
    deduplicated: bool = False
    processing_deferred: bool = False
    attempt_id: UUID | None = None
    ingest_route: str = "plugin"
    content_acquisition_status: str = "body_acquired"
    resolver: str | None = None
    body_source: str | None = None
    fallback_used: bool = False


class CollectorURLIngestRequest(BaseModel):
    source_url: str
    title: str | None = None
    output_language: OutputLanguage = "zh-CN"
    deduplicate: bool = True
    process_immediately: bool = True


class CollectorURLResolveRequest(BaseModel):
    title_hint: str | None = None
    body_preview: str | None = None
    body_text: str | None = None
    candidate_limit: int = Field(default=5, ge=1, le=10)


class CollectorURLResolveCandidateResponse(BaseModel):
    source_url: str
    title: str
    source_domain: str | None = None
    search_query: str
    snippet: str
    score: int
    matched_title: bool = False
    matched_excerpt: bool = False


class CollectorURLResolveResponse(BaseModel):
    resolved_url: str | None = None
    confidence: float = 0.0
    resolver: str = "none"
    matched_via: str | None = None
    queries: list[str] = Field(default_factory=list)
    candidates: list[CollectorURLResolveCandidateResponse] = Field(default_factory=list)


class CollectorURLIngestResponse(BaseModel):
    item: ItemOut
    deduplicated: bool = False
    ingest_mode: Literal["url"] = "url"
    processing_deferred: bool = False
    attempt_id: UUID | None = None
    ingest_route: str = "direct_url"
    content_acquisition_status: str = "pending_processing"
    resolver: str | None = None
    body_source: str | None = None
    fallback_used: bool = False


class CollectorOCRIngestResponse(BaseModel):
    item: ItemOut
    ocr_provider: str
    ocr_confidence: float
    ocr_text_length: int
    deduplicated: bool = False
    processing_deferred: bool = False
    attempt_id: UUID | None = None
    ingest_route: str = "ocr"
    content_acquisition_status: str = "body_acquired"
    resolver: str | None = None
    body_source: str | None = None
    fallback_used: bool = False


class CollectorOCRPreviewResponse(BaseModel):
    provider: str
    confidence: float
    text_length: int
    title: str
    body_preview: str
    body_text: str
    keywords: list[str] = Field(default_factory=list)
    quality_ok: bool
    quality_reason: str | None = None


class CollectorStatusResponse(BaseModel):
    user_id: UUID
    now: datetime
    last_24h_total: int
    last_24h_ready: int
    last_24h_processing: int
    last_24h_failed: int
    last_24h_ocr_items: int
    latest_item_at: datetime | None = None


class CollectorProcessPendingResponse(BaseModel):
    scanned: int
    processed: int
    failed: int
    remaining_pending: int
    item_ids: list[UUID]


class CollectorFailedItemOut(BaseModel):
    id: UUID
    title: str | None = None
    source_url: str | None = None
    source_domain: str | None = None
    status: str
    processing_error: str | None = None
    created_at: datetime
    processed_at: datetime | None = None


class CollectorFailedListResponse(BaseModel):
    total_failed: int
    items: list[CollectorFailedItemOut]


class CollectorRetryFailedResponse(BaseModel):
    scanned: int
    retried: int
    ready: int
    failed: int
    item_ids: list[UUID]


class CollectorSummaryItemOut(BaseModel):
    id: UUID
    title: str | None = None
    source_url: str | None = None
    source_domain: str | None = None
    score_value: float | None = None
    action_suggestion: str | None = None
    short_summary: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_at: datetime


class CollectorDailySummaryResponse(BaseModel):
    generated_at: datetime
    range_hours: int
    total_ingested: int
    ready_count: int
    processing_count: int
    failed_count: int
    deep_read_count: int
    later_count: int
    skip_count: int
    top_items: list[CollectorSummaryItemOut]
    failed_items: list[CollectorFailedItemOut]
    markdown: str


class CollectorIngestAttemptOut(BaseModel):
    id: UUID
    item_id: UUID
    source_url: str | None = None
    source_type: str
    route_type: str
    resolver: str | None = None
    attempt_status: str
    error_code: str | None = None
    error_detail: str | None = None
    body_source: str | None = None
    body_length: int | None = None
    confidence: float | None = None
    created_at: datetime


class ItemDiagnosticsOut(BaseModel):
    item_id: UUID
    source_type: str
    source_url: str | None = None
    ingest_route: str = "unknown"
    resolved_from_url: str | None = None
    content_acquisition_status: str = "pending"
    content_acquisition_note: str | None = None
    fallback_used: bool = False
    body_source: str | None = None
    processing_status: str
    processing_error: str | None = None
    latest_attempt: CollectorIngestAttemptOut | None = None
    attempt_count: int = 0


class CollectorSourceCreateRequest(BaseModel):
    source_url: str = Field(min_length=10)
    note: str | None = None
    enabled: bool = True


class CollectorSourceUpdateRequest(BaseModel):
    note: str | None = None
    enabled: bool | None = None


class CollectorSourceOut(BaseModel):
    id: UUID
    source_url: str
    source_domain: str | None = None
    note: str | None = None
    enabled: bool
    last_collected_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class CollectorSourceListResponse(BaseModel):
    total: int
    items: list[CollectorSourceOut]


class CollectorSourceImportRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=500)
    enabled: bool = True


class CollectorSourceImportResult(BaseModel):
    source_url: str
    status: Literal["created", "exists", "invalid"]
    source_id: UUID | None = None
    detail: str | None = None


class CollectorSourceImportResponse(BaseModel):
    total: int
    created: int
    exists: int
    invalid: int
    results: list[CollectorSourceImportResult]


class CollectorFeedSourceCreateRequest(BaseModel):
    source_url: str = Field(min_length=10)
    title: str | None = Field(default=None, max_length=160)
    note: str | None = None
    pull_immediately: bool = True
    output_language: OutputLanguage = "zh-CN"
    limit: int = Field(default=8, ge=1, le=20)


class CollectorFeedSourceOut(BaseModel):
    id: UUID
    feed_type: str
    source_url: str
    title: str
    note: str
    enabled: bool
    status: str
    last_synced_at: datetime | None = None
    last_error: str | None = None
    created_at: datetime
    updated_at: datetime


class CollectorFeedSourceListResponse(BaseModel):
    total: int
    items: list[CollectorFeedSourceOut]


class CollectorFeedPullRequest(BaseModel):
    feed_id: UUID | None = None
    limit: int = Field(default=8, ge=1, le=20)
    output_language: OutputLanguage = "zh-CN"


class CollectorFeedPullResult(BaseModel):
    feed_id: str
    source_url: str
    feed_title: str
    new_items: int = 0
    deduplicated_items: int = 0
    skipped_items: int = 0
    item_ids: list[str] = Field(default_factory=list)
    latest_titles: list[str] = Field(default_factory=list)
    status: str = "ok"
    error: str | None = None
    synced_at: datetime | None = None


class CollectorFeedPullResponse(BaseModel):
    total: int
    results: list[CollectorFeedPullResult] = Field(default_factory=list)


class CollectorNewsletterIngestRequest(BaseModel):
    title: str = Field(min_length=4, max_length=200)
    sender: str | None = Field(default=None, max_length=160)
    source_url: str | None = None
    raw_content: str = Field(min_length=40)
    output_language: OutputLanguage = "zh-CN"


class CollectorFileUploadRequest(BaseModel):
    file_name: str = Field(min_length=1, max_length=255)
    mime_type: str = Field(min_length=3, max_length=120)
    file_base64: str = Field(min_length=20)
    extracted_text: str | None = None
    title: str | None = Field(default=None, max_length=200)
    source_url: str | None = None
    output_language: OutputLanguage = "zh-CN"


class CollectorYouTubeIngestRequest(BaseModel):
    video_url: str = Field(min_length=10)
    transcript_text: str | None = None
    title: str | None = Field(default=None, max_length=200)
    output_language: OutputLanguage = "zh-CN"


class CollectorExternalIngestResponse(BaseModel):
    item: ItemOut
    deduplicated: bool = False
    processing_deferred: bool = False
    attempt_id: UUID | None = None
    ingest_route: str
    content_acquisition_status: str = "body_acquired"
    resolver: str | None = None
    body_source: str | None = None
    fallback_used: bool = False
    metadata: dict = Field(default_factory=dict)


class CollectorDaemonStatusResponse(BaseModel):
    running: bool
    pid: int | None = None
    pid_from_file: int | None = None
    pid_file_present: bool
    uptime_seconds: int | None = None
    last_report_at: datetime | None = None
    last_daily_summary_at: datetime | None = None
    log_file: str
    log_size_bytes: int
    source_file_count: int
    log_tail: list[str] = Field(default_factory=list)


class CollectorDaemonCommandResponse(BaseModel):
    action: Literal["start", "stop", "run_once"]
    ok: bool
    message: str
    status: CollectorDaemonStatusResponse
    output: str | None = None


class WechatAgentStatusResponse(BaseModel):
    running: bool
    pid: int | None = None
    pid_from_file: int | None = None
    pid_file_present: bool
    run_once_running: bool = False
    run_once_pid: int | None = None
    uptime_seconds: int | None = None
    config_file: str
    config_file_present: bool
    state_file: str
    state_file_present: bool
    report_file: str
    report_file_present: bool
    processed_hashes: int
    last_cycle_at: datetime | None = None
    last_cycle_submitted: int = 0
    last_cycle_submitted_new: int = 0
    last_cycle_deduplicated_existing: int = 0
    last_cycle_failed: int = 0
    last_cycle_skipped_seen: int = 0
    last_cycle_skipped_low_quality: int = 0
    last_cycle_error: str | None = None
    last_cycle_new_item_ids: list[str] = Field(default_factory=list)
    log_file: str
    log_size_bytes: int
    log_tail: list[str] = Field(default_factory=list)


class WechatAgentCommandResponse(BaseModel):
    action: Literal["start", "stop", "run_once"]
    ok: bool
    message: str
    status: WechatAgentStatusResponse
    output: str | None = None


class WechatAgentBatchStatusResponse(BaseModel):
    running: bool
    total_items: int = 0
    segment_items: int = 0
    start_batch_index: int = 0
    current_segment_index: int = 0
    total_segments: int = 0
    current_batch_index: int = 0
    started_at: datetime | None = None
    finished_at: datetime | None = None
    submitted: int = 0
    submitted_new: int = 0
    submitted_url: int = 0
    submitted_url_direct: int = 0
    submitted_url_share_copy: int = 0
    submitted_url_resolved: int = 0
    submitted_ocr: int = 0
    deduplicated_existing: int = 0
    deduplicated_existing_url: int = 0
    deduplicated_existing_url_direct: int = 0
    deduplicated_existing_url_share_copy: int = 0
    deduplicated_existing_url_resolved: int = 0
    deduplicated_existing_ocr: int = 0
    skipped_invalid_article: int = 0
    skipped_seen: int = 0
    failed: int = 0
    validation_retries: int = 0
    new_item_ids: list[str] = Field(default_factory=list)
    last_message: str | None = None
    last_error: str | None = None
    live_report_running: bool = False
    live_report_batch: int | None = None
    live_report_row: int | None = None
    live_report_stage: str | None = None
    live_report_detail: str | None = None
    live_report_clicked: int = 0
    live_report_submitted: int = 0
    live_report_submitted_url: int = 0
    live_report_submitted_url_direct: int = 0
    live_report_submitted_url_share_copy: int = 0
    live_report_submitted_url_resolved: int = 0
    live_report_submitted_ocr: int = 0
    live_report_skipped_seen: int = 0
    live_report_skipped_invalid_article: int = 0
    live_report_failed: int = 0
    live_report_checkpoint_at: datetime | None = None


class WechatAgentDedupSummaryResponse(BaseModel):
    processed_hashes: int = 0
    run_count: int = 0
    last_run_started_at: datetime | None = None
    last_run_finished_at: datetime | None = None
    last_run_submitted: int = 0
    last_run_skipped_seen: int = 0
    last_run_failed: int = 0
    last_run_item_ids: list[str] = Field(default_factory=list)


class WechatAgentBatchCommandResponse(BaseModel):
    ok: bool
    message: str
    batch_status: WechatAgentBatchStatusResponse


class WechatAgentConfigResponse(BaseModel):
    api_base: str
    output_language: OutputLanguage
    coordinate_mode: Literal["auto", "absolute", "window_relative"]
    article_link_profile: Literal["auto", "compact", "standard", "wide", "manual"]
    wechat_bundle_id: str
    wechat_app_name: str
    public_account_origin: dict[str, int]
    public_account_hotspots: list[dict[str, int]]
    list_origin: dict[str, int]
    article_row_height: int
    rows_per_batch: int
    batches_per_cycle: int
    article_open_wait_sec: float
    article_capture_region: dict[str, int]
    article_link_hotspots: list[dict[str, int]]
    article_link_menu_offsets: list[dict[str, int]]
    article_reset_page_up: int
    article_extra_page_down: int
    feed_reset_page_up: int
    page_down_wait_sec: float
    list_page_down_after_batch: int
    duplicate_escape_page_down: int
    duplicate_escape_max_extra_pages: int
    between_item_delay_sec: float
    dedup_max_hashes: int
    min_capture_file_size_kb: int
    article_allow_ocr_fallback: bool
    article_verify_with_ocr: bool
    article_verify_min_text_length: int
    article_verify_retries: int
    loop_interval_sec: int
    health_stale_minutes: int


class WechatAgentConfigPatchRequest(BaseModel):
    api_base: str | None = None
    output_language: OutputLanguage | None = None
    coordinate_mode: Literal["auto", "absolute", "window_relative"] | None = None
    article_link_profile: Literal["auto", "compact", "standard", "wide", "manual"] | None = None
    wechat_bundle_id: str | None = None
    wechat_app_name: str | None = None
    public_account_origin: dict[str, int] | None = None
    public_account_hotspots: list[dict[str, int]] | None = None
    list_origin: dict[str, int] | None = None
    article_row_height: int | None = None
    rows_per_batch: int | None = None
    batches_per_cycle: int | None = None
    article_open_wait_sec: float | None = None
    article_capture_region: dict[str, int] | None = None
    article_link_hotspots: list[dict[str, int]] | None = None
    article_link_menu_offsets: list[dict[str, int]] | None = None
    article_reset_page_up: int | None = None
    article_extra_page_down: int | None = None
    feed_reset_page_up: int | None = None
    page_down_wait_sec: float | None = None
    list_page_down_after_batch: int | None = None
    duplicate_escape_page_down: int | None = None
    duplicate_escape_max_extra_pages: int | None = None
    between_item_delay_sec: float | None = None
    dedup_max_hashes: int | None = None
    min_capture_file_size_kb: int | None = None
    article_allow_ocr_fallback: bool | None = None
    article_verify_with_ocr: bool | None = None
    article_verify_min_text_length: int | None = None
    article_verify_retries: int | None = None
    loop_interval_sec: int | None = None
    health_stale_minutes: int | None = None


class WechatAgentCapturePreviewResponse(BaseModel):
    captured_at: datetime
    image_base64: str
    mime_type: str = "image/png"
    region: dict[str, int]
    image_size_bytes: int


class WechatAgentOCRPreviewResponse(BaseModel):
    captured_at: datetime
    provider: str
    confidence: float
    text_length: int
    title: str
    body_preview: str
    keywords: list[str] = Field(default_factory=list)
    quality_ok: bool
    quality_reason: str | None = None


class WechatAgentHealthResponse(BaseModel):
    healthy: bool
    checked_at: datetime
    stale_threshold_minutes: int
    running: bool
    last_cycle_at: datetime | None = None
    minutes_since_last_cycle: float | None = None
    reasons: list[str] = Field(default_factory=list)
    recommendation: str | None = None
    status: WechatAgentStatusResponse


class WechatAgentSelfHealResponse(BaseModel):
    ok: bool
    action: Literal["none", "start", "restart"]
    message: str
    health_before: WechatAgentHealthResponse
    health_after: WechatAgentHealthResponse
    output: str | None = None
