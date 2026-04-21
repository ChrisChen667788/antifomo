from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class PreferenceScoreOut(BaseModel):
    key: str
    preference_score: float
    mapped_score: float
    updated_at: datetime | None = None


class PreferenceSummaryOut(BaseModel):
    user_id: UUID
    generated_at: datetime
    preference_version: str
    feedback_total: int = 0
    last_feedback_at: datetime | None = None
    recent_feedback_counts: dict[str, int] = Field(default_factory=dict)
    top_tags: list[PreferenceScoreOut] = Field(default_factory=list)
    top_domains: list[PreferenceScoreOut] = Field(default_factory=list)
    snapshot_id: UUID | None = None


class PreferenceResetRequest(BaseModel):
    scope: Literal["all", "topics", "sources"] = "all"


class PreferenceBoostRequest(BaseModel):
    dimension: Literal["topic", "source"]
    key: str = Field(min_length=1, max_length=255)
    delta: float = Field(default=1.0, ge=-10.0, le=10.0)


class PreferenceBoostResponse(BaseModel):
    dimension: Literal["topic", "source"]
    key: str
    delta: float
    updated_score: float
    summary: PreferenceSummaryOut
