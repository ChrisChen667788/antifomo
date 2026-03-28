from __future__ import annotations

import re
import ssl
from dataclasses import dataclass
from html import unescape
from html.parser import HTMLParser
from urllib.parse import urlparse
from urllib.request import Request, urlopen


class ContentExtractionError(Exception):
    """Raised when URL content cannot be extracted."""


@dataclass(slots=True)
class ExtractedContent:
    source_url: str
    source_domain: str | None
    title: str | None
    raw_content: str
    clean_content: str


class _HTMLTextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.title_parts: list[str] = []
        self.body_parts: list[str] = []
        self.meta_values: dict[str, str] = {}
        self._in_title = False
        self._skip_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:  # type: ignore[override]
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"}:
            self._skip_depth += 1
            return
        if lowered == "title":
            self._in_title = True
            return
        if lowered == "meta":
            attrs_map = {
                str(key).lower(): str(value)
                for key, value in attrs
                if key is not None and value is not None
            }
            key = (attrs_map.get("property") or attrs_map.get("name") or attrs_map.get("itemprop") or "").lower()
            content = attrs_map.get("content", "").strip()
            if key and content and key not in self.meta_values:
                self.meta_values[key] = content
            return
        if lowered in {"p", "div", "section", "article", "h1", "h2", "h3", "h4", "li", "br"}:
            self.body_parts.append("\n")

    def handle_endtag(self, tag: str) -> None:  # type: ignore[override]
        lowered = tag.lower()
        if lowered in {"script", "style", "noscript"} and self._skip_depth > 0:
            self._skip_depth -= 1
            return
        if lowered == "title":
            self._in_title = False
            return
        if lowered in {"p", "div", "section", "article", "li"}:
            self.body_parts.append("\n")

    def handle_data(self, data: str) -> None:  # type: ignore[override]
        if not data or self._skip_depth > 0:
            return
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.title_parts.append(text)
        else:
            self.body_parts.append(text)


def extract_domain(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlparse(url)
    return parsed.netloc.lower() or None


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", unescape(text)).strip()


def generate_title(clean_content: str, source_domain: str | None) -> str:
    if clean_content:
        candidate = clean_content[:48].strip()
        if len(candidate) >= 8:
            return candidate
    return f"{source_domain or '未知来源'} 内容摘要"


def _decode_bytes(raw_bytes: bytes, declared_charset: str | None) -> str:
    if declared_charset:
        try:
            return raw_bytes.decode(declared_charset, errors="ignore")
        except LookupError:
            pass
    return raw_bytes.decode("utf-8", errors="ignore")


def _urlopen_with_ssl_fallback(request: Request, *, timeout_seconds: int):
    try:
        return urlopen(request, timeout=timeout_seconds)
    except Exception as exc:
        if "certificate verify failed" not in str(exc).lower():
            raise
    insecure_context = ssl._create_unverified_context()
    return urlopen(request, timeout=timeout_seconds, context=insecure_context)


def _extract_from_html(html_text: str) -> tuple[str | None, str, dict[str, str]]:
    parser = _HTMLTextExtractor()
    parser.feed(html_text)
    parser.close()

    title = normalize_text(" ".join(parser.title_parts))
    body = normalize_text(" ".join(parser.body_parts))
    return (title or None), body, parser.meta_values


def _meta_first(meta_values: dict[str, str], keys: tuple[str, ...]) -> str | None:
    for key in keys:
        value = normalize_text(meta_values.get(key, ""))
        if value:
            return value
    return None


def _contains_access_block(text: str) -> bool:
    lowered = text.lower()
    hints = (
        "requiring captcha",
        "warning: this page maybe requiring captcha",
        "环境异常",
        "去验证",
        "访问受限",
        "完成验证后即可继续访问",
    )
    return any(hint in lowered for hint in hints)


def _build_access_limited_content(source_domain: str | None, source_url: str) -> tuple[str, str]:
    token = source_url.rstrip("/").split("/")[-1][:10] or "unknown"
    title = f"{source_domain or '未知来源'} 文章 {token}（访问受限）"
    clean_content = (
        f"该链接当前访问受限，未能抓取到正文。来源域名：{source_domain or '未知来源'}。"
        "可能需要登录、验证码或授权后才能读取。"
        "建议在已登录浏览器中通过插件重新提交页面，或直接粘贴文章正文。"
    )
    return title, clean_content


def extract_from_url(
    url: str,
    *,
    timeout_seconds: int = 12,
    max_bytes: int = 2_000_000,
) -> ExtractedContent:
    request = Request(
        url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            )
        },
    )

    try:
        with _urlopen_with_ssl_fallback(request, timeout_seconds=timeout_seconds) as response:
            content_type = (response.headers.get("Content-Type") or "").lower()
            declared_charset = response.headers.get_content_charset()
            raw_bytes = response.read(max_bytes)
    except Exception as exc:
        raise ContentExtractionError(f"Failed to fetch URL: {exc}") from exc

    text = _decode_bytes(raw_bytes, declared_charset)
    if not text:
        raise ContentExtractionError("Fetched response is empty")

    if "html" in content_type or "<html" in text.lower():
        title, body, meta = _extract_from_html(text)
        meta_title = _meta_first(meta, ("og:title", "twitter:title", "title"))
        meta_description = _meta_first(meta, ("og:description", "twitter:description", "description"))
        meta_keywords = _meta_first(meta, ("keywords",))

        if not title and meta_title:
            title = meta_title

        if len(body) < 80:
            merged = normalize_text(" ".join(filter(None, [meta_description, meta_keywords])))
            if len(merged) > len(body):
                body = merged

        if _contains_access_block(f"{title or ''} {body}"):
            title, body = _build_access_limited_content(extract_domain(url), url)
    else:
        title, body = None, normalize_text(text)

    if len(body) < 20:
        raise ContentExtractionError("Extracted text is too short")

    return ExtractedContent(
        source_url=url,
        source_domain=extract_domain(url),
        title=title,
        raw_content=body,
        clean_content=body,
    )


def extract_from_reader_proxy(
    url: str,
    *,
    timeout_seconds: int = 20,
    max_bytes: int = 2_000_000,
) -> ExtractedContent:
    target = url.strip()
    if target.startswith("https://"):
        target = "http://" + target[len("https://") :]
    elif not target.startswith("http://"):
        target = "http://" + target

    proxy_url = f"https://r.jina.ai/{target}"
    request = Request(
        proxy_url,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0 Safari/537.36"
            )
        },
    )
    try:
        with _urlopen_with_ssl_fallback(request, timeout_seconds=timeout_seconds) as response:
            raw_bytes = response.read(max_bytes)
    except Exception as exc:
        raise ContentExtractionError(f"Reader proxy fetch failed: {exc}") from exc

    text = raw_bytes.decode("utf-8", errors="ignore")
    if not text:
        raise ContentExtractionError("Reader proxy returned empty response")

    title_match = re.search(r"^Title:\s*(.+)$", text, flags=re.MULTILINE)
    title = normalize_text(title_match.group(1)) if title_match else None

    _, _, markdown_part = text.partition("Markdown Content:")
    body = normalize_text(markdown_part or text)

    source_domain = extract_domain(url)
    if _contains_access_block(f"{title or ''} {body}"):
        title, body = _build_access_limited_content(source_domain, url)

    if len(body) < 20:
        raise ContentExtractionError("Reader proxy extracted text is too short")

    return ExtractedContent(
        source_url=url,
        source_domain=source_domain,
        title=title,
        raw_content=body,
        clean_content=body,
    )
