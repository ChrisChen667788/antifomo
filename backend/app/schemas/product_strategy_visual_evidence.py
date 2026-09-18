from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class VisualChecklistItem(StrictModel):
    status: Literal["pass", "fail", "unknown"]
    note: str = Field(default="", max_length=2000)


class VisualChecklist(StrictModel):
    clipping: VisualChecklistItem
    overlap: VisualChecklistItem
    legibility: VisualChecklistItem
    assets: VisualChecklistItem
    pagination: VisualChecklistItem


class VisualViewport(StrictModel):
    width: int = Field(gt=0, le=16384, strict=True)
    height: int = Field(gt=0, le=16384, strict=True)
    device_scale_factor: float = Field(gt=0, le=8)


class VisualEvidenceCreateRequest(StrictModel):
    office_receipt_key: str = Field(min_length=1, max_length=240)
    expected_office_receipt_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    surface_key: str = Field(min_length=1, max_length=120)
    capture_kind: Literal["office_page", "desktop_browser", "mobile_viewport"]
    source_version: str = Field(min_length=1, max_length=120)
    file_name: str = Field(min_length=5, max_length=240)
    image_base64: str = Field(min_length=1, max_length=11184816)
    viewport: VisualViewport | None = None
    office_page_number: int | None = Field(default=None, gt=0, le=10000, strict=True)
    checklist: VisualChecklist
    notes: str = Field(default="", max_length=10000)
    previous_revision_digest: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def validate_capture_context(self) -> "VisualEvidenceCreateRequest":
        if self.capture_kind == "office_page" and self.office_page_number is None:
            raise ValueError("Office 页面证据必须填写页码。")
        if self.capture_kind != "office_page":
            if self.viewport is None:
                raise ValueError("浏览器截图必须填写实际 viewport。")
            if self.office_page_number is not None:
                raise ValueError("浏览器截图不能标记为 Office 页码。")
        return self


class VisualFieldDiff(StrictModel):
    field_path: str
    before: Any = None
    after: Any = None
    change_type: Literal["added", "removed", "changed"]


class VisualEvidenceRevisionOut(StrictModel):
    id: str
    revision_key: str
    office_receipt_key: str
    office_receipt_digest: str
    artifact_key: str
    artifact_revision: int
    artifact_revision_digest: str
    surface_key: str
    capture_kind: Literal["office_page", "desktop_browser", "mobile_viewport"]
    source_version: str
    file_name: str
    image_sha256: str
    image_width: int
    image_height: int
    viewport: VisualViewport | None
    office_page_number: int | None
    checklist: VisualChecklist
    notes: str
    revision: int
    previous_revision_digest: str | None
    revision_digest: str
    field_level_diff: list[VisualFieldDiff]
    review_status: Literal["needs_revision", "recorded_unverified"]
    human_review_status: Literal["missing"]
    acceptance_status: Literal["hold"]
    blocking_status: Literal["blocked"]
    can_auto_accept: Literal[False]
    can_auto_approve_release: Literal[False]
    production_status: Literal["not_authorized"]
    created_at: str


class VisualEvidenceCreateOut(StrictModel):
    outcome: Literal["created", "existing"]
    deduplicated: bool
    revision: VisualEvidenceRevisionOut


class VisualEvidenceLandscapeOut(StrictModel):
    visual_evidence_version: Literal["2.10.6"]
    revisions: list[VisualEvidenceRevisionOut]
    revision_count: int
    needs_revision_count: int
    acceptance_status: Literal["hold"]
    blocking_status: Literal["blocked"]
    note: str


class ResponsiveEvidenceOut(StrictModel):
    responsive_evidence_version: Literal["2.11.3"]
    desktop_browser_count: int = Field(ge=0)
    mobile_viewport_count: int = Field(ge=0)
    office_page_count: int = Field(ge=0)
    latest_revision_digests: list[str]
    physical_device_capture: Literal[False] = False
    production_performance_benchmark: Literal[False] = False
    blockers: list[str]
    acceptance_status: Literal["hold"] = "hold"
    blocking_status: Literal["blocked"] = "blocked"
    production_status: Literal["not_authorized"] = "not_authorized"
    can_auto_accept: Literal[False] = False
    can_auto_approve_release: Literal[False] = False
    note: str
