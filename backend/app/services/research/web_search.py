from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from html import unescape
from html.parser import HTMLParser
import json
import logging
import re
import ssl
from urllib import parse, request
from xml.etree import ElementTree

from app.services.content_extractor import normalize_text


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class SearchHit:
    title: str
    url: str
    snippet: str
    search_query: str
    source_hint: str | None = None
    source_label: str | None = None
    source_origin: str | None = None


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


class _SoResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchHit] = []
        self._current_query = ""
        self._inside_result = False
        self._result_depth = 0
        self._inside_title = False
        self._capture_title = False
        self._capture_snippet = False
        self._current_title: list[str] = []
        self._current_snippet: list[str] = []
        self._current_url: str | None = None

    def begin_query(self, query: str) -> None:
        self._current_query = query

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        attrs_map = {str(k).lower(): unescape(str(v)) for k, v in attrs if k and v}
        class_name = attrs_map.get("class", "")
        if tag == "li" and "res-list" in class_name.split():
            self._flush_current()
            self._inside_result = True
            self._result_depth = 1
            return
        if not self._inside_result:
            return
        self._result_depth += 1
        if tag == "h3" and "res-title" in class_name:
            self._inside_title = True
            return
        if tag == "a" and self._inside_title and self._current_url is None:
            direct_url = attrs_map.get("data-mdurl", "")
            href = attrs_map.get("href", "")
            candidate = direct_url if direct_url.startswith("http") else href
            if candidate.startswith("http"):
                self._current_url = normalize_text(candidate)
                self._capture_title = True
            return
        if tag in {"p", "span"} and any(
            marker in class_name for marker in ("res-list-summary", "res-desc")
        ):
            self._capture_snippet = True

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if self._capture_title and tag == "a":
            self._capture_title = False
        if self._capture_snippet and tag in {"p", "span"}:
            self._capture_snippet = False
        if self._inside_title and tag == "h3":
            self._inside_title = False
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
                    source_hint="so360",
                    source_label="360 搜索",
                )
            )
        self._current_title = []
        self._current_snippet = []
        self._current_url = None
        self._inside_title = False
        self._capture_title = False
        self._capture_snippet = False


class _BraveResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchHit] = []
        self._current_query = ""
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
        attrs_map = {str(k).lower(): unescape(str(v)) for k, v in attrs if k and v}
        class_name = attrs_map.get("class", "")
        if tag == "div" and "result-wrapper" in class_name.split():
            self._flush_current()
            self._inside_result = True
            self._result_depth = 1
            return
        if not self._inside_result:
            return
        self._result_depth += 1
        href = attrs_map.get("href", "")
        if tag == "a" and href.startswith(("http://", "https://")) and self._current_url is None:
            self._current_url = normalize_text(href)
            return
        if tag == "div" and "search-snippet-title" in class_name:
            title = normalize_text(re.sub(r"</?div>", " ", attrs_map.get("title", "")))
            if title:
                self._current_title.append(title)
            self._capture_title = not bool(title)
            return
        if tag == "div" and "content" in class_name.split() and "line-clamp-dynamic" in class_name:
            self._capture_snippet = True

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if self._capture_title and tag == "div":
            self._capture_title = False
        elif self._capture_snippet and tag == "div":
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
                    source_hint="brave",
                    source_label="Brave Search",
                )
            )
        self._current_title = []
        self._current_snippet = []
        self._current_url = None
        self._capture_title = False
        self._capture_snippet = False


class _YahooResultParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.results: list[SearchHit] = []
        self._current_query = ""
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
        attrs_map = {str(k).lower(): unescape(str(v)) for k, v in attrs if k and v}
        class_name = attrs_map.get("class", "")
        class_tokens = class_name.split()
        if tag == "div" and "algo" in class_tokens and "algo-sr" in class_tokens:
            self._flush_current()
            self._inside_result = True
            self._result_depth = 1
            return
        if not self._inside_result:
            return
        self._result_depth += 1
        href = attrs_map.get("href", "")
        if tag == "a" and href.startswith(("http://", "https://")) and self._current_url is None:
            self._current_url = _unwrap_yahoo_link(href)
            return
        if tag == "h3" and "title" in class_tokens:
            self._capture_title = True
            return
        if tag == "p" and "fc-dustygray" in class_tokens:
            self._capture_snippet = True

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        if self._capture_title and tag == "h3":
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
                    source_hint="yahoo",
                    source_label="Yahoo Search",
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


def _unwrap_yahoo_link(url: str) -> str:
    raw = unescape(url or "").strip()
    parsed = parse.urlparse(raw)
    if not parsed.hostname or not parsed.hostname.endswith("search.yahoo.com"):
        return raw
    match = re.search(r"/RU=([^/]+)(?:/RK=|$)", parsed.path)
    if match is None:
        return raw
    resolved = parse.unquote(match.group(1))
    return resolved if resolved.startswith(("http://", "https://")) else raw


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


def _search_so360(query: str, *, timeout_seconds: int, limit: int) -> list[SearchHit]:
    url = f"https://www.so.com/s?q={parse.quote_plus(query)}"
    req = request.Request(
        url,
        headers={
            "Accept-Language": "zh-CN,zh;q=0.9",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            ),
        },
    )
    with _safe_urlopen(req, timeout_seconds=timeout_seconds) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    parser = _SoResultParser()
    parser.begin_query(query)
    parser.feed(html)
    parser.close()
    return parser.results[:limit]


def _search_brave(query: str, *, timeout_seconds: int, limit: int) -> list[SearchHit]:
    url = "https://search.brave.com/search?" + parse.urlencode({"q": query, "source": "web"})
    req = request.Request(
        url,
        headers={
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            ),
        },
    )
    with _safe_urlopen(req, timeout_seconds=timeout_seconds) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    parser = _BraveResultParser()
    parser.begin_query(query)
    parser.feed(html)
    parser.close()
    return parser.results[:limit]


def _search_yahoo(query: str, *, timeout_seconds: int, limit: int) -> list[SearchHit]:
    url = "https://search.yahoo.com/search?" + parse.urlencode({"p": query, "n": max(10, limit)})
    req = request.Request(
        url,
        headers={
            "Accept-Language": "zh-CN,zh;q=0.9,en-US;q=0.8",
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            ),
        },
    )
    with _safe_urlopen(req, timeout_seconds=timeout_seconds) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    parser = _YahooResultParser()
    parser.begin_query(query)
    parser.feed(html)
    parser.close()
    return parser.results[:limit]


_RSS_RELEVANCE_MARKERS = (
    "文旅", "文博", "旅游", "景区", "博物馆", "文物", "导览", "医疗", "医院", "卫健", "金融", "银行",
    "教育", "学校", "政务", "政府", "数据中心", "算力", "人工智能", "大模型", "采购", "招标", "预算", "中标",
)


def _rss_hit_matches_query(hit: SearchHit, query: str) -> bool:
    normalized_query = normalize_text(query).lower()
    haystack = normalize_text(f"{hit.title} {hit.snippet} {hit.url}").lower()
    markers = [marker.lower() for marker in _RSS_RELEVANCE_MARKERS if marker.lower() in normalized_query]
    spaced_tokens = [
        token.lower()
        for token in re.split(r"[\s,，、/|:：;；（）()\"']+", normalized_query)
        if 2 <= len(token) <= 12
    ]
    unique_markers = list(dict.fromkeys(markers))
    if len(unique_markers) >= 2 and sum(marker in haystack for marker in unique_markers) < 2:
        return False
    candidates = list(dict.fromkeys([*markers, *spaced_tokens]))
    return not candidates or any(token in haystack for token in candidates)


@lru_cache(maxsize=512)
def _decode_google_news_url(url: str, timeout_seconds: int) -> str:
    parsed_url = parse.urlparse(url)
    path_parts = [part for part in parsed_url.path.split("/") if part]
    if parsed_url.hostname != "news.google.com" or len(path_parts) < 2 or path_parts[-2] not in {"articles", "read"}:
        return url
    article_token = path_parts[-1]
    params_url = f"https://news.google.com/articles/{article_token}?hl=zh-CN&gl=CN&ceid=CN:zh-Hans"
    params_req = request.Request(params_url, headers={"User-Agent": "Mozilla/5.0"})
    with _safe_urlopen(params_req, timeout_seconds=timeout_seconds) as resp:
        html = resp.read().decode("utf-8", errors="ignore")
    match = re.search(r'data-n-a-ts="([^"]+)"\s+data-n-a-sg="([^"]+)"', html)
    if match is None:
        return url
    timestamp, signature = match.groups()
    payload = [
        "Fbv4je",
        (
            '["garturlreq",[["X","X",["X","X"],null,null,1,1,"US:en",null,1,null,null,null,null,null,0,1],'
            f'"X","X",1,[1,1,1],1,1,null,0,0,null,0],"{article_token}",{timestamp},"{signature}"]'
        ),
    ]
    body = f"f.req={parse.quote(json.dumps([[payload]], separators=(',', ':')))}".encode()
    decode_req = request.Request(
        "https://news.google.com/_/DotsSplashUi/data/batchexecute",
        data=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded;charset=UTF-8",
            "User-Agent": "Mozilla/5.0",
        },
        method="POST",
    )
    with _safe_urlopen(decode_req, timeout_seconds=timeout_seconds) as resp:
        response_text = resp.read().decode("utf-8", errors="ignore")
    chunks = response_text.split("\n\n")
    if len(chunks) < 2:
        return url
    decoded_rows = json.loads(chunks[1])[:-2]
    decoded_url = normalize_text(str(json.loads(decoded_rows[0][2])[1])) if decoded_rows else ""
    if not decoded_url.startswith(("http://", "https://")):
        return url
    return decoded_url


def _search_google_news(query: str, *, timeout_seconds: int, limit: int) -> list[SearchHit]:
    url = "https://news.google.com/rss/search?" + parse.urlencode(
        {"q": query, "hl": "zh-CN", "gl": "CN", "ceid": "CN:zh-Hans"}
    )
    req = request.Request(
        url,
        headers={"Accept": "application/rss+xml, application/xml", "User-Agent": "Mozilla/5.0"},
    )
    with _safe_urlopen(req, timeout_seconds=timeout_seconds) as resp:
        payload = resp.read()
    root = ElementTree.fromstring(payload)
    results: list[SearchHit] = []
    publisher_recovery_attempts = 0
    for item in root.findall(".//item"):
        title = normalize_text(item.findtext("title") or "")
        google_url = normalize_text(item.findtext("link") or "")
        source = item.find("source")
        source_name = normalize_text(source.text or "") if source is not None else ""
        source_url = normalize_text(source.attrib.get("url", "")) if source is not None else ""
        raw_description = unescape(item.findtext("description") or "")
        published_at = normalize_text(item.findtext("pubDate") or "")
        snippet = normalize_text(
            " ".join([re.sub(r"<[^>]+>", " ", raw_description), published_at])
        )
        if not title or not google_url:
            continue
        provisional = SearchHit(title, google_url, snippet, query, source_label=source_name or "Google News")
        if not _rss_hit_matches_query(provisional, query):
            continue
        try:
            resolved_url = _decode_google_news_url(google_url, min(max(timeout_seconds, 5), 20))
        except Exception as exc:
            logger.debug("Google News URL decode failed for url=%r: %s", google_url, exc)
            resolved_url = google_url
        if (
            (parse.urlparse(resolved_url).hostname or "").lower() == "news.google.com"
            and publisher_recovery_attempts < min(3, max(1, limit))
        ):
            publisher_recovery_attempts += 1
            try:
                recovered_url = _recover_google_news_direct_url(
                    title,
                    source_url,
                    min(max(timeout_seconds, 5), 10),
                )
            except Exception as exc:
                logger.debug("Google News publisher recovery failed for url=%r: %s", google_url, exc)
                recovered_url = ""
            if recovered_url:
                resolved_url = recovered_url
        resolved_domain = (parse.urlparse(resolved_url).hostname or "").lower()
        source_hint = None
        if resolved_domain.endswith("gov.cn"):
            source_hint = (
                "procurement"
                if "ccgp.gov.cn" in resolved_domain or "ggzy.gov.cn" in resolved_domain
                else "policy"
            )
        results.append(
            SearchHit(
                title=title,
                url=resolved_url,
                snippet=snippet,
                search_query=query,
                source_hint=source_hint,
                source_label=source_name or "Google News",
            )
        )
        if len(results) >= limit:
            break
    return results


def _search_bing_rss(query: str, *, timeout_seconds: int, limit: int) -> list[SearchHit]:
    url = f"https://www.bing.com/search?format=rss&q={parse.quote_plus(query)}&setlang=zh-Hans"
    req = request.Request(
        url,
        headers={
            "Accept": "application/rss+xml, application/xml, text/xml",
            "User-Agent": "anti-fomo-research-search/1.0",
        },
    )
    with _safe_urlopen(req, timeout_seconds=timeout_seconds) as resp:
        payload = resp.read()

    root = ElementTree.fromstring(payload)
    results: list[SearchHit] = []
    for item in root.findall(".//item"):
        title = normalize_text(item.findtext("title") or "")
        url = normalize_text(item.findtext("link") or "")
        raw_description = unescape(item.findtext("description") or "")
        snippet = normalize_text(re.sub(r"<[^>]+>", " ", raw_description))
        if not title or not url:
            continue
        hit = SearchHit(
            title=title,
            url=url,
            snippet=snippet,
            search_query=query,
            source_hint="bing_rss",
            source_label="Bing RSS",
        )
        if not _rss_hit_matches_query(hit, query):
            continue
        results.append(hit)
        if len(results) >= limit:
            break
    return results


@lru_cache(maxsize=512)
def _recover_google_news_direct_url(title: str, source_url: str, timeout_seconds: int) -> str:
    """Resolve a blocked Google News wrapper through the publisher's own domain."""
    source_domain = (parse.urlparse(normalize_text(source_url)).hostname or "").lower().removeprefix("www.")
    if not source_domain:
        return ""
    compact_title = normalize_text(re.split(r"\s+-\s+", title, maxsplit=1)[0])[:72]
    if not compact_title:
        return ""
    recovery_query = f"site:{source_domain} {compact_title}"
    recovery_timeout = min(max(int(timeout_seconds), 5), 10)
    providers = (_search_so360, _search_bing_rss, _search_duckduckgo, _search_bing)
    for provider in providers:
        try:
            candidates = provider(recovery_query, timeout_seconds=recovery_timeout, limit=4)
        except Exception:
            continue
        for candidate in candidates:
            parsed_candidate = parse.urlparse(normalize_text(candidate.url))
            candidate_domain = (parsed_candidate.hostname or "").lower().removeprefix("www.")
            if not parsed_candidate.path.strip("/"):
                continue
            if candidate_domain == source_domain or candidate_domain.endswith(f".{source_domain}"):
                return normalize_text(candidate.url)
    return ""


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


def _query_site_domain(query: str) -> str:
    match = re.search(r"(?:^|\s)site:([^\s]+)", normalize_text(query).lower())
    return (match.group(1).strip("./") if match else "").removeprefix("www.")


def _search_hit_domains(hits: list[SearchHit]) -> set[str]:
    return {
        domain.removeprefix("www.")
        for hit in hits
        if (domain := (parse.urlparse(normalize_text(hit.url)).hostname or "").lower())
    }


_SEARCH_AGGREGATOR_DOMAINS = {
    "news.google.com",
    "r.search.yahoo.com",
}


def _prioritize_search_hits(hits: list[SearchHit], *, query: str) -> list[SearchHit]:
    site_domain = _query_site_domain(query)

    def priority(indexed_hit: tuple[int, SearchHit]) -> tuple[int, int, int]:
        index, hit = indexed_hit
        domain = (parse.urlparse(normalize_text(hit.url)).hostname or "").lower().removeprefix("www.")
        matches_site = bool(
            site_domain and (domain == site_domain or domain.endswith(f".{site_domain}"))
        )
        is_aggregator = domain in _SEARCH_AGGREGATOR_DOMAINS
        return (0 if matches_site else 1, 1 if is_aggregator else 0, index)

    return [hit for _, hit in sorted(enumerate(hits), key=priority)]


def _needs_provider_diversity(hits: list[SearchHit], *, query: str, limit: int) -> bool:
    deduped = _dedupe_search_hits(hits)
    required_count = max(2, min(max(1, int(limit)), max(2, int(limit) // 2)))
    site_domain = _query_site_domain(query)
    domains = _search_hit_domains(deduped)
    if site_domain:
        target_matched = any(domain == site_domain or domain.endswith(f".{site_domain}") for domain in domains)
        return len(deduped) < required_count or not target_matched
    required_domains = min(3, max(2, int(limit) // 3))
    return len(deduped) < required_count or len(domains) < required_domains


def _search_public_web(query: str, *, timeout_seconds: int, limit: int) -> list[SearchHit]:
    results: list[SearchHit] = []
    providers = (
        ("Yahoo", _search_yahoo),
        ("Brave", _search_brave),
        ("360", _search_so360),
        ("Google News", _search_google_news),
        ("Bing RSS", _search_bing_rss),
        ("DuckDuckGo", _search_duckduckgo),
        ("Bing HTML", _search_bing),
    )
    for provider_label, provider in providers:
        try:
            results.extend(provider(query, timeout_seconds=timeout_seconds, limit=limit))
        except Exception as exc:
            logger.debug("%s search failed for query=%r: %s", provider_label, query, exc)
        if not _needs_provider_diversity(results, query=query, limit=limit):
            break
    deduped = _prioritize_search_hits(_dedupe_search_hits(results), query=query)[:limit]
    if not deduped:
        logger.warning("All public search providers returned zero results for query=%r", query)
    return deduped
