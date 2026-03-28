from __future__ import annotations

from decimal import Decimal
from difflib import SequenceMatcher
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.session import get_db
from app.models.entities import KnowledgeEntry
from app.schemas.knowledge import (
    KnowledgeBatchMarkdownRequest,
    KnowledgeBatchUpdateRequest,
    KnowledgeEntryListResponse,
    KnowledgeMarkdownOut,
    KnowledgeEntryOut,
    KnowledgeMergePreviewOut,
    KnowledgeMergePreviewRequest,
    KnowledgeEntryUpdateRequest,
    KnowledgeMergeRequest,
    KnowledgeRuleOut,
    KnowledgeRuleUpdateRequest,
)
from app.services.knowledge_service import ensure_knowledge_rule
from app.services.user_context import ensure_demo_user


router = APIRouter(prefix="/api/knowledge", tags=["knowledge"])
settings = get_settings()


def _get_entry_or_404(db: Session, entry_id: UUID) -> KnowledgeEntry:
    entry = db.scalar(
        select(KnowledgeEntry)
        .where(KnowledgeEntry.id == entry_id)
        .where(KnowledgeEntry.user_id == settings.single_user_id)
        .options(selectinload(KnowledgeEntry.item))
    )
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")
    return entry


def _resolve_entry_title(entry: KnowledgeEntry) -> str:
    def is_placeholder(value: str) -> bool:
        return value.lower().startswith(("wechat auto", "wechat ocr"))

    raw_title = (entry.title or "").strip()
    if raw_title and not is_placeholder(raw_title):
        return raw_title

    item_title = (entry.item.title if entry.item else "") or ""
    item_title = item_title.strip()
    if item_title and not is_placeholder(item_title):
        return item_title

    content = (entry.content or "").replace("\n", " ").strip()
    if content.startswith("知识库笔记："):
        content = content.split("：", 1)[1].strip()
    if content.lower().startswith("knowledge note:"):
        content = content.split(":", 1)[1].strip()

    for segment in content.replace("。", ".").replace("！", ".").replace("？", ".").split("."):
        candidate = segment.strip().strip("，,、:：- ")
        if is_placeholder(candidate):
            continue
        if len(candidate) >= 8:
            return candidate[:30]

    return raw_title or "知识卡片"


def _to_entry_out(entry: KnowledgeEntry) -> KnowledgeEntryOut:
    return KnowledgeEntryOut(
        id=entry.id,
        item_id=entry.item_id,
        title=_resolve_entry_title(entry),
        content=entry.content,
        source_domain=entry.source_domain,
        metadata_payload=entry.metadata_payload,
        collection_name=entry.collection_name,
        is_pinned=entry.is_pinned,
        is_focus_reference=entry.is_focus_reference,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _build_merge_title(entries: list[KnowledgeEntry]) -> str:
    titles = [_resolve_entry_title(entry) for entry in entries]
    unique_titles: list[str] = []
    for title in titles:
        if title and title not in unique_titles:
            unique_titles.append(title)
    if not unique_titles:
        return "合并知识卡片"
    if len(unique_titles) == 1:
        return f"{unique_titles[0]} / 综合卡片"[:120]
    return f"{unique_titles[0]} + {len(unique_titles) - 1} 条延展"[:120]


def _build_merge_content(entries: list[KnowledgeEntry]) -> str:
    blocks: list[str] = []
    for index, entry in enumerate(entries, start=1):
        blocks.append(f"{index}. {_resolve_entry_title(entry)}\n{entry.content.strip()}")
    return "\n\n".join(blocks)


def _build_merge_collection_name(entries: list[KnowledgeEntry]) -> str | None:
    collection_names = {
        (entry.collection_name or "").strip()
        for entry in entries
        if (entry.collection_name or "").strip()
    }
    if len(collection_names) == 1:
        return next(iter(collection_names))
    return None


def _build_markdown_filename(entry: KnowledgeEntry) -> str:
    title = _resolve_entry_title(entry)
    safe_title = re.sub(r"[^A-Za-z0-9\u4e00-\u9fff\-_ ]+", "", title).strip().replace(" ", "_")
    if not safe_title:
        safe_title = "knowledge-card"
    return f"{safe_title[:48]}.md"


def _build_markdown_content(entry: KnowledgeEntry) -> str:
    lines = [
        f"# {_resolve_entry_title(entry)}",
        "",
        f"- 来源: {entry.source_domain or '未知来源'}",
        f"- 创建时间: {entry.created_at.isoformat()}",
    ]
    if entry.updated_at:
        lines.append(f"- 最近更新: {entry.updated_at.isoformat()}")
    if entry.collection_name:
        lines.append(f"- 分组: {entry.collection_name}")
    if entry.is_focus_reference:
        lines.append("- Focus 参考: 是")
    lines.append(f"- 置顶: {'是' if entry.is_pinned else '否'}")
    lines.extend(["", "## 卡片内容", "", entry.content.strip()])
    return "\n".join(lines)


def _normalize_compare_text(value: str | None) -> str:
    return " ".join((value or "").lower().split())[:600]


def _compute_related_score(target: KnowledgeEntry, candidate: KnowledgeEntry) -> float:
    title_ratio = SequenceMatcher(
        None,
        _normalize_compare_text(_resolve_entry_title(target)),
        _normalize_compare_text(_resolve_entry_title(candidate)),
    ).ratio()
    content_ratio = SequenceMatcher(
        None,
        _normalize_compare_text(target.content),
        _normalize_compare_text(candidate.content),
    ).ratio()
    score = title_ratio * 72 + content_ratio * 28
    if target.source_domain and candidate.source_domain and target.source_domain == candidate.source_domain:
        score += 18
    if target.item_id and candidate.item_id and target.item_id == candidate.item_id:
        score += 26
    return score


@router.get("/rules", response_model=KnowledgeRuleOut)
def get_knowledge_rule(db: Session = Depends(get_db)) -> KnowledgeRuleOut:
    ensure_demo_user(db)
    rule = ensure_knowledge_rule(db, settings.single_user_id)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return KnowledgeRuleOut(
        enabled=rule.enabled,
        min_score_value=float(rule.min_score_value),
        archive_on_like=rule.archive_on_like,
        archive_on_save=rule.archive_on_save,
    )


@router.put("/rules", response_model=KnowledgeRuleOut)
def update_knowledge_rule(
    payload: KnowledgeRuleUpdateRequest,
    db: Session = Depends(get_db),
) -> KnowledgeRuleOut:
    ensure_demo_user(db)
    rule = ensure_knowledge_rule(db, settings.single_user_id)
    if payload.enabled is not None:
        rule.enabled = payload.enabled
    if payload.min_score_value is not None:
        rule.min_score_value = Decimal(str(payload.min_score_value))
    if payload.archive_on_like is not None:
        rule.archive_on_like = payload.archive_on_like
    if payload.archive_on_save is not None:
        rule.archive_on_save = payload.archive_on_save
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return KnowledgeRuleOut(
        enabled=rule.enabled,
        min_score_value=float(rule.min_score_value),
        archive_on_like=rule.archive_on_like,
        archive_on_save=rule.archive_on_save,
    )


@router.get("", response_model=KnowledgeEntryListResponse)
def list_knowledge_entries(
    limit: int = 30,
    item_id: UUID | None = None,
    focus_reference_only: bool = False,
    source_domain: str | None = None,
    collection_name: str | None = None,
    query: str | None = None,
    db: Session = Depends(get_db),
) -> KnowledgeEntryListResponse:
    ensure_demo_user(db)
    stmt = (
        select(KnowledgeEntry)
        .where(KnowledgeEntry.user_id == settings.single_user_id)
        .options(selectinload(KnowledgeEntry.item))
        .order_by(
            desc(KnowledgeEntry.is_focus_reference),
            desc(KnowledgeEntry.is_pinned),
            desc(KnowledgeEntry.created_at),
        )
        .limit(max(1, min(limit, 100)))
    )
    if item_id is not None:
        stmt = stmt.where(KnowledgeEntry.item_id == item_id)
    if focus_reference_only:
        stmt = stmt.where(KnowledgeEntry.is_focus_reference.is_(True))
    if source_domain:
        stmt = stmt.where(KnowledgeEntry.source_domain == source_domain.strip())
    if collection_name:
        stmt = stmt.where(KnowledgeEntry.collection_name == collection_name.strip())
    if query:
        normalized_query = f"%{query.strip()}%"
        stmt = stmt.where(
            KnowledgeEntry.title.ilike(normalized_query) | KnowledgeEntry.content.ilike(normalized_query)
        )
    items = list(db.scalars(stmt))
    return KnowledgeEntryListResponse(
        items=[_to_entry_out(item) for item in items]
    )


@router.post("/merge/preview", response_model=KnowledgeMergePreviewOut)
def preview_merge_knowledge_entries(
    payload: KnowledgeMergePreviewRequest,
    db: Session = Depends(get_db),
) -> KnowledgeMergePreviewOut:
    ensure_demo_user(db)
    unique_ids = list(dict.fromkeys(payload.entry_ids))
    entries = list(
        db.scalars(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.user_id == settings.single_user_id)
            .where(KnowledgeEntry.id.in_(unique_ids))
            .options(selectinload(KnowledgeEntry.item))
        )
    )
    if len(entries) != len(unique_ids):
        raise HTTPException(status_code=404, detail="Some knowledge entries were not found")

    order = {entry_id: index for index, entry_id in enumerate(unique_ids)}
    entries.sort(key=lambda entry: order.get(entry.id, 0))
    collection_name = _build_merge_collection_name(entries)
    preview_title = (payload.title or "").strip() or _build_merge_title(entries)

    return KnowledgeMergePreviewOut(
        title=preview_title,
        count=len(entries),
        titles=[_resolve_entry_title(entry) for entry in entries[:3]],
        more_count=max(0, len(entries) - 3),
        inherit_pinned=any(entry.is_pinned for entry in entries),
        inherit_focus_reference=any(entry.is_focus_reference for entry in entries),
        inherit_collection=collection_name,
        ready=len(entries) >= 2,
    )


@router.post("/merge", response_model=KnowledgeEntryOut)
def merge_knowledge_entries(
    payload: KnowledgeMergeRequest,
    db: Session = Depends(get_db),
) -> KnowledgeEntryOut:
    ensure_demo_user(db)
    unique_ids = list(dict.fromkeys(payload.entry_ids))
    if len(unique_ids) < 2:
        raise HTTPException(status_code=400, detail="At least two knowledge entries are required")

    entries = list(
        db.scalars(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.user_id == settings.single_user_id)
            .where(KnowledgeEntry.id.in_(unique_ids))
            .options(selectinload(KnowledgeEntry.item))
        )
    )
    if len(entries) != len(unique_ids):
        raise HTTPException(status_code=404, detail="Some knowledge entries were not found")

    order = {entry_id: index for index, entry_id in enumerate(unique_ids)}
    entries.sort(key=lambda entry: order.get(entry.id, 0))

    source_domains = {entry.source_domain for entry in entries if entry.source_domain}
    item_ids = {entry.item_id for entry in entries if entry.item_id}

    merged_entry = KnowledgeEntry(
        user_id=settings.single_user_id,
        item_id=item_ids.pop() if len(item_ids) == 1 else None,
        title=(payload.title or "").strip() or _build_merge_title(entries),
        content=(payload.content or "").strip() or _build_merge_content(entries),
        source_domain=source_domains.pop() if len(source_domains) == 1 else None,
        collection_name=_build_merge_collection_name(entries),
        is_pinned=any(entry.is_pinned for entry in entries),
        is_focus_reference=any(entry.is_focus_reference for entry in entries),
    )
    db.add(merged_entry)
    db.commit()
    db.refresh(merged_entry)
    return _to_entry_out(merged_entry)


@router.get("/{entry_id}", response_model=KnowledgeEntryOut)
def get_knowledge_entry(entry_id: UUID, db: Session = Depends(get_db)) -> KnowledgeEntryOut:
    ensure_demo_user(db)
    entry = _get_entry_or_404(db, entry_id)
    return _to_entry_out(entry)


@router.get("/{entry_id}/markdown", response_model=KnowledgeMarkdownOut)
def get_knowledge_markdown(entry_id: UUID, db: Session = Depends(get_db)) -> KnowledgeMarkdownOut:
    ensure_demo_user(db)
    entry = _get_entry_or_404(db, entry_id)
    return KnowledgeMarkdownOut(
        filename=_build_markdown_filename(entry),
        content=_build_markdown_content(entry),
        entry_count=1,
    )


@router.post("/batch-update", response_model=KnowledgeEntryListResponse)
def batch_update_knowledge_entries(
    payload: KnowledgeBatchUpdateRequest,
    db: Session = Depends(get_db),
) -> KnowledgeEntryListResponse:
    ensure_demo_user(db)
    unique_ids = list(dict.fromkeys(payload.entry_ids))
    entries = list(
        db.scalars(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.user_id == settings.single_user_id)
            .where(KnowledgeEntry.id.in_(unique_ids))
            .options(selectinload(KnowledgeEntry.item))
        )
    )
    if len(entries) != len(unique_ids):
        raise HTTPException(status_code=404, detail="Some knowledge entries were not found")

    order = {entry_id: index for index, entry_id in enumerate(unique_ids)}
    entries.sort(key=lambda entry: order.get(entry.id, 0))
    for entry in entries:
        if "collection_name" in payload.model_fields_set:
            normalized_collection = (payload.collection_name or "").strip()
            entry.collection_name = normalized_collection[:80] if normalized_collection else None
        if "is_pinned" in payload.model_fields_set and payload.is_pinned is not None:
            entry.is_pinned = payload.is_pinned
        if "is_focus_reference" in payload.model_fields_set and payload.is_focus_reference is not None:
            entry.is_focus_reference = payload.is_focus_reference
        db.add(entry)
    db.commit()
    for entry in entries:
        db.refresh(entry)
    return KnowledgeEntryListResponse(items=[_to_entry_out(entry) for entry in entries])


@router.post("/batch-markdown", response_model=KnowledgeMarkdownOut)
def get_batch_knowledge_markdown(
    payload: KnowledgeBatchMarkdownRequest,
    db: Session = Depends(get_db),
) -> KnowledgeMarkdownOut:
    from app.services.work_task_service import build_knowledge_bundle_markdown

    ensure_demo_user(db)
    unique_ids = list(dict.fromkeys(payload.entry_ids))
    entries = list(
        db.scalars(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.user_id == settings.single_user_id)
            .where(KnowledgeEntry.id.in_(unique_ids))
        )
    )
    if len(entries) != len(unique_ids):
        raise HTTPException(status_code=404, detail="Some knowledge entries were not found")

    order = {entry_id: index for index, entry_id in enumerate(unique_ids)}
    entries.sort(key=lambda entry: order.get(entry.id, 0))
    filename, content = build_knowledge_bundle_markdown(
        entries,
        output_language=payload.output_language or "zh-CN",
        title=payload.title,
    )
    return KnowledgeMarkdownOut(filename=filename, content=content, entry_count=len(entries))


@router.get("/{entry_id}/related", response_model=KnowledgeEntryListResponse)
def list_related_knowledge_entries(
    entry_id: UUID,
    limit: int = 4,
    db: Session = Depends(get_db),
) -> KnowledgeEntryListResponse:
    ensure_demo_user(db)
    entry = _get_entry_or_404(db, entry_id)
    candidates = list(
        db.scalars(
            select(KnowledgeEntry)
            .where(KnowledgeEntry.user_id == settings.single_user_id)
            .where(KnowledgeEntry.id != entry_id)
            .options(selectinload(KnowledgeEntry.item))
        )
    )
    ranked = sorted(
        (
            (candidate, _compute_related_score(entry, candidate))
            for candidate in candidates
        ),
        key=lambda pair: pair[1],
        reverse=True,
    )
    related_items = [
        _to_entry_out(candidate)
        for candidate, score in ranked
        if score >= 30
    ][: max(1, min(limit, 8))]
    return KnowledgeEntryListResponse(items=related_items)


@router.patch("/{entry_id}", response_model=KnowledgeEntryOut)
def update_knowledge_entry(
    entry_id: UUID,
    payload: KnowledgeEntryUpdateRequest,
    db: Session = Depends(get_db),
) -> KnowledgeEntryOut:
    ensure_demo_user(db)
    entry = _get_entry_or_404(db, entry_id)
    if "title" in payload.model_fields_set and payload.title is not None:
        entry.title = payload.title.strip()
    if "content" in payload.model_fields_set and payload.content is not None:
        entry.content = payload.content.strip()
    if "collection_name" in payload.model_fields_set:
        normalized_collection = (payload.collection_name or "").strip()
        entry.collection_name = normalized_collection[:80] if normalized_collection else None
    if "is_pinned" in payload.model_fields_set and payload.is_pinned is not None:
        entry.is_pinned = payload.is_pinned
    if "is_focus_reference" in payload.model_fields_set and payload.is_focus_reference is not None:
        entry.is_focus_reference = payload.is_focus_reference
    if "metadata_payload" in payload.model_fields_set:
        entry.metadata_payload = payload.metadata_payload
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return _to_entry_out(entry)
