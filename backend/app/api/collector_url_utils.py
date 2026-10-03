from __future__ import annotations

from app.services.content_extractor import normalize_text
from app.services.source_url_privacy import (
    canonicalize_persisted_url,
    normalize_fetch_url,
)


def is_valid_http_url(url: str | None) -> bool:
    return normalize_fetch_url(url) is not None


def clean_text(value: str | None) -> str:
    return normalize_text(value or "")


normalize_source_url = canonicalize_persisted_url


__all__ = [
    "canonicalize_persisted_url",
    "clean_text",
    "is_valid_http_url",
    "normalize_fetch_url",
    "normalize_source_url",
]
