from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import hashlib
from html import unescape
from html.parser import HTMLParser
import re
from typing import Any
from urllib import parse as urllib_parse
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.collector_entities import CollectorImportBatch
from app.services.content_extractor import normalize_text
from app.services.language import normalize_output_language


WECHAT_ARTICLE_QUERY_KEYS = {"__biz", "mid", "idx", "sn", "chksm"}
WECHAT_ARTICLE_TRACKING_KEYS = {
    "ascene",
    "clicktime",
    "devicetype",
    "enterid",
    "exportkey",
    "fontgear",
    "from",
    "key",
    "lang",
    "pass_ticket",
    "scene",
    "sessionid",
    "subscene",
    "uin",
    "version",
}
WECHAT_ARTICLE_BAD_PATH_PREFIXES = (
    "/cgi-bin/",
    "/mp/profile_",
    "/mp/homepage",
    "/mp/msg",
    "/mp/readtemplate",
)
URL_RE = re.compile(r"https?://[^\s<>'\"\u3000]+", flags=re.IGNORECASE)


@dataclass(slots=True)
class WechatFavoriteCandidate:
    title: str | None
    source_url: str | None
    raw_content: str
    dedup_key: str
    extraction_mode: str


class _AnchorCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.anchors: list[tuple[str, str]] = []
        self._stack: list[dict[str, Any]] = []

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        if tag.lower() != "a":
            return
        attrs_map = {
            str(key).lower(): str(value)
            for key, value in attrs
            if key is not None and value is not None
        }
        href = attrs_map.get("href", "")
        if href:
            self._stack.append({"href": href, "text": []})

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        if self._stack and data:
            self._stack[-1]["text"].append(data)

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if tag.lower() != "a" or not self._stack:
            return
        current = self._stack.pop()
        href = normalize_text(unescape(str(current["href"])))
        title = normalize_text(unescape(" ".join(current["text"])))
        if href:
            self.anchors.append((href, title))


def _trim_url_candidate(value: str) -> str:
    text = unescape(value or "").strip()
    text = text.rstrip(".,;:!?，。；：！？)]}）】》\"'")
    return text


def _decode_common_url_escapes(value: str) -> str:
    text = unescape(value or "")
    replacements = {
        "\\/": "/",
        "\\u0026": "&",
        "\\u002F": "/",
        "\\u002f": "/",
        "\\u003A": ":",
        "\\u003a": ":",
        "\\u003D": "=",
        "\\u003d": "=",
        "\\u003F": "?",
        "\\u003f": "?",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _url_text_variants(value: str) -> list[str]:
    variants: list[str] = []
    seen: set[str] = set()

    def add(candidate: str) -> None:
        if candidate and candidate not in seen:
            seen.add(candidate)
            variants.append(candidate)

    add(value or "")
    add(unescape(value or ""))
    for candidate in list(variants):
        add(_decode_common_url_escapes(candidate))

    for _ in range(2):
        for candidate in list(variants):
            decoded = urllib_parse.unquote(candidate)
            add(_decode_common_url_escapes(decoded))
    return variants


def _iter_urls_in_text(value: str):
    seen: set[str] = set()
    for variant in _url_text_variants(value):
        for match in URL_RE.finditer(variant):
            raw_url = match.group(0)
            if raw_url in seen:
                continue
            seen.add(raw_url)
            yield variant, match


def _normalize_wechat_article_url(value: str | None) -> str | None:
    text = _trim_url_candidate(value or "")
    if not text:
        return None
    parsed = urllib_parse.urlparse(text)
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if not netloc.endswith("mp.weixin.qq.com"):
        return None
    if any(path.startswith(prefix) for prefix in WECHAT_ARTICLE_BAD_PATH_PREFIXES):
        return None
    if not (path == "/s" or path.startswith("/s/")):
        return None

    query_pairs = urllib_parse.parse_qsl(parsed.query, keep_blank_values=True)
    stable_pairs: list[tuple[str, str]] = []
    article_key_seen = False
    for key, raw_value in query_pairs:
        if key in WECHAT_ARTICLE_QUERY_KEYS:
            article_key_seen = True
            stable_pairs.append((key, raw_value))
        elif key not in WECHAT_ARTICLE_TRACKING_KEYS:
            stable_pairs.append((key, raw_value))

    if path == "/s" and not article_key_seen:
        return None

    stable_query = urllib_parse.urlencode(stable_pairs, doseq=True)
    normalized = parsed._replace(
        scheme="https",
        netloc=netloc,
        path=path.rstrip("/") if path != "/" and path.endswith("/") else path,
        query=stable_query,
        fragment="",
    )
    return urllib_parse.urlunparse(normalized)


def _wechat_favorite_key(source_url: str | None, content: str) -> str:
    seed = source_url or normalize_text(content)
    return hashlib.sha1(seed.encode("utf-8")).hexdigest()


def _build_wechat_favorite_url(content: str) -> str:
    digest = _wechat_favorite_key(None, content)[:24]
    return f"https://wechat.local/favorites/{digest}"


def _candidate_title(value: str | None, *, fallback: str | None = None) -> str | None:
    text = normalize_text(value or "")
    text = re.sub(r"^(标题|题目|收藏|公众号文章)\s*[:：]\s*", "", text).strip()
    if not text and fallback:
        text = normalize_text(fallback)
    if not text:
        return None
    return text[:120]


def _build_wechat_url_raw_content(source_url: str, title: str | None) -> str:
    title_text = title or "微信收藏公众号文章"
    return "\n".join(
        [
            f"标题：{title_text}",
            "来源：微信收藏",
            f"链接：{source_url}",
            f"正文：{title_text}。该条目来自微信收藏，正文会优先通过公众号文章链接解析。",
        ]
    )


def _html_anchor_candidates(export_text: str) -> list[tuple[str, str]]:
    if "<a" not in export_text.lower():
        return []
    parser = _AnchorCollector()
    try:
        parser.feed(export_text)
        parser.close()
    except Exception:
        return []
    return parser.anchors


def _line_title_hints(export_text: str) -> dict[str, str]:
    hints: dict[str, str] = {}
    previous_non_empty = ""
    for raw_line in export_text.splitlines():
        line = normalize_text(_decode_common_url_escapes(raw_line))
        if not line:
            previous_non_empty = ""
            continue
        found_url = False
        for variant, match in _iter_urls_in_text(line):
            url = _normalize_wechat_article_url(match.group(0))
            if not url:
                continue
            found_url = True
            before = normalize_text(variant[: match.start()])
            after = normalize_text(variant[match.end() :])
            title = _candidate_title(before) or _candidate_title(previous_non_empty)
            if not title and after and len(after) <= 120:
                title = _candidate_title(after)
            if title:
                hints[url] = title
        if len(line) <= 160 and not found_url:
            previous_non_empty = line
    return hints


def _extract_wechat_urls(export_text: str, urls: list[str] | None = None) -> list[tuple[str, str | None]]:
    discovered: list[tuple[str, str | None]] = []
    for raw in urls or []:
        for _variant, match in _iter_urls_in_text(raw):
            url = _normalize_wechat_article_url(match.group(0))
            if url:
                discovered.append((url, None))

    for href, anchor_title in _html_anchor_candidates(export_text):
        for _variant, match in _iter_urls_in_text(href):
            url = _normalize_wechat_article_url(match.group(0))
            if url:
                discovered.append((url, _candidate_title(anchor_title)))

    line_hints = _line_title_hints(export_text)
    for _variant, match in _iter_urls_in_text(export_text):
        url = _normalize_wechat_article_url(match.group(0))
        if url:
            discovered.append((url, line_hints.get(url)))

    deduped: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    titles: dict[str, str] = {}
    for url, title in discovered:
        if title and url not in titles:
            titles[url] = title
        if url in seen:
            continue
        seen.add(url)
        deduped.append((url, titles.get(url) or title))
    return deduped


def _plain_text_from_export(export_text: str) -> str:
    text = _decode_common_url_escapes(export_text or "")
    text = urllib_parse.unquote(text)
    text = re.sub(r"(?is)<script[^>]*>.*?</script>", " ", text)
    text = re.sub(r"(?is)<style[^>]*>.*?</style>", " ", text)
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(?:p|div|li|section|article|h[1-6])>", "\n\n", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = URL_RE.sub(" ", text)
    lines = [normalize_text(line) for line in text.splitlines()]
    return "\n".join(lines)


def _looks_like_link_export_metadata(chunk: str) -> bool:
    lowered = chunk.lower()
    metadata_tokens = (
        "[internetshortcut]",
        '"url":',
        "'url':",
        "url=",
        "<key>url</key>",
        ".webloc",
    )
    return len(chunk) < 500 and any(token in lowered for token in metadata_tokens)


def _extract_wechat_text_blocks(
    export_text: str,
    *,
    max_blocks: int = 30,
    excluded_titles: set[str] | None = None,
) -> list[WechatFavoriteCandidate]:
    plain = _plain_text_from_export(export_text)
    chunks = [
        normalize_text(chunk)
        for chunk in re.split(r"(?:\n\s*){2,}", plain)
        if normalize_text(chunk)
    ]
    candidates: list[WechatFavoriteCandidate] = []
    seen: set[str] = set()
    title_exclusions = {normalize_text(title) for title in (excluded_titles or set()) if normalize_text(title)}
    for chunk in chunks:
        if len(chunk) < 80:
            continue
        if _looks_like_link_export_metadata(chunk):
            continue
        if not re.search(r"[\u4e00-\u9fff]", chunk):
            continue
        title = _candidate_title(chunk.split("。", 1)[0][:80])
        if title:
            normalized_title = normalize_text(title)
            if any(
                normalized_title == excluded_title
                or (
                    chunk.startswith(excluded_title)
                    and len(chunk) <= len(excluded_title) + 80
                )
                for excluded_title in title_exclusions
            ):
                continue
        dedup_key = _wechat_favorite_key(None, chunk)
        if dedup_key in seen:
            continue
        seen.add(dedup_key)
        source_url = _build_wechat_favorite_url(chunk)
        raw_content = "\n".join(
            [
                f"标题：{title or '微信收藏正文'}",
                "来源：微信收藏",
                f"正文：{chunk}",
            ]
        )
        candidates.append(
            WechatFavoriteCandidate(
                title=title,
                source_url=source_url,
                raw_content=raw_content,
                dedup_key=dedup_key,
                extraction_mode="wechat_favorites_text",
            )
        )
        if len(candidates) >= max_blocks:
            break
    return candidates


def parse_wechat_favorites_export(
    export_text: str | None = None,
    *,
    urls: list[str] | None = None,
    include_text_blocks: bool = True,
    limit: int = 200,
) -> list[WechatFavoriteCandidate]:
    safe_limit = max(1, min(limit, 500))
    text = export_text or ""
    candidates: list[WechatFavoriteCandidate] = []
    seen_keys: set[str] = set()

    url_titles: set[str] = set()
    for source_url, title in _extract_wechat_urls(text, urls):
        dedup_key = _wechat_favorite_key(source_url, "")
        if dedup_key in seen_keys:
            continue
        seen_keys.add(dedup_key)
        if title:
            url_titles.add(title)
        candidates.append(
            WechatFavoriteCandidate(
                title=title,
                source_url=source_url,
                raw_content=_build_wechat_url_raw_content(source_url, title),
                dedup_key=dedup_key,
                extraction_mode="wechat_favorites_url",
            )
        )
        if len(candidates) >= safe_limit:
            return candidates

    if include_text_blocks and text and len(candidates) < safe_limit:
        remaining_limit = safe_limit - len(candidates)
        for candidate in _extract_wechat_text_blocks(
            text,
            max_blocks=min(30, remaining_limit),
            excluded_titles=url_titles,
        ):
            if candidate.dedup_key in seen_keys:
                continue
            seen_keys.add(candidate.dedup_key)
            candidates.append(candidate)
            if len(candidates) >= safe_limit:
                break

    return candidates


def import_wechat_favorites(
    db: Session,
    *,
    user_id: UUID,
    persist_item: Callable[..., dict[str, Any]],
    export_text: str | None = None,
    urls: list[str] | None = None,
    output_language: str = "zh-CN",
    limit: int = 200,
    include_text_blocks: bool = True,
    process_immediately: bool = False,
) -> dict[str, Any]:
    candidates = parse_wechat_favorites_export(
        export_text,
        urls=urls,
        include_text_blocks=include_text_blocks,
        limit=limit,
    )
    results: list[dict[str, Any]] = []
    created_item_ids: list[str] = []
    created = 0
    deduplicated = 0
    invalid = 0
    item_ids: list[str] = []

    for candidate in candidates:
        try:
            source_url = candidate.source_url
            source_type = "text" if candidate.extraction_mode == "wechat_favorites_text" else "url"
            result = persist_item(
                db,
                user_id=user_id,
                source_type=source_type,
                source_url=source_url,
                title=candidate.title,
                raw_content=candidate.raw_content,
                output_language=output_language,
                ingest_route="wechat_favorites",
                content_note="微信收藏导入：公众号内容",
                resolver="wechat_favorites_import",
                body_source=candidate.extraction_mode,
                process_immediately=process_immediately,
            )
            item = result["item"]
            status = "deduplicated" if result.get("deduplicated") else "created"
            if status == "created":
                created += 1
                created_item_ids.append(str(item.id))
            else:
                deduplicated += 1
            item_ids.append(str(item.id))
            results.append(
                {
                    "source_url": item.source_url,
                    "title": item.title or candidate.title,
                    "item_id": str(item.id),
                    "status": status,
                    "detail": None,
                    "body_source": candidate.extraction_mode,
                }
            )
        except Exception as exc:
            invalid += 1
            results.append(
                {
                    "source_url": candidate.source_url,
                    "title": candidate.title,
                    "item_id": None,
                    "status": "invalid",
                    "detail": str(exc),
                    "body_source": candidate.extraction_mode,
                }
            )

    batch = CollectorImportBatch(
        user_id=user_id,
        import_type="wechat_favorites",
        source_label="微信收藏",
        status="queued" if created and not process_immediately else "imported",
        output_language=normalize_output_language(output_language),
        processing_deferred=not process_immediately,
        total_candidates=len(candidates),
        created_count=created,
        deduplicated_count=deduplicated,
        invalid_count=invalid,
        skipped_count=0,
        item_ids=item_ids,
        created_item_ids=created_item_ids,
        result_payload=results[:100],
        source_payload={
            "url_candidates": sum(1 for candidate in candidates if candidate.extraction_mode == "wechat_favorites_url"),
            "text_candidates": sum(1 for candidate in candidates if candidate.extraction_mode == "wechat_favorites_text"),
            "include_text_blocks": include_text_blocks,
            "limit": max(1, min(limit, 500)),
        },
    )
    db.add(batch)
    db.flush()

    return {
        "batch_id": str(batch.id),
        "batch": batch,
        "total_candidates": len(candidates),
        "created": created,
        "deduplicated": deduplicated,
        "invalid": invalid,
        "skipped": 0,
        "created_item_ids": created_item_ids,
        "results": results,
    }
