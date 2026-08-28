#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"


def _bootstrap_backend(database_url: str | None) -> None:
    os.chdir(BACKEND_ROOT)
    if database_url:
        os.environ["DATABASE_URL"] = database_url
    if str(BACKEND_ROOT) not in sys.path:
        sys.path.insert(0, str(BACKEND_ROOT))


def _sqlite_path_from_url(database_url: str) -> Path | None:
    if not database_url.startswith("sqlite"):
        return None
    parsed = urlparse(database_url)
    if parsed.path and parsed.path != "/":
        candidate = Path(parsed.path)
        if candidate.is_absolute():
            return candidate
        return (BACKEND_ROOT / candidate).resolve()
    raw = database_url.split("sqlite:///", 1)[-1]
    if not raw:
        return None
    candidate = Path(raw)
    if candidate.is_absolute():
        return candidate
    return (BACKEND_ROOT / candidate).resolve()


def _backup_database(database_url: str, backup_dir: Path) -> str:
    db_path = _sqlite_path_from_url(database_url)
    if db_path is None or not db_path.exists():
        return ""
    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup_path = backup_dir / f"{db_path.stem}-before-low-quality-repair-{timestamp}{db_path.suffix}"
    shutil.copy2(db_path, backup_path)
    return str(backup_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Repair low-quality research reports for release-hardening gates.")
    parser.add_argument("--database-url", help="Override backend DATABASE_URL for this run.")
    parser.add_argument("--target-rate", type=float, default=0.10, help="Target flagged/total rate.")
    parser.add_argument("--max-items", type=int, default=40, help="Maximum entries to attempt in one run.")
    parser.add_argument("--dry-run", action="store_true", help="Only list candidate entries; do not mutate the DB.")
    parser.add_argument(
        "--accept-zero-risk",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Accept a deterministic rewrite only when the post-rewrite risk score is zero.",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=ROOT / ".tmp" / "db-backups",
        help="Directory for SQLite backups before mutation.",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=ROOT / ".tmp" / "release_hardening_low_quality_repair.json",
        help="Path to write the machine-readable repair report.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    _bootstrap_backend(args.database_url)

    from app.core.config import get_settings
    from app.db.session import SessionLocal
    from app.services.research_review_service import (
        list_low_quality_research_review_queue,
        resolve_low_quality_research_entry,
        rewrite_low_quality_research_entry,
    )

    settings = get_settings()
    database_url = args.database_url or settings.database_url
    report: dict[str, object] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database_url": database_url,
        "target_rate": args.target_rate,
        "dry_run": args.dry_run,
        "backup_path": "",
        "before": {},
        "after": {},
        "processed": [],
        "skipped": [],
    }
    with SessionLocal() as db:
        before = list_low_quality_research_review_queue(db, top=max(1, args.max_items), include_resolved=False)
        total = int(before.get("total_reports") or 0)
        target_flagged = int(total * max(0.0, min(args.target_rate, 1.0)))
        report["before"] = {
            "total_reports": total,
            "flagged_reports": int(before.get("flagged_reports") or 0),
            "invalid_payloads": int(before.get("invalid_payloads") or 0),
            "target_flagged_reports": target_flagged,
        }
        if args.dry_run:
            report["processed"] = [
                {
                    "entry_id": item.get("entry_id"),
                    "title": item.get("entry_title"),
                    "risk_score": item.get("risk_score"),
                    "issue_codes": item.get("issue_codes"),
                }
                for item in list(before.get("items") or [])[: max(0, args.max_items)]
            ]
        else:
            report["backup_path"] = _backup_database(database_url, args.backup_dir)
            attempts = 0
            attempted_ids: set[str] = set()
            while attempts < max(0, args.max_items):
                queue = list_low_quality_research_review_queue(db, top=max(1, args.max_items), include_resolved=False)
                flagged = int(queue.get("flagged_reports") or 0)
                if flagged <= target_flagged:
                    break
                candidates = [
                    item
                    for item in list(queue.get("items") or [])
                    if str(item.get("entry_id") or "") not in attempted_ids
                ]
                if not candidates:
                    break
                item = candidates[0]
                entry_id = str(item.get("entry_id") or "")
                attempts += 1
                if not entry_id:
                    report["skipped"].append({"reason": "missing_entry_id", "item": item})  # type: ignore[union-attr]
                    continue
                attempted_ids.add(entry_id)
                try:
                    current_risk = int(item.get("risk_score") or 0)
                    if args.accept_zero_risk and current_risk == 0:
                        resolve_low_quality_research_entry(db, entry_id=entry_id, action="accept")
                        report["processed"].append(  # type: ignore[union-attr]
                            {
                                "entry_id": entry_id,
                                "before_risk_score": 0,
                                "after_risk_score": 0,
                                "review_status": item.get("review_status"),
                                "accepted": True,
                                "accept_mode": "existing_zero_risk",
                            }
                        )
                        continue
                    rewritten = rewrite_low_quality_research_entry(db, entry_id)
                    diff = rewritten.get("diff") or {}
                    after_risk = int(diff.get("after_risk_score") or 0)
                    processed = {
                        "entry_id": entry_id,
                        "before_risk_score": int(diff.get("before_risk_score") or item.get("risk_score") or 0),
                        "after_risk_score": after_risk,
                        "review_status": rewritten.get("review_status"),
                        "accepted": False,
                    }
                    if args.accept_zero_risk and after_risk == 0:
                        resolve_low_quality_research_entry(db, entry_id=entry_id, action="accept")
                        processed["accepted"] = True
                    report["processed"].append(processed)  # type: ignore[union-attr]
                except Exception as exc:
                    report["skipped"].append(  # type: ignore[union-attr]
                        {
                            "entry_id": entry_id,
                            "reason": str(exc),
                            "risk_score": item.get("risk_score"),
                            "issue_codes": item.get("issue_codes"),
                        }
                    )
            after = list_low_quality_research_review_queue(db, top=max(1, args.max_items), include_resolved=False)
            report["after"] = {
                "total_reports": int(after.get("total_reports") or 0),
                "flagged_reports": int(after.get("flagged_reports") or 0),
                "invalid_payloads": int(after.get("invalid_payloads") or 0),
                "target_flagged_reports": target_flagged,
            }

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
