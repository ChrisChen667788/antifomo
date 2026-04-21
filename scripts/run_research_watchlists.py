#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run due Anti-FOMO research watchlists via local API.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000", help="Backend base URL")
    parser.add_argument("--limit", type=int, default=6, help="Max number of due watchlists to refresh")
    parser.add_argument("--output-language", default="zh-CN", help="Research output language")
    parser.add_argument("--max-sources", type=int, default=12, help="Max sources per watchlist refresh")
    parser.add_argument("--without-wechat", action="store_true", help="Skip WeChat sources")
    parser.add_argument("--no-save", action="store_true", help="Do not persist refreshed reports into knowledge")
    parser.add_argument("--notify", action="store_true", help="Send macOS notification when watchlists refreshed or failed")
    parser.add_argument(
        "--state-file",
        default=str(Path(__file__).resolve().parents[1] / ".tmp" / "watchlist_scheduler.last.json"),
        help="Where to persist the latest scheduler result",
    )
    parser.add_argument("--notification-title", default="AntiFomo Watchlists", help="Notification title")
    return parser


def _write_state(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _notify(title: str, message: str) -> None:
    safe_message = message.replace('"', '\\"')
    safe_title = title.replace('"', '\\"')
    try:
        subprocess.run(
            ["osascript", "-e", f'display notification "{safe_message}" with title "{safe_title}"'],
            capture_output=True,
            text=True,
            check=False,
            timeout=8,
        )
    except Exception:
        return


def main() -> int:
    args = build_parser().parse_args()
    state_path = Path(args.state_file).expanduser()
    payload = {
      "output_language": args.output_language,
      "include_wechat": not args.without_wechat,
      "max_sources": args.max_sources,
      "save_to_knowledge": not args.no_save,
    }
    endpoint = f"{args.base_url.rstrip('/')}/api/research/watchlists/run-due?limit={max(1, min(args.limit, 12))}"
    request = Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=600) as response:
            body = response.read().decode("utf-8")
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        print(f"[watchlists] HTTP {exc.code}: {detail or exc.reason}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"[watchlists] request failed: {exc}", file=sys.stderr)
        return 1

    try:
        result = json.loads(body)
    except json.JSONDecodeError:
        print("[watchlists] invalid JSON response", file=sys.stderr)
        return 1

    state_payload = {
        "checked_at": result.get("checked_at"),
        "due_count": int(result.get("due_count") or 0),
        "refreshed_count": int(result.get("refreshed_count") or 0),
        "failed_count": int(result.get("failed_count") or 0),
        "items": result.get("items") or [],
    }
    _write_state(state_path, state_payload)

    print(
        f"[watchlists] checked={result.get('checked_at')} due={result.get('due_count', 0)} "
        f"refreshed={result.get('refreshed_count', 0)} failed={result.get('failed_count', 0)}"
    )
    for item in result.get("items", []):
        summary = item.get("summary") or item.get("error") or ""
        print(
            f"- {item.get('name', 'Watchlist')} | {item.get('status', 'unknown')} | "
            f"changes={item.get('change_count', 0)} | {summary}"
        )
    if args.notify and (state_payload["refreshed_count"] or state_payload["failed_count"]):
        message = (
            f"refreshed={state_payload['refreshed_count']} failed={state_payload['failed_count']} "
            f"due={state_payload['due_count']}"
        )
        _notify(args.notification_title, message)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
