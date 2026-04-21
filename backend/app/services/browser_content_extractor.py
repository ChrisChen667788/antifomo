from __future__ import annotations

import json
import subprocess
from pathlib import Path

from app.core.config import BACKEND_DIR, get_settings
from app.services.content_extractor import (
    ContentExtractionError,
    ExtractedContent,
    extract_domain,
    normalize_text,
)


PROJECT_ROOT = BACKEND_DIR.parent
BROWSER_EXTRACT_SCRIPT = PROJECT_ROOT / "scripts" / "browser_extract_article.mjs"


def _build_browser_extract_command(url: str, *, timeout_seconds: int) -> list[str]:
    settings = get_settings()
    command = [
        "node",
        str(BROWSER_EXTRACT_SCRIPT),
        "--url",
        url,
        "--chrome-path",
        settings.browser_extractor_chrome_path,
        "--timeout-sec",
        str(timeout_seconds),
    ]
    if settings.browser_extractor_user_data_dir:
        command.extend(["--user-data-dir", settings.browser_extractor_user_data_dir])
    if settings.browser_extractor_profile_dir:
        command.extend(["--profile-dir", settings.browser_extractor_profile_dir])
    if not settings.browser_extractor_headless:
        command.append("--headful")
    return command


def extract_from_browser(
    url: str,
    *,
    timeout_seconds: int | None = None,
) -> ExtractedContent:
    settings = get_settings()
    if not settings.browser_extractor_enabled:
        raise ContentExtractionError("Browser extractor is disabled")
    if not BROWSER_EXTRACT_SCRIPT.exists():
        raise ContentExtractionError(f"Browser extractor script not found: {BROWSER_EXTRACT_SCRIPT}")

    resolved_timeout = max(8, int(timeout_seconds or settings.browser_extractor_timeout_seconds))
    command = _build_browser_extract_command(url, timeout_seconds=resolved_timeout)

    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=False,
            timeout=resolved_timeout + 15,
            cwd=str(PROJECT_ROOT),
        )
    except subprocess.TimeoutExpired as exc:
        raise ContentExtractionError(f"Browser extraction timed out after {resolved_timeout}s") from exc
    except Exception as exc:  # pragma: no cover - defensive shell failure path
        raise ContentExtractionError(f"Browser extraction failed to start: {exc}") from exc

    stdout = (completed.stdout or "").strip()
    stderr = normalize_text(completed.stderr or "")
    if completed.returncode != 0:
        detail = stderr or normalize_text(stdout)
        raise ContentExtractionError(f"Browser extraction failed: {detail or completed.returncode}")

    last_line = stdout.splitlines()[-1] if stdout else ""
    try:
        payload = json.loads(last_line)
    except json.JSONDecodeError as exc:
        raise ContentExtractionError("Browser extractor returned invalid JSON") from exc

    body_text = normalize_text(str(payload.get("body_text", "") or ""))
    raw_content = normalize_text(str(payload.get("raw_content", "") or body_text))
    title = normalize_text(str(payload.get("title", "") or "")) or None
    final_url = normalize_text(str(payload.get("page_url", "") or "")) or url
    source_domain = normalize_text(str(payload.get("source_domain", "") or "")) or extract_domain(final_url)

    if len(body_text) < 80:
        raise ContentExtractionError("Browser extractor returned too little text")

    return ExtractedContent(
        source_url=final_url,
        source_domain=source_domain,
        title=title,
        raw_content=raw_content or body_text,
        clean_content=body_text,
    )
