from __future__ import annotations

from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
import ssl
from urllib import parse, request

from app.services.content_extractor import normalize_text


@dataclass(slots=True)
class SearchHit:
    title: str
    url: str
    snippet: str
    search_query: str
    source_hint: str | None = None
    source_label: str | None = None


class _DuckDuckGoResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchHit] = []
        self._current_title: list[str] = []
        self._current_snippet: list[str] = []
        self._current_url: str | None = None
        self._current_query: str = ""
        self._capture_mode: str | None = None

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
                SearchHit(
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


class _BingResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchHit] = []
        self._current_query: str = ""
        self._inside_result = False
        self._result_depth = 0
        self._capture_title = False
        self._capture_snippet = False
        self._current_title: list[str] = []
        self._current_snippet: list[str] = []
        self._current_url: str | None = None

    def begin_query(self, query: str) -> None:
        self._current_query = query

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        attrs_map = {str(k).lower(): str(v) for k, v in attrs if k and v}
        class_name = attrs_map.get("class", "")
        href = attrs_map.get("href", "")
        if tag == "li" and "b_algo" in class_name:
            self._flush_current()
            self._inside_result = True
            self._result_depth = 1
            return
        if self._inside_result:
            self._result_depth += 1
            if tag == "a" and href.startswith("http") and self._current_url is None:
                self._current_url = normalize_text(href)
                self._capture_title = True
                return
            if tag == "p":
                self._capture_snippet = True

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if self._capture_title and tag == "a":
            self._capture_title = False
        if self._capture_snippet and tag == "p":
            self._capture_snippet = False
        if self._inside_result:
            self._result_depth -= 1
            if self._result_depth <= 0:
                self._inside_result = False
                self._flush_current()

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        text = normalize_text(data)
        if not text:
            return
        if self._capture_title:
            self._current_title.append(text)
        elif self._capture_snippet:
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
                SearchHit(
                    title=title,
                    url=url,
                    snippet=snippet,
                    search_query=self._current_query,
                )
            )
        self._current_title = []
        self._current_snippet = []
        self._current_url = None
        self._capture_title = False
        self._capture_snippet = False


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


def _safe_urlopen(req: request.Request, *, timeout_seconds: int):
    try:
        return request.urlopen(req, timeout=timeout_seconds)
    except Exception as exc:
        message = str(exc).lower()
        if "certificate verify failed" not in message:
            raise
        insecure_context = ssl._create_unverified_context()
        return request.urlopen(req, timeout=timeout_seconds, context=insecure_context)


def _search_duckduckgo(query: str, *, timeout_seconds: int, limit: int) -> list[SearchHit]:
    url = f"https://html.duckduckgo.com/html/?q={parse.quote_plus(query)}"
    req = request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            )
        },
    )
    with _safe_urlopen(req, timeout_seconds=timeout_seconds) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    parser = _DuckDuckGoResultParser()
    parser.begin_query(query)
    parser.feed(html)
    parser.close()
    return parser.results[:limit]


def _search_bing(query: str, *, timeout_seconds: int, limit: int) -> list[SearchHit]:
    url = f"https://www.bing.com/search?q={parse.quote_plus(query)}&setlang=zh-Hans"
    req = request.Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            )
        },
    )
    with _safe_urlopen(req, timeout_seconds=timeout_seconds) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    parser = _BingResultParser()
    parser.begin_query(query)
    parser.feed(html)
    parser.close()
    return parser.results[:limit]


def _dedupe_search_hits(hits: list[SearchHit]) -> list[SearchHit]:
    deduped: list[SearchHit] = []
    seen_urls: set[str] = set()
    for hit in hits:
        normalized_url = normalize_text(hit.url)
        if not normalized_url or normalized_url in seen_urls:
            continue
        seen_urls.add(normalized_url)
        deduped.append(hit)
    return deduped


def _search_public_web(query: str, *, timeout_seconds: int, limit: int) -> list[SearchHit]:
    results: list[SearchHit] = []
    try:
        results.extend(_search_duckduckgo(query, timeout_seconds=timeout_seconds, limit=limit))
    except Exception:
        pass
    if len(results) < max(2, limit // 2):
        try:
            results.extend(_search_bing(query, timeout_seconds=timeout_seconds, limit=limit))
        except Exception:
            pass
    return _dedupe_search_hits(results)[:limit]
