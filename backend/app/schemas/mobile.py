from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MobileDailyBriefItemOut(BaseModel):
    id: str
    title: str
    source_domain: str
    summary: str
    action_suggestion: str
    score_value: float | None = None
    source_url: str | None = None


class MobileDailyBriefWatchlistChangeOut(BaseModel):
    id: str
    change_type: str
    summary: str
    severity: str
    created_at: str | None = None


class MobileDailyBriefResponse(BaseModel):
    snapshot_id: str
    brief_date: str
    headline: str
    summary: str
    top_items: list[MobileDailyBriefItemOut] = Field(default_factory=list)
    watchlist_changes: list[MobileDailyBriefWatchlistChangeOut] = Field(default_factory=list)
    generated_at: str | None = None
    audio_status: Literal["pending", "ready", "unavailable"] = "pending"
    audio_url: str | None = None
    audio_script: str | None = None
