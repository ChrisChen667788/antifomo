from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class KnowledgeEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    item_id: UUID | None = None
    title: str
    content: str
    source_domain: str | None = None
    metadata_payload: dict | None = None
    collection_name: str | None = None
    is_pinned: bool = False
    is_focus_reference: bool = False
    created_at: datetime
    updated_at: datetime | None = None


class KnowledgeEntryListResponse(BaseModel):
    items: list[KnowledgeEntryOut] = Field(default_factory=list)


class KnowledgeRuleOut(BaseModel):
    enabled: bool = True
    min_score_value: float = 4.0
    archive_on_like: bool = True
    archive_on_save: bool = True


class KnowledgeRuleUpdateRequest(BaseModel):
    enabled: bool | None = None
    min_score_value: float | None = Field(default=None, ge=1.0, le=5.0)
    archive_on_like: bool | None = None
    archive_on_save: bool | None = None


class KnowledgeEntryUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    content: str | None = Field(default=None, min_length=1, max_length=8000)
    collection_name: str | None = Field(default=None, max_length=80)
    is_pinned: bool | None = None
    is_focus_reference: bool | None = None
    metadata_payload: dict | None = None

    @model_validator(mode="after")
    def validate_has_any_field(self) -> "KnowledgeEntryUpdateRequest":
        if not self.model_fields_set:
            raise ValueError("At least one field must be provided")
        return self


class KnowledgeBatchUpdateRequest(BaseModel):
    entry_ids: list[UUID] = Field(min_length=1, max_length=24)
    collection_name: str | None = Field(default=None, max_length=80)
    is_pinned: bool | None = None
    is_focus_reference: bool | None = None

    @model_validator(mode="after")
    def validate_has_any_patch(self) -> "KnowledgeBatchUpdateRequest":
        patch_fields = {
            field_name
            for field_name in ("collection_name", "is_pinned", "is_focus_reference")
            if field_name in self.model_fields_set
        }
        if not patch_fields:
            raise ValueError("At least one patch field must be provided")
        return self


class KnowledgeMergeRequest(BaseModel):
    entry_ids: list[UUID] = Field(min_length=2, max_length=12)
    title: str | None = Field(default=None, max_length=120)
    content: str | None = Field(default=None, max_length=12000)


class KnowledgeMergePreviewRequest(BaseModel):
    entry_ids: list[UUID] = Field(min_length=1, max_length=12)
    title: str | None = Field(default=None, max_length=120)


class KnowledgeMergePreviewOut(BaseModel):
    title: str
    count: int
    titles: list[str] = Field(default_factory=list)
    more_count: int = 0
    inherit_pinned: bool = False
    inherit_focus_reference: bool = False
    inherit_collection: str | None = None
    ready: bool = False


class KnowledgeMarkdownOut(BaseModel):
    filename: str
    content: str
    entry_count: int = 1


class KnowledgeBatchMarkdownRequest(BaseModel):
    entry_ids: list[UUID] = Field(min_length=1, max_length=24)
    title: str | None = Field(default=None, max_length=120)
    output_language: str | None = Field(default=None, max_length=10)
