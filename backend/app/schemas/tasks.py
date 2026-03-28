from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class WorkTaskCreateRequest(BaseModel):
    task_type: str = Field(
        pattern="^(export_markdown_summary|export_reading_list|export_todo_draft|export_knowledge_markdown|export_knowledge_bundle_markdown|export_research_report_markdown|export_research_report_word|export_research_report_pdf|export_exec_brief|export_sales_brief|export_outreach_draft|export_watchlist_digest)$"
    )
    session_id: UUID | None = None
    input_payload: dict | None = None


class WorkTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    user_id: UUID
    session_id: UUID | None = None
    task_type: str
    input_payload: dict | None = None
    output_payload: dict | None = None
    status: str
    error_message: str | None = None
    created_at: datetime
    finished_at: datetime | None = None
