from __future__ import annotations

from urllib.parse import urlparse, urlunparse

from app.services.content_extractor import normalize_text


def is_valid_http_url(url: str | None) -> bool:
    if not url:
        return False
    parsed = urlparse(url.strip())
    return parsed.scheme in {"http", "https"} and bool(parsed.netloc)


def clean_text(value: str | None) -> str:
    return normalize_text(value or "")


def normalize_source_url(url: str | None) -> str | None:
    if not url:
        return None
    text = str(url).strip()
    if not text:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    scheme = parsed.scheme.lower()
    netloc = parsed.netloc.lower()
    path = parsed.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")
    normalized = parsed._replace(scheme=scheme, netloc=netloc, path=path, fragment="")
    return urlunparse(normalized)
