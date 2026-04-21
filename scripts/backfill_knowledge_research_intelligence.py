#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
BACKEND_ROOT = ROOT / "backend"
os.chdir(BACKEND_ROOT)
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.db.session import SessionLocal  # noqa: E402
from app.services.knowledge_intelligence_service import backfill_research_knowledge_intelligence  # noqa: E402


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Backfill stored research.report knowledge intelligence with batching and checkpoint support."
    )
    parser.add_argument("--batch-size", type=int, default=20, help="Number of rows to read per DB page.")
    parser.add_argument(
        "--commit-every",
        type=int,
        default=20,
        help="Commit and persist checkpoint every N processed rows.",
    )
    parser.add_argument(
        "--max-rows",
        type=int,
        default=None,
        help="Optional row budget for this run. Use with --resume for chunked execution.",
    )
    parser.add_argument(
        "--checkpoint",
        type=Path,
        default=ROOT / ".tmp" / "backfill-checkpoints" / "research-report-intelligence.json",
        help="Checkpoint file path used for resume.",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Resume from the checkpoint instead of starting from the beginning.",
    )
    return parser


def main() -> int:
    args = _build_parser().parse_args()
    checkpoint_path = args.checkpoint if args.checkpoint.is_absolute() else (ROOT / args.checkpoint)
    db = SessionLocal()
    try:
        result = backfill_research_knowledge_intelligence(
            db,
            batch_size=args.batch_size,
            commit_every=args.commit_every,
            checkpoint_path=checkpoint_path,
            resume=args.resume,
            max_rows=args.max_rows,
        )
    finally:
        db.close()
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
