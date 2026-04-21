from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from app.schemas.tasks import WorkTaskOut


WorkBuddyTaskType = Literal[
    "export_markdown_summary",
    "export_reading_list",
    "export_todo_draft",
    "export_knowledge_markdown",
    "export_knowledge_bundle_markdown",
    "export_research_report_markdown",
    "export_research_report_word",
    "export_research_report_pdf",
]
WorkBuddyEventType = Literal["ping", "create_task"]


class WorkBuddyCallbackConfig(BaseModel):
    url: str | None = None
    headers: dict[str, str] = Field(default_factory=dict)


class WorkBuddyWebhookRequest(BaseModel):
    event_type: WorkBuddyEventType = "create_task"
    request_id: str | None = None
    task_type: WorkBuddyTaskType | None = None
    session_id: UUID | None = None
    input_payload: dict | None = None
    callback: WorkBuddyCallbackConfig | None = None

    @model_validator(mode="after")
    def validate_payload(self) -> "WorkBuddyWebhookRequest":
        if self.event_type == "create_task" and not self.task_type:
            raise ValueError("task_type is required when event_type is create_task")
        return self


class WorkBuddyCallbackResultOut(BaseModel):
    attempted: bool = False
    ok: bool | None = None
    status_code: int | None = None
    detail: str | None = None


class WorkBuddyWebhookResponse(BaseModel):
    accepted: bool
    event_type: WorkBuddyEventType
    request_id: str | None = None
    message: str
    signature_check: str | None = None
    task: WorkTaskOut | None = None
    callback: WorkBuddyCallbackResultOut = Field(default_factory=WorkBuddyCallbackResultOut)
