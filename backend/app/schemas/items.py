from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

OutputLanguage = Literal["zh-CN", "zh-TW", "en", "ja", "ko"]


class ItemCreateRequest(BaseModel):
    source_type: str = Field(pattern="^(url|text|plugin)$")
    source_url: str | None = None
    title: str | None = None
    raw_content: str | None = None
    output_language: OutputLanguage = "zh-CN"

    @model_validator(mode="after")
    def validate_payload(self) -> "ItemCreateRequest":
        if self.source_type == "url" and not self.source_url:
            raise ValueError("source_url is required when source_type is url")
        if self.source_type == "text" and not self.raw_content:
            raise ValueError("raw_content is required when source_type is text")
        if self.source_type == "plugin" and not (self.source_url or self.raw_content):
            raise ValueError("source_url or raw_content is required when source_type is plugin")
        return self


class ItemBatchCreateRequest(BaseModel):
    source_type: str = Field(default="url", pattern="^(url|plugin)$")
    urls: list[str] = Field(min_length=1, max_length=200)
    deduplicate: bool = True
    output_language: OutputLanguage = "zh-CN"

    @model_validator(mode="after")
    def validate_urls(self) -> "ItemBatchCreateRequest":
        normalized: list[str] = []
        for raw in self.urls:
            value = raw.strip()
            if not value:
                continue
            normalized.append(value)

        if not normalized:
            raise ValueError("urls must contain at least one non-empty URL")

        self.urls = normalized
        return self


class ItemBatchCreateResult(BaseModel):
    source_url: str
    status: Literal["created", "skipped", "invalid"]
    item_id: UUID | None = None
    detail: str | None = None


class ItemBatchCreateResponse(BaseModel):
    total: int
    created: int
    skipped: int
    invalid: int
    results: list[ItemBatchCreateResult]


class ItemTagOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tag_name: str
    created_at: datetime


class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    source_type: str
    source_url: str | None = None
    source_domain: str | None = None
    title: str | None = None
    raw_content: str | None = None
    clean_content: str | None = None
    short_summary: str | None = None
    long_summary: str | None = None
    score_value: float | None = None
    action_suggestion: str | None = None
    output_language: OutputLanguage = "zh-CN"
    ingest_route: str | None = None
    content_acquisition_status: str = "pending"
    content_acquisition_note: str | None = None
    resolved_from_url: str | None = None
    fallback_used: bool = False
    status: str
    processing_error: str | None = None
    created_at: datetime
    processed_at: datetime | None = None
    tags: list[ItemTagOut] = Field(default_factory=list)
    recommendation_score: float | None = None
    recommendation_bucket: str | None = None
    recommendation_reason: list[str] = Field(default_factory=list)
    topic_match_score: float | None = None
    source_match_score: float | None = None
    preference_version: str | None = None
    matched_preferences: list[str] = Field(default_factory=list)
    why_recommended: list[str] = Field(default_factory=list)


class ItemListResponse(BaseModel):
    items: list[ItemOut]


class ItemInterpretRequest(BaseModel):
    output_language: OutputLanguage | None = None


class ItemInterpretResponse(BaseModel):
    item_id: UUID
    output_language: OutputLanguage = "zh-CN"
    insight_title: str
    expert_take: str
    key_signals: list[str] = Field(default_factory=list)
    knowledge_note: str


class ItemKnowledgeSaveRequest(BaseModel):
    title: str | None = None
    content: str | None = None
    output_language: OutputLanguage | None = None


class ItemKnowledgeSaveResponse(BaseModel):
    entry_id: UUID
    item_id: UUID
    title: str
    content: str
    source_domain: str | None = None
    created_at: datetime


class ItemReprocessRequest(BaseModel):
    output_language: OutputLanguage | None = None


class ItemReprocessResponse(BaseModel):
    item_id: UUID
    status: str
    output_language: OutputLanguage = "zh-CN"


class ItemFeedbackRequest(BaseModel):
    feedback_type: str = Field(pattern="^(ignore|like|save|open_detail|inaccurate)$")


class ItemFeedbackResponse(BaseModel):
    item_id: UUID
    feedback_type: str
    status: str
    knowledge_entry_id: UUID | None = None
    knowledge_status: str | None = None
    knowledge_trigger: str | None = None
    knowledge_threshold: float | None = None
    knowledge_score_value: float | None = None
