from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import re
import ssl
from urllib import parse, request

from sqlalchemy import select

from app.db.session import SessionLocal
from app.models.entities import Item
from app.services.content_extractor import (
    ContentExtractionError,
    extract_domain,
    extract_from_reader_proxy,
    extract_from_url,
    normalize_text,
)


DDG_HTML_URL = "https://html.duckduckgo.com/html/?q="
WECHAT_ALLOWED_DOMAINS = ("mp.weixin.qq.com", "weixin.qq.com")
GENERIC_RESOLVE_TOKENS = {
    "阅读",
    "分享",
    "收藏",
    "在看",
    "标题",
    "关键词",
    "正文",
    "作者",
    "原创",
    "发布于",
    "发表于",
}
GENERIC_ACCOUNT_TOKENS = {
    "公众号",
    "官方公众号",
    "微信",
    "微信编辑",
    "阅读原文",
    "原创内容",
    "作者",
    "来源",
    "上海",
    "北京",
}


@dataclass(slots=True)
class WechatArticleResolveCandidate:
    source_url: str
    title: str
    source_domain: str | None
    search_query: str
    snippet: str
    score: int
    matched_title: bool
    matched_excerpt: bool


@dataclass(slots=True)
class WechatArticleResolveResult:
    resolved_url: str | None
    confidence: float
    resolver: str
    matched_via: str | None
    queries: list[str]
    candidates: list[WechatArticleResolveCandidate]


@dataclass(slots=True)
class _SearchHit:
    title: str
    url: str
    snippet: str
    search_query: str


class _DuckDuckGoWechatParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._current_title: list[str] = []
        self._current_snippet: list[str] = []
        self._current_url: str | None = None
        self._current_query: str = ""
        self._capture_mode: str | None = None
        self.results: list[_SearchHit] = []

    def begin_query(self, query: str) -> None:
        self._current_query = query

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        attrs_map = {str(k).lower(): str(v) for k, v in attrs if k and v}
        class_name = attrs_map.get("class", "")
        href = attrs_map.get("href", "")
        if tag == "a" and "result__a" in class_name:
            self._flush_current()
            self._current_url = _unwrap_duckduckgo_link(href)
            self._capture_mode = "title"
            return
        if tag == "a" and "result__snippet" in class_name:
            if not self._current_url:
                self._current_url = _unwrap_duckduckgo_link(href)
            self._capture_mode = "snippet"

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if tag == "a" and self._capture_mode in {"title", "snippet"}:
            self._capture_mode = None

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        text = normalize_text(data)
        if not text:
            return
        if self._capture_mode == "title":
            self._current_title.append(text)
        elif self._capture_mode == "snippet":
            self._current_snippet.append(text)

    def close(self) -> None:
        super().close()
        self._flush_current()

    def _flush_current(self) -> None:
        title = normalize_text(" ".join(self._current_title))
        snippet = normalize_text(" ".join(self._current_snippet))
        url = normalize_text(self._current_url or "")
        if title and url:
            self.results.append(
                _SearchHit(
                    title=title,
                    url=url,
                    snippet=snippet,
                    search_query=self._current_query,
                )
            )
        self._current_title = []
        self._current_snippet = []
        self._current_url = None
        self._capture_mode = None


def _unwrap_duckduckgo_link(url: str) -> str:
    raw = unescape(url or "").strip()
    if not raw:
        return ""
    if raw.startswith("//"):
        raw = f"https:{raw}"
    parsed = parse.urlparse(raw)
    if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
        params = parse.parse_qs(parsed.query)
        redirect = params.get("uddg")
        if redirect:
            return parse.unquote(redirect[0])
    return raw


def _compact_text(value: str) -> str:
    return re.sub(r"\s+", "", normalize_text(value))


def _tokenize(value: str) -> list[str]:
    text = normalize_text(value)
    if not text:
        return []
    rough = re.split(r"[\s,，、/|:：;；（）()【】“”\"'‘’\-\u3000]+", text)
    tokens: list[str] = []
    for raw in rough:
        token = raw.strip()
        if len(token) < 2:
            continue
        if token in GENERIC_RESOLVE_TOKENS:
            continue
        tokens.append(token)
    compact = _compact_text(text)
    if 3 <= len(compact) <= 30:
        tokens.append(compact)
    return list(dict.fromkeys(tokens))


def _extract_account_hints(*values: str) -> list[str]:
    hints: list[str] = []
    patterns = (
        r"([A-Za-z0-9\u4e00-\u9fff·]{2,20})官方公众号",
        r"来源\s*[|丨:：]?\s*([A-Za-z0-9\u4e00-\u9fff·]{2,20})",
        r"出品\s*[|丨:：]?\s*([A-Za-z0-9\u4e00-\u9fff·]{2,20})",
        r"发布于\s*([A-Za-z0-9\u4e00-\u9fff·]{2,20})",
    )
    for raw in values:
        text = normalize_text(raw)
        if not text:
            continue
        for pattern in patterns:
            for match in re.findall(pattern, text):
                hint = normalize_text(match).strip()
                if len(hint) < 2 or hint in GENERIC_ACCOUNT_TOKENS:
                    continue
                hints.append(hint)
    return list(dict.fromkeys(hints))


def _extract_dense_phrases(value: str, *, limit: int = 6) -> list[str]:
    text = normalize_text(value)
    if not text:
        return []
    text = re.sub(r"https?://\S+", " ", text)
    phrases: list[str] = []
    for part in re.split(r"[。！？!?；;：:\n\r]+", text):
        piece = normalize_text(part)
        if len(piece) < 8:
            continue
        if any(token in piece for token in ("阅读原文", "公众号", "原创内容", "微信编辑")):
            continue
        if len(piece) > 36:
            piece = piece[:36].strip()
        phrases.append(piece)
    if not phrases:
        compact = _compact_text(text)
        for idx in range(0, min(len(compact), 48), 12):
            chunk = compact[idx : idx + 18]
            if len(chunk) >= 8:
                phrases.append(chunk)
    return list(dict.fromkeys(phrases))[:limit]


def _strip_noisy_title_prefix(value: str) -> str:
    text = normalize_text(value)
    if not text:
        return ""
    text = re.sub(r"\b20\d{2}年\d{1,2}月\d{1,2}日\b", " ", text)
    text = re.sub(r"\b\d{1,2}:\d{2}\b", " ", text)
    text = re.sub(r"\b(上海|北京|深圳|广州|杭州|成都)\b", " ", text)
    text = normalize_text(text)
    if "据" in text and len(text) > 12:
        head, tail = text.split("据", 1)
        if len(head) <= 10 and len(tail) >= 8:
            return normalize_text(tail)
    return text


def _is_allowed_wechat_url(url: str | None) -> bool:
    domain = (extract_domain(url) or "").lower()
    if not domain:
        return False
    return any(domain == suffix or domain.endswith(f".{suffix}") for suffix in WECHAT_ALLOWED_DOMAINS)


def _search_duckduckgo(query: str, *, timeout_seconds: int, limit: int) -> list[_SearchHit]:
    req = request.Request(
        f"{DDG_HTML_URL}{parse.quote_plus(query)}",
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            )
        },
    )
    try:
        with request.urlopen(req, timeout=timeout_seconds) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    except ssl.SSLCertVerificationError:
        insecure_context = ssl._create_unverified_context()
        with request.urlopen(req, timeout=timeout_seconds, context=insecure_context) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
    parser = _DuckDuckGoWechatParser()
    parser.begin_query(query)
    parser.feed(html)
    parser.close()
    deduped: list[_SearchHit] = []
    seen: set[str] = set()
    for hit in parser.results:
        if not _is_allowed_wechat_url(hit.url):
            continue
        if hit.url in seen:
            continue
        seen.add(hit.url)
        deduped.append(hit)
        if len(deduped) >= limit:
            break
    return deduped


def _search_existing_items(title_hint: str, body_preview: str, *, limit: int) -> list[WechatArticleResolveCandidate]:
    account_hints = _extract_account_hints(title_hint, body_preview)
    dense_phrases = _extract_dense_phrases(body_preview, limit=3)
    title_tokens = _tokenize(_strip_noisy_title_prefix(title_hint) or title_hint)[:3]
    candidates: list[WechatArticleResolveCandidate] = []
    with SessionLocal() as db:
        stmt = (
            select(Item)
            .where(Item.source_url.is_not(None))
            .where(Item.source_url.like("%mp.weixin.qq.com%"))
            .order_by(Item.created_at.desc())
            .limit(400)
        )
        rows = db.execute(stmt).scalars().all()
    for item in rows:
        item_title = normalize_text(item.title or "")
        item_body = normalize_text(item.clean_content or item.raw_content or "")[:1600]
        haystack = normalize_text(" ".join([item_title, item_body]))
        if not haystack:
            continue
        fast_hit = False
        for token in [*account_hints[:2], *dense_phrases[:2], *title_tokens]:
            if token and token in haystack:
                fast_hit = True
                break
        if not fast_hit:
            continue
        score, matched_title, matched_excerpt = _match_score(
            title_hint=title_hint,
            body_preview=body_preview,
            candidate_title=item_title,
            candidate_snippet=item_body[:220],
            extracted_title=item_title,
            extracted_body=item_body,
        )
        if score <= 0:
            continue
        candidates.append(
            WechatArticleResolveCandidate(
                source_url=item.source_url or "",
                title=item_title,
                source_domain=extract_domain(item.source_url),
                search_query="history",
                snippet=item_body[:220],
                score=score + 18,
                matched_title=matched_title,
                matched_excerpt=matched_excerpt,
            )
        )
    candidates.sort(key=lambda item: item.score, reverse=True)
    deduped: list[WechatArticleResolveCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate.source_url in seen:
            continue
        seen.add(candidate.source_url)
        deduped.append(candidate)
        if len(deduped) >= limit:
            break
    return deduped


def _build_queries(title_hint: str, body_preview: str, *, limit: int = 10) -> list[str]:
    title = normalize_text(title_hint)
    body = normalize_text(body_preview)
    stripped_title = _strip_noisy_title_prefix(title)
    account_hints = _extract_account_hints(title, body)
    dense_phrases = _extract_dense_phrases(body, limit=6)
    queries: list[str] = []
    compact_title = _compact_text(title)
    excerpt_tokens = _tokenize(body)[:4]
    if title:
        queries.append(f'site:mp.weixin.qq.com "{title}"')
        queries.append(f"site:mp.weixin.qq.com {title}")
    if stripped_title and stripped_title != title:
        queries.append(f'site:mp.weixin.qq.com "{stripped_title}"')
        queries.append(f"site:mp.weixin.qq.com {stripped_title}")
    if compact_title and compact_title != title:
        queries.append(f'site:mp.weixin.qq.com "{compact_title}"')
    if account_hints and stripped_title:
        for account in account_hints[:2]:
            queries.append(f'site:mp.weixin.qq.com {account} "{stripped_title}"')
    for account in account_hints[:2]:
        for phrase in dense_phrases[:2]:
            queries.append(f'site:mp.weixin.qq.com {account} "{phrase}"')
    for phrase in dense_phrases[:3]:
        queries.append(f'site:mp.weixin.qq.com "{phrase}"')
    if title and excerpt_tokens:
        queries.append(f"site:mp.weixin.qq.com {title} {' '.join(excerpt_tokens[:2])}")
    elif excerpt_tokens:
        queries.append(f"site:mp.weixin.qq.com {' '.join(excerpt_tokens[:3])}")
    if title:
        shortened = title[:18].strip()
        if shortened and shortened != title:
            queries.append(f'site:mp.weixin.qq.com "{shortened}"')
    deduped: list[str] = []
    seen: set[str] = set()
    for query in queries:
        normalized = normalize_text(query)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
        if len(deduped) >= limit:
            break
    return deduped


def _match_score(
    *,
    title_hint: str,
    body_preview: str,
    candidate_title: str,
    candidate_snippet: str,
    extracted_title: str = "",
    extracted_body: str = "",
) -> tuple[int, bool, bool]:
    compact_title = _compact_text(title_hint)
    candidate_title_compact = _compact_text(candidate_title)
    combined = normalize_text(" ".join([candidate_title, candidate_snippet, extracted_title, extracted_body]))
    combined_compact = _compact_text(combined)
    title_tokens = _tokenize(title_hint)[:6]
    excerpt_tokens = _tokenize(body_preview)[:6]

    score = 0
    matched_title = False
    matched_excerpt = False

    if compact_title:
        if compact_title in candidate_title_compact or compact_title in combined_compact:
            score += 120
            matched_title = True
        else:
            prefix = compact_title[: min(len(compact_title), 16)]
            if prefix and prefix in combined_compact:
                score += 75
                matched_title = True

    title_overlap = sum(1 for token in title_tokens if token and token in combined)
    if title_overlap:
        score += min(48, title_overlap * 12)
        matched_title = matched_title or title_overlap >= 2

    excerpt_overlap = sum(1 for token in excerpt_tokens if token and token in combined)
    if excerpt_overlap:
        score += min(36, excerpt_overlap * 6)
        matched_excerpt = excerpt_overlap >= 2

    if extracted_title:
        extracted_title_compact = _compact_text(extracted_title)
        if compact_title and extracted_title_compact and compact_title == extracted_title_compact:
            score += 90
            matched_title = True

    if extracted_body:
        dense_overlap = sum(1 for token in excerpt_tokens if token and token in extracted_body)
        if dense_overlap:
            score += min(42, dense_overlap * 7)
            matched_excerpt = True

    return score, matched_title, matched_excerpt


def resolve_wechat_article_url(
    *,
    title_hint: str | None,
    body_preview: str | None,
    timeout_seconds: int = 8,
    search_limit: int = 5,
    verify_limit: int = 3,
) -> WechatArticleResolveResult:
    title = normalize_text(title_hint or "")
    body = normalize_text(body_preview or "")
    if not title and not body:
        return WechatArticleResolveResult(
            resolved_url=None,
            confidence=0.0,
            resolver="none",
            matched_via=None,
            queries=[],
            candidates=[],
        )

    history_candidates = _search_existing_items(title, body, limit=search_limit)
    queries = _build_queries(title, body, limit=10)
    all_hits: list[_SearchHit] = []
    seen_urls: set[str] = set()
    for query in queries:
        try:
            hits = _search_duckduckgo(query, timeout_seconds=timeout_seconds, limit=search_limit)
        except Exception:
            continue
        for hit in hits:
            if hit.url in seen_urls:
                continue
            seen_urls.add(hit.url)
            all_hits.append(hit)

    ranked: list[WechatArticleResolveCandidate] = list(history_candidates)
    for hit in all_hits[: max(verify_limit * 2, search_limit)]:
        extracted_title = ""
        extracted_body = ""
        for extractor in (extract_from_url, extract_from_reader_proxy):
            try:
                extracted = extractor(hit.url, timeout_seconds=min(timeout_seconds, 10))
            except (ContentExtractionError, Exception):
                continue
            extracted_title = normalize_text(extracted.title or "")
            extracted_body = normalize_text(extracted.clean_content or extracted.raw_content or "")[:1200]
            break
        score, matched_title, matched_excerpt = _match_score(
            title_hint=title,
            body_preview=body,
            candidate_title=hit.title,
            candidate_snippet=hit.snippet,
            extracted_title=extracted_title,
            extracted_body=extracted_body,
        )
        if score <= 0:
            continue
        ranked.append(
            WechatArticleResolveCandidate(
                source_url=hit.url,
                title=extracted_title or hit.title,
                source_domain=extract_domain(hit.url),
                search_query=hit.search_query,
                snippet=normalize_text(extracted_body or hit.snippet)[:220],
                score=score,
                matched_title=matched_title,
                matched_excerpt=matched_excerpt,
            )
        )

    ranked.sort(key=lambda item: item.score, reverse=True)
    ranked.sort(key=lambda item: item.score, reverse=True)
    candidates = ranked[:search_limit]
    best = candidates[0] if candidates else None
    matched_via = None
    if best:
        if best.matched_title and best.matched_excerpt:
            matched_via = "title+excerpt"
        elif best.matched_title:
            matched_via = "title"
        elif best.matched_excerpt:
            matched_via = "excerpt"
    confidence = 0.0
    if best:
        confidence = min(1.0, round(best.score / 220, 3))
    return WechatArticleResolveResult(
        resolved_url=best.source_url if best and best.score >= 70 else None,
        confidence=confidence,
        resolver="history" if best and best.search_query == "history" else ("search" if candidates else "none"),
        matched_via=matched_via,
        queries=queries,
        candidates=candidates,
    )
