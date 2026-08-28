from __future__ import annotations

from datetime import UTC, datetime
import hashlib
import json
from typing import Any


def utc_now() -> datetime:
    return datetime.now(UTC)


def iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
    return normalized.isoformat().replace("+00:00", "Z")


def canonical_digest(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def audit_event(*, action: str, actor_id: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "action": action,
        "actor_id": actor_id,
        "details": details or {},
        "at": iso(utc_now()),
    }
