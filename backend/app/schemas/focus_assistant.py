from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from app.schemas.tasks import WorkTaskOut


FocusAssistantActionKey = Literal[
    "reading_digest",
    "session_markdown_summary",
    "todo_draft",
    "focus_reference_bundle",
    "personal_wechat_auto_send",
]
FocusAssistantChannel = Literal["workbuddy", "direct"]


class FocusAssistantPlanRequest(BaseModel):
    goal_text: str | None = Field(default=None, max_length=500)
    duration_minutes: int | None = Field(default=None, ge=1, le=180)
    session_id: UUID | None = None
    output_language: str | None = Field(default=None, max_length=10)


class FocusAssistantActionOut(BaseModel):
    key: FocusAssistantActionKey
    title: str
    description: str
    available: bool = True
    reason: str | None = None
    task_type: str | None = None
    session_required: bool = False
    steps: list[str] = Field(default_factory=list)
    handoff_prompt: str | None = None


class FocusAssistantPlanOut(BaseModel):
    goal_text: str | None = None
    duration_minutes: int | None = None
    output_language: str
    latest_session_id: UUID | None = None
    latest_session_status: str | None = None
    focus_reference_count: int = 0
    focus_reference_ids: list[UUID] = Field(default_factory=list)
    focus_reference_titles: list[str] = Field(default_factory=list)
    summary: str
    actions: list[FocusAssistantActionOut] = Field(default_factory=list)
    blocked_actions: list[FocusAssistantActionOut] = Field(default_factory=list)
    guardrails: list[str] = Field(default_factory=list)


class FocusAssistantExecuteRequest(BaseModel):
    action_key: FocusAssistantActionKey
    goal_text: str | None = Field(default=None, max_length=500)
    duration_minutes: int | None = Field(default=None, ge=1, le=180)
    session_id: UUID | None = None
    output_language: str | None = Field(default=None, max_length=10)
    channel: FocusAssistantChannel = "workbuddy"


class FocusAssistantExecuteOut(BaseModel):
    accepted: bool
    action_key: FocusAssistantActionKey
    channel_used: FocusAssistantChannel
    message: str
    task: WorkTaskOut | None = None
