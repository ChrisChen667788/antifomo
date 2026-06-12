from __future__ import annotations

from collections.abc import Iterable

from app.services.content_extractor import normalize_text


def dedupe_strings(values: Iterable[object], limit: int) -> list[str]:
    deduped: list[str] = []
    seen: set[str] = set()
    for value in values:
        normalized = normalize_text(str(value or ""))
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        deduped.append(normalized)
        if len(deduped) >= limit:
            break
    return deduped
