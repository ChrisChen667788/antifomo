from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from typing import Any
from urllib import error as urllib_error
from urllib import parse as urllib_parse
from urllib import request as urllib_request
from uuid import UUID
import xml.etree.ElementTree as ET

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.models.collector_entities import CollectorFeedEntry, CollectorFeedSource, UploadedDocument
from app.models.entities import Item
from app.services.collector_diagnostics import create_ingest_attempt, update_item_ingest_state
from app.services.content_extractor import extract_domain, normalize_text
from app.services.item_processing_runtime import process_item_in_session
from app.services.language import normalize_output_language


PROJECT_ROOT = Path(__file__).resolve().parents[3]
UPLOAD_ROOT = PROJECT_ROOT / ".storage" / "uploads"


@dataclass(slots=True)
class FeedEntryPayload:
    title: str
    source_url: str | None
    summary: str
    published_at: datetime | None
    dedup_key: str
    raw_payload: dict[str, Any]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _normalize_url(value: str | None) -> str | None:
    text = normalize_text(value or "")
    if not text:
        return None
    parsed = urllib_parse.urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    normalized = parsed._replace(
        scheme=parsed.scheme.lower(),
        netloc=parsed.netloc.lower(),
        path=path,
        fragment="",
    )
    return urllib_parse.urlunparse(normalized)


def _parse_datetime(value: str | None) -> datetime | None:
    text = normalize_text(value or "")
    if not text:
        return None
    normalized = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        parsed = None
    if parsed is not None:
        if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    for fmt in (
        "%a, %d %b %Y %H:%M:%S %z",
        "%d %b %Y %H:%M:%S %z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d",
    ):
        try:
            parsed = datetime.strptime(text, fmt)
            if parsed.tzinfo is None or parsed.tzinfo.utcoffset(parsed) is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc)
        except ValueError:
            continue
    return None


def _strip_html(value: str | None) -> str:
    text = normalize_text(value or "")
    if not text:
        return ""
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</p>", "\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("&nbsp;", " ").replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    return normalize_text(text)


def _fetch_url_bytes(url: str, *, timeout_seconds: int = 12) -> bytes:
    req = urllib_request.Request(
        url,
        headers={
            "User-Agent": "anti-fomo-demo/1.0",
            "Accept": "application/rss+xml, application/atom+xml, text/xml, application/xml, text/html;q=0.8, */*;q=0.5",
        },
    )
    with urllib_request.urlopen(req, timeout=timeout_seconds) as response:
        return response.read()


def _load_existing_item_by_url(db: Session, *, user_id: UUID, source_url: str | None) -> Item | None:
    normalized = _normalize_url(source_url)
    if not normalized:
        return None
    return db.scalar(
        select(Item)
        .where(Item.user_id == user_id)
        .where(Item.source_url == normalized)
        .order_by(desc(Item.created_at))
        .limit(1)
    )


def _make_title_slug(value: str, *, fallback: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9]+", "-", normalize_text(value).lower()).strip("-")
    if normalized:
        return normalized[:48]
    return fallback


def _storage_file_path(*, file_name: str, suffix: str | None = None) -> Path:
    UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = _utc_now().strftime("%Y%m%d%H%M%S")
    stem = Path(file_name).stem or "upload"
    ext = suffix or Path(file_name).suffix or ".bin"
    digest = hashlib.sha1(f"{file_name}:{timestamp}".encode("utf-8")).hexdigest()[:10]
    return UPLOAD_ROOT / f"{_make_title_slug(stem, fallback='upload')}-{timestamp}-{digest}{ext}"


def _decode_pdf_literal(value: str) -> str:
    def replace_match(match: re.Match[str]) -> str:
        token = match.group(1)
        if token.isdigit():
            try:
                return chr(int(token, 8))
            except ValueError:
                return ""
        mapping = {"n": "\n", "r": "\r", "t": "\t", "b": "\b", "f": "\f", "\\": "\\", "(": "(", ")": ")"}
        return mapping.get(token, token)

    return re.sub(r"\\([0-7]{1,3}|.)", replace_match, value)


def _extract_pdf_text(data: bytes) -> str:
    text = data.decode("latin-1", errors="ignore")
    parts: list[str] = []
    for match in re.finditer(r"\((.*?)\)\s*Tj", text, re.S):
        parts.append(_decode_pdf_literal(match.group(1)))
    for match in re.finditer(r"\[(.*?)\]\s*TJ", text, re.S):
        inner = " ".join(_decode_pdf_literal(value) for value in re.findall(r"\((.*?)\)", match.group(1), re.S))
        if inner:
            parts.append(inner)
    combined = normalize_text(" ".join(parts))
    if len(combined) >= 120:
        return combined
    return ""


def _extract_uploaded_text(*, file_name: str, mime_type: str, file_bytes: bytes, extracted_text: str | None = None) -> tuple[str, str]:
    preferred = normalize_text(extracted_text or "")
    if len(preferred) >= 40:
        return preferred, "client_extract"

    lowered_name = file_name.lower()
    lowered_type = mime_type.lower()

    if lowered_type.startswith("text/") or lowered_name.endswith((".txt", ".md", ".markdown", ".csv", ".json")):
        for encoding in ("utf-8", "utf-16", "gb18030", "latin-1"):
            try:
                text = file_bytes.decode(encoding)
                normalized = normalize_text(text)
                if normalized:
                    return normalized, "direct_decode"
            except UnicodeDecodeError:
                continue

    if lowered_type in {"text/html", "application/xhtml+xml"} or lowered_name.endswith((".html", ".htm")):
        normalized = _strip_html(file_bytes.decode("utf-8", errors="ignore"))
        if normalized:
            return normalized, "html_extract"

    if lowered_type == "application/pdf" or lowered_name.endswith(".pdf"):
        extracted = _extract_pdf_text(file_bytes)
        if extracted:
            return extracted, "pdf_text"
        return "", "pdf_extract_failed"

    return normalize_text(file_bytes.decode("utf-8", errors="ignore")), "fallback_decode"


def _extract_youtube_id(url: str) -> str | None:
    normalized = _normalize_url(url)
    if not normalized:
        return None
    parsed = urllib_parse.urlparse(normalized)
    if parsed.netloc in {"youtu.be", "www.youtu.be"}:
        return parsed.path.strip("/") or None
    if "youtube.com" in parsed.netloc:
        if parsed.path == "/watch":
            return urllib_parse.parse_qs(parsed.query).get("v", [None])[0]
        if parsed.path.startswith("/shorts/"):
            return parsed.path.split("/shorts/", 1)[1].split("/", 1)[0] or None
        if parsed.path.startswith("/embed/"):
            return parsed.path.split("/embed/", 1)[1].split("/", 1)[0] or None
    return None


def _fetch_youtube_title(video_url: str) -> str | None:
    try:
        encoded_url = urllib_parse.quote(video_url, safe="")
        payload = _fetch_url_bytes(f"https://www.youtube.com/oembed?url={encoded_url}&format=json", timeout_seconds=8)
        data = json.loads(payload.decode("utf-8"))
    except (urllib_error.URLError, json.JSONDecodeError, UnicodeDecodeError):
        return None
    title = normalize_text(str(data.get("title") or ""))
    return title or None


def _feed_entry_key(feed_id: UUID, entry_url: str | None, title: str) -> str:
    seed = _normalize_url(entry_url) or normalize_text(title)
    return hashlib.sha1(f"{feed_id}:{seed}".encode("utf-8")).hexdigest()


def _xml_text(node: ET.Element | None, path: str) -> str:
    if node is None:
        return ""
    child = node.find(path)
    if child is None:
        return ""
    return normalize_text("".join(child.itertext()))


def _parse_rss_payload(source_url: str, payload: bytes, *, limit: int) -> tuple[str, list[FeedEntryPayload]]:
    root = ET.fromstring(payload)
    channel = root.find("channel")
    feed_title = _xml_text(channel, "title") or _xml_text(root, "{http://www.w3.org/2005/Atom}title") or extract_domain(source_url) or "RSS"
    entries: list[FeedEntryPayload] = []

    if channel is not None:
        for node in channel.findall("item")[:limit]:
            title = _xml_text(node, "title") or "未命名 RSS 条目"
            link = _xml_text(node, "link") or normalize_text(node.findtext("guid") or "")
            link = _normalize_url(link) or None
            summary = _xml_text(node, "description") or _xml_text(
                node,
                "{http://purl.org/rss/1.0/modules/content/}encoded",
            )
            published_at = _parse_datetime(_xml_text(node, "pubDate"))
            entries.append(
                FeedEntryPayload(
                    title=title,
                    source_url=link,
                    summary=summary,
                    published_at=published_at,
                    dedup_key=_feed_entry_key(UUID(int=0), link, title),
                    raw_payload={
                        "title": title,
                        "url": link,
                        "summary": summary,
                        "published_at": published_at.isoformat() if published_at else None,
                    },
                )
            )
    else:
        namespace = {"atom": "http://www.w3.org/2005/Atom"}
        for node in root.findall("atom:entry", namespace)[:limit]:
            title = _xml_text(node, "atom:title") or "未命名 Atom 条目"
            link_node = node.find("atom:link[@rel='alternate']", namespace) or node.find("atom:link", namespace)
            link = _normalize_url(link_node.get("href") if link_node is not None else None)
            summary = _xml_text(node, "atom:summary") or _xml_text(node, "atom:content")
            published_at = _parse_datetime(_xml_text(node, "atom:updated") or _xml_text(node, "atom:published"))
            entries.append(
                FeedEntryPayload(
                    title=title,
                    source_url=link,
                    summary=summary,
                    published_at=published_at,
                    dedup_key=_feed_entry_key(UUID(int=0), link, title),
                    raw_payload={
                        "title": title,
                        "url": link,
                        "summary": summary,
                        "published_at": published_at.isoformat() if published_at else None,
                    },
                )
            )

    return feed_title, entries


def serialize_feed_source(feed: CollectorFeedSource) -> dict[str, Any]:
    return {
        "id": str(feed.id),
        "feed_type": feed.feed_type,
        "source_url": feed.source_url,
        "title": feed.title,
        "note": feed.note,
        "enabled": feed.enabled,
        "status": feed.status,
        "last_synced_at": feed.last_synced_at,
        "last_error": feed.last_error,
        "created_at": feed.created_at,
        "updated_at": feed.updated_at,
    }


def list_feed_sources(db: Session, *, user_id: UUID, feed_type: str | None = None) -> list[dict[str, Any]]:
    query = select(CollectorFeedSource).where(CollectorFeedSource.user_id == user_id).order_by(desc(CollectorFeedSource.updated_at))
    if feed_type:
        query = query.where(CollectorFeedSource.feed_type == feed_type)
    return [serialize_feed_source(feed) for feed in db.scalars(query)]


def save_feed_source(
    db: Session,
    *,
    user_id: UUID,
    feed_type: str,
    source_url: str,
    title: str | None = None,
    note: str | None = None,
) -> CollectorFeedSource:
    normalized_url = _normalize_url(source_url)
    if not normalized_url:
        raise ValueError("invalid feed source url")
    existing = db.scalar(
        select(CollectorFeedSource)
        .where(CollectorFeedSource.user_id == user_id)
        .where(CollectorFeedSource.feed_type == feed_type)
        .where(CollectorFeedSource.source_url == normalized_url)
        .limit(1)
    )
    if existing is not None:
        if title is not None:
            existing.title = normalize_text(title)
        if note is not None:
            existing.note = normalize_text(note)
        db.add(existing)
        db.commit()
        db.refresh(existing)
        return existing

    feed = CollectorFeedSource(
        user_id=user_id,
        feed_type=feed_type,
        source_url=normalized_url,
        title=normalize_text(title or ""),
        note=normalize_text(note or ""),
        enabled=True,
        status="idle",
    )
    db.add(feed)
    db.commit()
    db.refresh(feed)
    return feed


def _persist_item(
    db: Session,
    *,
    user_id: UUID,
    source_type: str,
    source_url: str | None,
    title: str | None,
    raw_content: str,
    output_language: str,
    ingest_route: str,
    content_note: str,
    resolver: str,
    body_source: str,
) -> dict[str, Any]:
    normalized_url = _normalize_url(source_url)
    if normalized_url:
        existing = _load_existing_item_by_url(db, user_id=user_id, source_url=normalized_url)
        if existing is not None:
            update_item_ingest_state(
                existing,
                ingest_route=existing.ingest_route or ingest_route,
                resolved_from_url=normalized_url,
                fallback_used=existing.fallback_used,
            )
            attempt = create_ingest_attempt(
                db,
                item=existing,
                source_url=normalized_url,
                route_type=existing.ingest_route or ingest_route,
                resolver="existing_item",
                attempt_status="deduplicated",
                body_source=body_source,
            )
            db.add(existing)
            db.commit()
            db.refresh(existing)
            return {"item": existing, "attempt": attempt, "deduplicated": True}

    item = Item(
        user_id=user_id,
        source_type=source_type,
        source_url=normalized_url,
        source_domain=extract_domain(normalized_url) or extract_domain(source_url),
        title=normalize_text(title or "") or None,
        raw_content=normalize_text(raw_content),
        output_language=normalize_output_language(output_language),
        ingest_route=ingest_route,
        content_acquisition_status="body_acquired",
        content_acquisition_note=content_note,
        resolved_from_url=normalized_url,
        fallback_used=False,
        status="pending",
    )
    db.add(item)
    db.flush()
    process_item_in_session(db, item, output_language=item.output_language, auto_archive=True)
    update_item_ingest_state(
        item,
        ingest_route=ingest_route,
        resolved_from_url=normalized_url,
        fallback_used=False,
    )
    attempt = create_ingest_attempt(
        db,
        item=item,
        source_url=normalized_url,
        route_type=ingest_route,
        resolver=resolver,
        attempt_status="ready" if item.status == "ready" else "failed",
        body_source=body_source,
        error_detail=item.processing_error,
    )
    db.commit()
    db.refresh(item)
    return {"item": item, "attempt": attempt, "deduplicated": False}


def sync_rss_feeds(
    db: Session,
    *,
    user_id: UUID,
    feed_id: UUID | None = None,
    limit: int = 8,
    output_language: str = "zh-CN",
) -> list[dict[str, Any]]:
    query = (
        select(CollectorFeedSource)
        .where(CollectorFeedSource.user_id == user_id)
        .where(CollectorFeedSource.enabled.is_(True))
        .where(CollectorFeedSource.feed_type == "rss")
        .order_by(desc(CollectorFeedSource.updated_at))
    )
    if feed_id is not None:
        query = query.where(CollectorFeedSource.id == feed_id)
    feeds = list(db.scalars(query))
    results: list[dict[str, Any]] = []

    for feed in feeds:
        result = {
            "feed_id": str(feed.id),
            "source_url": feed.source_url,
            "feed_title": feed.title or feed.source_url,
            "new_items": 0,
            "deduplicated_items": 0,
            "skipped_items": 0,
            "item_ids": [],
            "latest_titles": [],
            "status": "ok",
            "error": None,
            "synced_at": None,
        }
        try:
            payload = _fetch_url_bytes(feed.source_url)
            parsed_title, entries = _parse_rss_payload(feed.source_url, payload, limit=max(1, min(limit, 20)))
            if parsed_title and not feed.title:
                feed.title = parsed_title
            for entry in entries:
                dedup_key = _feed_entry_key(feed.id, entry.source_url, entry.title)
                existing_entry = db.scalar(
                    select(CollectorFeedEntry)
                    .where(CollectorFeedEntry.feed_id == feed.id)
                    .where(CollectorFeedEntry.dedup_key == dedup_key)
                    .limit(1)
                )
                if existing_entry is not None:
                    result["skipped_items"] += 1
                    continue

                db.add(
                    CollectorFeedEntry(
                        feed_id=feed.id,
                        source_url=entry.source_url,
                        title=entry.title,
                        published_at=entry.published_at,
                        dedup_key=dedup_key,
                        raw_payload=entry.raw_payload,
                    )
                )
                raw_parts = [f"标题：{entry.title}"]
                if entry.summary:
                    raw_parts.append(f"正文：{entry.summary}")
                elif entry.source_url:
                    raw_parts.append(f"链接：{entry.source_url}")
                ingest = _persist_item(
                    db,
                    user_id=user_id,
                    source_type="plugin" if entry.source_url else "text",
                    source_url=entry.source_url,
                    title=entry.title,
                    raw_content="\n".join(raw_parts),
                    output_language=output_language,
                    ingest_route="rss_feed",
                    content_note=f"RSS 已同步：{parsed_title}",
                    resolver="rss_pull",
                    body_source="rss_summary",
                )
                if ingest["deduplicated"]:
                    result["deduplicated_items"] += 1
                else:
                    result["new_items"] += 1
                result["item_ids"].append(str(ingest["item"].id))
                result["latest_titles"].append(entry.title)
            feed.status = "ready"
            feed.last_error = None
            feed.last_synced_at = _utc_now()
            result["feed_title"] = feed.title or parsed_title or feed.source_url
            result["synced_at"] = feed.last_synced_at
        except Exception as exc:
            feed.status = "failed"
            feed.last_error = str(exc)
            result["status"] = "failed"
            result["error"] = str(exc)
        db.add(feed)
        db.commit()
        results.append(result)
    return results


def ingest_newsletter(
    db: Session,
    *,
    user_id: UUID,
    title: str,
    raw_content: str,
    sender: str | None = None,
    source_url: str | None = None,
    output_language: str = "zh-CN",
) -> dict[str, Any]:
    header = [f"标题：{normalize_text(title)}"]
    if sender:
        header.append(f"来源：{normalize_text(sender)}")
    header.append(f"正文：{normalize_text(raw_content)}")
    result = _persist_item(
        db,
        user_id=user_id,
        source_type="plugin" if source_url else "text",
        source_url=source_url,
        title=title,
        raw_content="\n".join(header),
        output_language=output_language,
        ingest_route="newsletter",
        content_note="Newsletter 已导入正文",
        resolver="newsletter_ingest",
        body_source="newsletter_body",
    )
    result["sender"] = normalize_text(sender or "") or None
    return result


def ingest_uploaded_document(
    db: Session,
    *,
    user_id: UUID,
    file_name: str,
    mime_type: str,
    file_base64: str,
    extracted_text: str | None = None,
    title: str | None = None,
    source_url: str | None = None,
    output_language: str = "zh-CN",
) -> dict[str, Any]:
    file_bytes = base64.b64decode(file_base64)
    storage_path = _storage_file_path(file_name=file_name).resolve()
    storage_path.write_bytes(file_bytes)
    parsed_text, parse_method = _extract_uploaded_text(
        file_name=file_name,
        mime_type=mime_type,
        file_bytes=file_bytes,
        extracted_text=extracted_text,
    )
    parse_status = "parsed" if len(parsed_text) >= 80 else "partial"
    document = UploadedDocument(
        user_id=user_id,
        file_name=file_name,
        file_type=mime_type,
        file_size=len(file_bytes),
        storage_path=str(storage_path),
        parse_status=parse_status,
        parse_payload={
            "parse_method": parse_method,
            "text_length": len(parsed_text),
            "title_hint": normalize_text(title or "") or Path(file_name).stem,
            "preview": parsed_text[:300],
        },
    )
    db.add(document)
    db.flush()

    raw_lines = [f"文件：{file_name}"]
    if title:
        raw_lines.append(f"标题：{normalize_text(title)}")
    if parsed_text:
        raw_lines.append(f"正文：{parsed_text}")
    else:
        raw_lines.append("正文：当前文件提取结果较弱，建议补充文本摘录后重新导入。")

    result = _persist_item(
        db,
        user_id=user_id,
        source_type="plugin" if source_url else "text",
        source_url=source_url,
        title=title or Path(file_name).stem,
        raw_content="\n".join(raw_lines),
        output_language=output_language,
        ingest_route="file_upload",
        content_note=f"文件已导入，解析方式={parse_method}",
        resolver="file_upload",
        body_source=parse_method,
    )
    db.refresh(document)
    result["document"] = document
    result["parse_status"] = parse_status
    result["parse_method"] = parse_method
    result["text_length"] = len(parsed_text)
    return result


def ingest_youtube_transcript(
    db: Session,
    *,
    user_id: UUID,
    video_url: str,
    transcript_text: str | None = None,
    title: str | None = None,
    output_language: str = "zh-CN",
) -> dict[str, Any]:
    normalized_url = _normalize_url(video_url)
    if not normalized_url:
        raise ValueError("invalid youtube url")
    resolved_title = normalize_text(title or "") or _fetch_youtube_title(normalized_url) or "YouTube 视频转录"
    video_id = _extract_youtube_id(normalized_url)
    transcript = normalize_text(transcript_text or "")
    note = "YouTube 转录已导入" if transcript else "YouTube 仅导入视频链接，建议补充 transcript"
    raw_lines = [f"标题：{resolved_title}"]
    if video_id:
        raw_lines.append(f"视频 ID：{video_id}")
    raw_lines.append(f"链接：{normalized_url}")
    if transcript:
        raw_lines.append(f"正文：{transcript}")
    else:
        raw_lines.append("正文：当前仅保存视频链接，建议补充 transcript 文本后再次导入。")
    result = _persist_item(
        db,
        user_id=user_id,
        source_type="plugin",
        source_url=normalized_url,
        title=resolved_title,
        raw_content="\n".join(raw_lines),
        output_language=output_language,
        ingest_route="youtube_transcript",
        content_note=note,
        resolver="youtube_ingest",
        body_source="youtube_transcript" if transcript else "youtube_link_only",
    )
    result["video_id"] = video_id
    result["transcript_attached"] = bool(transcript)
    return result
