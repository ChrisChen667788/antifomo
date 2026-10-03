from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.collector_evidence_entities import (
    CollectorDocumentRevision,
    CollectorRawAsset,
    CollectorSourceItem,
    CollectorSourceSpan,
    CollectorTransformReceipt,
)
from app.models.entities import Item
from app.services.content_extractor import normalize_text
from app.services.source_url_privacy import canonicalize_persisted_url


EntityT = TypeVar("EntityT")


@dataclass(frozen=True, slots=True)
class SourceCaptureResult:
    source_item: CollectorSourceItem
    raw_asset: CollectorRawAsset
    revision: CollectorDocumentRevision
    revision_created: bool


def connector_for_item(item: Item) -> str:
    route = normalize_text(item.ingest_route or item.source_type).lower().replace(" ", "_")
    if route == "wechat_favorites":
        return "wechat_favorites_history"
    return route or "manual"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_text(value: str) -> str:
    return _sha256_bytes(value.encode("utf-8"))


def _canonical_json(value: object) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def canonicalize_source_url(value: str | None) -> str | None:
    return canonicalize_persisted_url(value)


def derive_native_item_id(*, native_item_id: str | None, canonical_url: str | None, item_id: UUID) -> str:
    explicit = str(native_item_id or "").strip()
    if explicit:
        return explicit[:512]
    if canonical_url:
        return f"url:{_sha256_text(canonical_url)}"
    return f"item:{item_id}"


def canonicalize_source_identity(
    *,
    connector: str,
    account_scope: str,
    native_item_id: str,
) -> tuple[str, str, str]:
    resolved_connector = normalize_text(connector).lower().replace(" ", "_")[:80] or "manual"
    resolved_scope = normalize_text(account_scope)[:160] or "local"
    resolved_native_id = str(native_item_id or "").strip()[:512]
    return resolved_connector, resolved_scope, resolved_native_id


def _fingerprint(value: str) -> str:
    normalized = str(value or "").strip()
    if len(normalized) == 64 and all(char in "0123456789abcdef" for char in normalized.lower()):
        return normalized.lower()
    return _sha256_text(normalized or "unspecified")


def _insert_or_load(
    db: Session,
    *,
    candidate: EntityT,
    lookup,
) -> tuple[EntityT, bool]:
    """Insert under a savepoint so a concurrent unique-key winner stays recoverable."""

    try:
        with db.begin_nested():
            db.add(candidate)
            db.flush()
        return candidate, True
    except IntegrityError as exc:
        existing = db.scalar(lookup)
        if existing is None:
            raise RuntimeError("Evidence upsert lost a race but no winning row is visible") from exc
        return existing, False


def record_source_capture(
    db: Session,
    *,
    item: Item,
    connector: str,
    raw_content: str,
    clean_content: str | None = None,
    account_scope: str = "local",
    native_item_id: str | None = None,
    native_version: str | None = None,
    canonical_url: str | None = None,
    mime_type: str = "text/plain",
    parser_fingerprint: str = "collector-capture-v1",
    parse_status: str = "captured",
    metadata_payload: dict[str, Any] | None = None,
    advance_current: bool = True,
) -> SourceCaptureResult:
    canonical = canonicalize_source_url(canonical_url or item.source_url)
    item.source_url = canonicalize_persisted_url(item.source_url)
    item.resolved_from_url = canonicalize_persisted_url(item.resolved_from_url)
    explicit_native_id = bool(str(native_item_id or "").strip())
    identity_basis = (
        "connector_native_id"
        if explicit_native_id
        else "canonical_url"
        if canonical
        else "item_id"
    )
    native_id = derive_native_item_id(
        native_item_id=native_item_id,
        canonical_url=canonical,
        item_id=item.id,
    )
    resolved_connector, resolved_scope, native_id = canonicalize_source_identity(
        connector=connector,
        account_scope=account_scope,
        native_item_id=native_id,
    )
    now = datetime.now(timezone.utc)

    def _source_lookup(resolved_native_id: str):
        return (
            select(CollectorSourceItem)
            .where(CollectorSourceItem.user_id == item.user_id)
            .where(CollectorSourceItem.connector == resolved_connector)
            .where(CollectorSourceItem.account_scope == resolved_scope)
            .where(CollectorSourceItem.native_item_id == resolved_native_id)
            .limit(1)
        )

    source_lookup = _source_lookup(native_id)
    source_item = db.scalar(source_lookup)
    if source_item is None:
        source_item, _ = _insert_or_load(
            db,
            candidate=CollectorSourceItem(
                user_id=item.user_id,
                item_id=item.id,
                connector=resolved_connector,
                account_scope=resolved_scope,
                native_item_id=native_id,
                native_version=native_version,
                canonical_url=canonical,
                state="active",
                metadata_payload={"identity_basis": identity_basis},
                first_seen_at=now,
                last_seen_at=now,
            ),
            lookup=source_lookup,
        )
    if source_item.item_id is not None and source_item.item_id != item.id:
        raise ValueError(
            "Source identity is already bound to another Item projection: "
            f"{source_item.item_id}"
        )
    if source_item.item_id != item.id:
        if source_item.item_id is None:
            source_item.item_id = item.id
    source_item.canonical_url = canonical or canonicalize_persisted_url(source_item.canonical_url)
    source_item.last_seen_at = now
    # Source metadata records only the identity basis written at row creation.
    # Per-capture diagnostics belong to immutable revisions below; merging them
    # back here would make concurrent captures overwrite one another.

    raw_bytes = raw_content.encode("utf-8")
    raw_sha256 = _sha256_bytes(raw_bytes)
    raw_lookup = (
        select(CollectorRawAsset)
        .where(CollectorRawAsset.user_id == item.user_id)
        .where(CollectorRawAsset.sha256 == raw_sha256)
        .limit(1)
    )
    raw_asset = db.scalar(raw_lookup)
    if raw_asset is None:
        raw_asset, _ = _insert_or_load(
            db,
            candidate=CollectorRawAsset(
                user_id=item.user_id,
                sha256=raw_sha256,
                mime_type=mime_type,
                byte_size=len(raw_bytes),
                raw_text=raw_content,
                metadata_payload={"capture_connector": resolved_connector},
            ),
            lookup=raw_lookup,
        )

    normalized_content = normalize_text(clean_content if clean_content is not None else raw_content)
    normalized_sha256 = _sha256_text(normalized_content)
    parser_hash = _fingerprint(parser_fingerprint)
    revision_key = _sha256_text(
        _canonical_json(
            {
                "native_version": native_version or "",
                "raw_sha256": raw_sha256,
                "normalized_sha256": normalized_sha256,
                "parser_fingerprint": parser_hash,
            }
        )
    )
    revision_lookup = (
        select(CollectorDocumentRevision)
        .where(CollectorDocumentRevision.source_item_id == source_item.id)
        .where(CollectorDocumentRevision.revision_key == revision_key)
        .limit(1)
    )
    revision = db.scalar(revision_lookup)
    revision_created = False
    if revision is None:
        revision, revision_created = _insert_or_load(
            db,
            candidate=CollectorDocumentRevision(
                source_item_id=source_item.id,
                raw_asset_id=raw_asset.id,
                item_id=item.id,
                revision_key=revision_key,
                native_version=native_version,
                normalized_sha256=normalized_sha256,
                parser_fingerprint=parser_hash,
                parse_status=parse_status,
                diagnostics_payload=dict(metadata_payload or {}),
            ),
            lookup=revision_lookup,
        )

        if revision_created and normalized_content:
            text_sha256 = _sha256_text(normalized_content)
            db.add(
                CollectorSourceSpan(
                    revision_id=revision.id,
                    span_key=f"body:0:{text_sha256[:24]}",
                    kind="body",
                    text=normalized_content,
                    text_sha256=text_sha256,
                    char_start=0,
                    char_end=len(normalized_content),
                    metadata_payload={"origin": "normalized_full_text"},
                )
            )

    # Replaying an older, already-known capture must not move the current
    # pointer backwards from a later processed revision. Callers doing an
    # explicitly out-of-order backfill can also retain the current head without
    # attempting to order connector-native version strings. An empty pointer is
    # always repaired by the only revision available to this capture.
    if source_item.current_revision_key is None or (revision_created and advance_current):
        source_item.current_revision_key = revision.revision_key

    # Head metadata must describe the revision selected by current_revision_key,
    # rather than whichever capture happened to arrive most recently.
    if source_item.current_revision_key == revision.revision_key:
        current_revision = revision
    else:
        current_revision = db.scalar(
            select(CollectorDocumentRevision)
            .where(CollectorDocumentRevision.source_item_id == source_item.id)
            .where(
                CollectorDocumentRevision.revision_key
                == source_item.current_revision_key
            )
            .limit(1)
        )
        if current_revision is None:
            raise RuntimeError("Collector source current revision is missing")
    source_item.native_version = current_revision.native_version
    db.add(source_item)
    db.flush()
    return SourceCaptureResult(
        source_item=source_item,
        raw_asset=raw_asset,
        revision=revision,
        revision_created=revision_created,
    )


def latest_revision_for_item(db: Session, *, item_id: UUID) -> CollectorDocumentRevision | None:
    return db.scalar(
        select(CollectorDocumentRevision)
        .join(
            CollectorSourceItem,
            CollectorSourceItem.id == CollectorDocumentRevision.source_item_id,
        )
        .where(CollectorDocumentRevision.item_id == item_id)
        .where(CollectorDocumentRevision.revision_key == CollectorSourceItem.current_revision_key)
        .order_by(
            desc(CollectorSourceItem.last_seen_at),
            desc(CollectorDocumentRevision.created_at),
            desc(CollectorDocumentRevision.id),
        )
        .limit(1)
    )


def record_transform_receipts(
    db: Session,
    *,
    item: Item,
    revision: CollectorDocumentRevision,
    input_text: str,
    receipts: list[dict[str, Any]],
) -> list[CollectorTransformReceipt]:
    if revision.item_id != item.id:
        raise ValueError("Transform receipt item does not own the document revision")
    revision_user_id = db.scalar(
        select(CollectorSourceItem.user_id)
        .where(CollectorSourceItem.id == revision.source_item_id)
        .limit(1)
    )
    if revision_user_id is None or revision_user_id != item.user_id:
        raise ValueError("Transform receipt user does not own the document revision")

    fallback_input_hash = _sha256_text(normalize_text(input_text))
    stored: list[CollectorTransformReceipt] = []
    for payload in receipts:
        prompt_name = str(payload.get("prompt_name") or "unknown")
        stage = prompt_name.removesuffix(".txt")[:80] or "unknown"
        schema_fingerprint = str(payload.get("prompt_schema_sha256") or "") or None
        input_hash = _fingerprint(str(payload.get("prompt_sha256") or fallback_input_hash))
        output_hash = _fingerprint(str(payload.get("output_sha256") or ""))
        stage_fingerprint = _sha256_text(
            _canonical_json(
                {
                    "stage": stage,
                    "provider": payload.get("provider"),
                    "model": payload.get("model"),
                    "prompt": prompt_name,
                    "prompt_template": payload.get("prompt_template_sha256"),
                    "schema": schema_fingerprint,
                    "pipeline": "item-processing-v2",
                }
            )
        )
        receipt_lookup = (
            select(CollectorTransformReceipt)
            .where(CollectorTransformReceipt.user_id == item.user_id)
            .where(CollectorTransformReceipt.revision_id == revision.id)
            .where(CollectorTransformReceipt.stage == stage)
            .where(CollectorTransformReceipt.input_hash == input_hash)
            .where(CollectorTransformReceipt.stage_fingerprint == stage_fingerprint)
            .where(CollectorTransformReceipt.output_hash == output_hash)
            .limit(1)
        )
        existing = db.scalar(receipt_lookup)
        if existing is not None:
            stored.append(existing)
            continue
        parse_status = str(payload.get("parse_status") or "valid")
        runtime_status = str(payload.get("status") or "unknown")
        status = "degraded" if parse_status == "fallback" else runtime_status
        record, _ = _insert_or_load(
            db,
            candidate=CollectorTransformReceipt(
                user_id=item.user_id,
                revision_id=revision.id,
                item_id=item.id,
                stage=stage,
                input_hash=input_hash,
                stage_fingerprint=stage_fingerprint,
                output_hash=output_hash,
                status=status,
                provider=str(payload.get("provider") or "") or None,
                model=str(payload.get("model") or "") or None,
                prompt_name=prompt_name,
                schema_fingerprint=schema_fingerprint,
                usage_payload=dict(payload.get("usage") or {}),
                diagnostics_payload={
                    "attempts": payload.get("attempts"),
                    "response_id": payload.get("response_id"),
                    "finish_reason": payload.get("finish_reason"),
                    "parse_status": parse_status,
                    "estimated_cost_usd": payload.get("estimated_cost_usd"),
                    "metadata": dict(payload.get("metadata") or {}),
                },
            ),
            lookup=receipt_lookup,
        )
        stored.append(record)
    return stored


def mark_source_tombstone(
    db: Session,
    *,
    user_id: UUID,
    connector: str,
    account_scope: str,
    native_item_id: str,
    reason: str,
) -> CollectorSourceItem | None:
    resolved_connector, resolved_scope, resolved_native_id = canonicalize_source_identity(
        connector=connector,
        account_scope=account_scope,
        native_item_id=native_item_id,
    )
    source_item = db.scalar(
        select(CollectorSourceItem)
        .where(CollectorSourceItem.user_id == user_id)
        .where(CollectorSourceItem.connector == resolved_connector)
        .where(CollectorSourceItem.account_scope == resolved_scope)
        .where(CollectorSourceItem.native_item_id == resolved_native_id)
        .limit(1)
    )
    if source_item is None:
        return None
    source_item.state = "tombstoned"
    source_item.tombstoned_at = datetime.now(timezone.utc)
    source_item.metadata_payload = {
        **dict(source_item.metadata_payload or {}),
        "tombstone_reason": normalize_text(reason),
    }
    db.add(source_item)
    return source_item
