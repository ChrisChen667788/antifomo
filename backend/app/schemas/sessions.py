from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

OutputLanguage = Literal["zh-CN", "zh-TW", "en", "ja", "ko"]


class SessionStartRequest(BaseModel):
    goal_text: str | None = None
    duration_minutes: int = Field(ge=1, le=240)
    output_language: OutputLanguage = "zh-CN"


class SessionFinishRequest(BaseModel):
    output_language: OutputLanguage | None = None


class SessionItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    title: str | None = None
    source_domain: str | None = None
    short_summary: str | None = None
    action_suggestion: str | None = None
    score_value: float | None = None
    tags: list[str] = Field(default_factory=list)


class SessionMetricsOut(BaseModel):
    new_content_count: int = 0
    deep_read_count: int = 0
    later_count: int = 0
    skip_count: int = 0


class SessionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    goal_text: str | None = None
    output_language: OutputLanguage = "zh-CN"
    duration_minutes: int
    start_time: datetime
    end_time: datetime | None = None
    status: str
    summary_text: str | None = None
    created_at: datetime
    metrics: SessionMetricsOut = Field(default_factory=SessionMetricsOut)
    items: list[SessionItemOut] = Field(default_factory=list)


class SessionFinishResponse(BaseModel):
    session: SessionOut


class SessionTodoCalendarRequest(BaseModel):
    output_language: OutputLanguage | None = None
    calendar_name: str | None = None
    todo_markdown: str | None = None


class SessionTodoCalendarEventOut(BaseModel):
    title: str
    notes: str
    start_time: datetime
    end_time: datetime


class SessionTodoCalendarPreviewResponse(BaseModel):
    calendar_name: str
    summary_title: str
    task_count: int
    tasks: list[str] = Field(default_factory=list)
    events: list[SessionTodoCalendarEventOut] = Field(default_factory=list)
    markdown: str


class SessionTodoCalendarImportResponse(BaseModel):
    calendar_name: str
    imported_count: int
    imported_titles: list[str] = Field(default_factory=list)


class SessionArtifactItemOut(BaseModel):
    id: UUID
    item_id: UUID | None = None
    position: int
    included_reason: str | None = None
    title_snapshot: str
    source_url_snapshot: str | None = None
    created_at: datetime


class SessionArtifactOut(BaseModel):
    id: UUID
    work_task_id: UUID
    session_id: UUID | None = None
    artifact_type: str
    markdown: str
    created_at: datetime
    items: list[SessionArtifactItemOut] = Field(default_factory=list)
