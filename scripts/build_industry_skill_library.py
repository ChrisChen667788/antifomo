#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "backend"))

from app.services.industry_skill_library import (  # noqa: E402
    DEFAULT_LIBRARY_DIR,
    DEFAULT_SOURCE_ROOT,
    build_industry_skill_library,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a full-content local industry RAG and solution-intelligence skills.")
    parser.add_argument("--source-dir", default=str(DEFAULT_SOURCE_ROOT), help="Source folder; original files are never moved.")
    parser.add_argument("--output-dir", default=str(DEFAULT_LIBRARY_DIR), help="Generated local catalog and skill bundle directory.")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent local extractors, capped at 8.")
    parser.add_argument("--skip-rag", action="store_true", help="Analyze full contents but skip SQLite FTS and vector index generation.")
    parser.add_argument("--skip-ocr", action="store_true", help="Skip macOS Vision OCR for scanned PDFs and mark them as pending.")
    parser.add_argument("--max-excerpt-chars", type=int, default=5000, help="Maximum public reference excerpt characters retained in the catalog.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    last_reported = 0
    last_embedded = 0

    def progress(completed: int, total: int) -> None:
        nonlocal last_reported
        if completed == total or completed - last_reported >= 20:
            last_reported = completed
            print(f"indexed {completed}/{total}", flush=True)

    def rag_progress(stage: str, completed: int, total: int) -> None:
        nonlocal last_embedded
        if stage == "embedding" and (completed == total or completed - last_embedded >= 1000):
            last_embedded = completed
            print(f"embedded {completed}/{total}", flush=True)

    catalog = build_industry_skill_library(
        source_root=args.source_dir,
        library_dir=args.output_dir,
        workers=args.workers,
        max_excerpt_chars=args.max_excerpt_chars,
        progress=progress,
        rag_progress=rag_progress,
        build_rag=not args.skip_rag,
        enable_ocr=not args.skip_ocr,
    )
    summary = catalog["summary"]
    print(
        json.dumps(
            {
                "catalog_path": str(Path(args.output_dir) / "catalog.json"),
                "classification_report": str(Path(args.output_dir) / "classification-report.md"),
                "document_count": summary["source_file_count"],
                "skill_count": summary["skill_count"],
                "extracted_count": summary["extracted_count"],
                "full_content_analyzed_count": summary.get("full_content_analyzed_count", 0),
                "ocr_analyzed_count": summary.get("ocr_analyzed_count", 0),
                "ocr_pending_count": summary.get("ocr_pending_count", 0),
                "knowledge_base": catalog.get("knowledge_base", {}),
                "needs_review_count": summary["needs_review_count"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
