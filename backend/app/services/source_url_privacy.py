from __future__ import annotations

import re
from typing import Any
from urllib import parse as urllib_parse


WECHAT_CANONICAL_QUERY_KEYS = ("__biz", "mid", "idx", "sn", "chksm")
_HTTP_URL_PATTERN = re.compile(r"https?://[^\s<>\"']+", flags=re.IGNORECASE)
_TRAILING_URL_PUNCTUATION_PATTERN = re.compile(r"[),.;，。；）】》]+$")


def _normalized_http_parts(value: str | None) -> urllib_parse.SplitResult | None:
    raw = str(value or "").strip()
    if not raw:
        return None

    try:
        parsed = urllib_parse.urlsplit(raw)
        hostname = parsed.hostname
        port = parsed.port
    except ValueError:
        return None
    scheme = parsed.scheme.lower()
    if scheme not in {"http", "https"} or not hostname:
        return None

    normalized_host = hostname.lower().rstrip(".")
    if not normalized_host:
        return None
    if ":" in normalized_host and not normalized_host.startswith("["):
        normalized_host = f"[{normalized_host}]"
    if port is not None and not (
        (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    ):
        netloc = f"{normalized_host}:{port}"
    else:
        netloc = normalized_host

    path = parsed.path or "/"
    if path != "/":
        path = path.rstrip("/") or "/"
    return parsed._replace(scheme=scheme, netloc=netloc, path=path, fragment="")


def normalize_fetch_url(value: str | None) -> str | None:
    """Normalize a temporary fetch target without dropping its query string.

    Fetch URLs may need short-lived authorization or routing parameters. Callers
    must keep this result out of persisted URL fields and logs.
    """

    parsed = _normalized_http_parts(value)
    if parsed is None:
        return None
    return urllib_parse.urlunsplit(parsed)


def canonicalize_persisted_url(value: str | None) -> str | None:
    """Return the privacy-safe URL representation allowed in durable storage."""

    parsed = _normalized_http_parts(value)
    if parsed is None:
        return None

    query = parsed.query
    if (parsed.hostname or "").lower() == "mp.weixin.qq.com":
        values_by_key: dict[str, list[str]] = {key: [] for key in WECHAT_CANONICAL_QUERY_KEYS}
        for key, item in urllib_parse.parse_qsl(parsed.query, keep_blank_values=True):
            if key in values_by_key:
                values_by_key[key].append(item)
        stable_pairs = [
            (key, item)
            for key in WECHAT_CANONICAL_QUERY_KEYS
            for item in sorted(values_by_key[key])
        ]
        query = urllib_parse.urlencode(stable_pairs, doseq=True)

    return urllib_parse.urlunsplit(parsed._replace(query=query))


def redact_sensitive_urls(value: object) -> str:
    """Replace URLs embedded in durable text or logs with privacy-safe forms."""

    text = str(value or "")

    def replace(match: re.Match[str]) -> str:
        candidate = match.group(0)
        trailing_match = _TRAILING_URL_PUNCTUATION_PATTERN.search(candidate)
        trailing = trailing_match.group(0) if trailing_match else ""
        core = candidate[: -len(trailing)] if trailing else candidate
        canonical = canonicalize_persisted_url(core)
        return f"{canonical or '[invalid-url]'}{trailing}"

    return _HTTP_URL_PATTERN.sub(replace, text)


def redact_sensitive_url_values(value: Any) -> Any:
    """Recursively scrub URL-bearing strings in durable JSON-style payloads."""

    if isinstance(value, str):
        return redact_sensitive_urls(value)
    if isinstance(value, list):
        return [redact_sensitive_url_values(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_sensitive_url_values(item) for item in value)
    if isinstance(value, dict):
        return {
            key: redact_sensitive_url_values(item)
            for key, item in value.items()
        }
    return value
