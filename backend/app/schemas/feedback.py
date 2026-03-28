from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class FeedbackCreateRequest(BaseModel):
    item_id: UUID
    feedback_type: str = Field(pattern="^(ignore|like|save|open_detail|inaccurate)$")


class FeedbackCreateResponse(BaseModel):
    item_id: UUID
    feedback_type: str
    status: str

