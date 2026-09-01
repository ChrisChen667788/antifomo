#!/usr/bin/env python3
"""Generate a deterministic, synthetic benchmark for WeChat capture dedupe.

This benchmark exercises the production perceptual-hash helpers with generated
UI-like frames.  It does not automate WeChat, use personal content, or claim
physical-device / production reliability.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AGENT_PATH = PROJECT_ROOT / "scripts" / "wechat_pc_full_auto_agent.py"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "docs" / "assets" / "wechat-collector-reliability"
BENCHMARK_VERSION = "wechat-dedupe-synthetic-v1"


def _load_agent_module():
    spec = importlib.util.spec_from_file_location("wechat_pc_full_auto_agent_benchmark", AGENT_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Unable to load collector helper module: {AGENT_PATH}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _draw_ui_frame(path: Path, *, offset_x: int = 0, offset_y: int = 0, alternate: bool = False) -> None:
    image = Image.new("RGB", (300, 220), "white")
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle((20, 16, 280, 204), radius=18, outline="#1f2937", width=4)
    if alternate:
        draw.rectangle((40, 42, 116, 178), fill="#111827")
        draw.ellipse((178, 54, 252, 128), fill="#64748b")
        draw.line((156, 164, 258, 164), fill="#0f172a", width=8)
    else:
        x = offset_x
        y = offset_y
        draw.ellipse((42 + x, 40 + y, 76 + x, 74 + y), fill="#111827")
        for row in range(3):
            top = 42 + y + row * 48
            draw.rounded_rectangle((92 + x, top, 258 + x, top + 13), radius=6, fill="#334155")
            draw.rounded_rectangle((92 + x, top + 21, 220 + x, top + 30), radius=4, fill="#94a3b8")
    image.save(path)


def _build_frames(directory: Path) -> list[dict[str, Any]]:
    base = directory / "base.png"
    exact = directory / "exact-copy.png"
    shift_one = directory / "shift-1px.png"
    shift_three = directory / "shift-3px.png"
    brightness = directory / "brightness.png"
    different = directory / "different.png"

    _draw_ui_frame(base)
    exact.write_bytes(base.read_bytes())
    _draw_ui_frame(shift_one, offset_x=1, offset_y=1)
    _draw_ui_frame(shift_three, offset_x=3, offset_y=2)
    with Image.open(base) as image:
        ImageEnhance.Brightness(image).enhance(0.92).save(brightness)
    _draw_ui_frame(different, alternate=True)

    return [
        {"key": "base", "path": base, "expected_group": "article_a"},
        {"key": "exact_copy", "path": exact, "expected_group": "article_a"},
        {"key": "shift_1px", "path": shift_one, "expected_group": "article_a"},
        {"key": "shift_3px", "path": shift_three, "expected_group": "article_a"},
        {"key": "brightness_92pct", "path": brightness, "expected_group": "article_a"},
        {"key": "different_layout", "path": different, "expected_group": "article_b"},
    ]


def run_benchmark(*, threshold: int = 10) -> dict[str, Any]:
    agent = _load_agent_module()
    with TemporaryDirectory(prefix="anti-fomo-wechat-benchmark-") as temp_dir:
        frames = _build_frames(Path(temp_dir))
        exact_seen: set[str] = set()
        perceptual_state: dict[str, dict[str, str]] = {"processed_hashes": {}}
        rows: list[dict[str, Any]] = []
        exact_duplicates = 0
        perceptual_duplicates = 0

        for frame in frames:
            raw = frame["path"].read_bytes()
            exact_digest = hashlib.sha256(raw).hexdigest()
            exact_duplicate = exact_digest in exact_seen
            exact_seen.add(exact_digest)

            perceptual_digest = agent.file_perceptual_hash(frame["path"])
            matched_digest, distance = agent.find_similar_perceptual_hash(
                perceptual_state,
                perceptual_digest,
                threshold=threshold,
            )
            perceptual_duplicate = matched_digest is not None
            if perceptual_digest and not perceptual_duplicate:
                perceptual_state["processed_hashes"][perceptual_digest] = "synthetic"

            exact_duplicates += int(exact_duplicate)
            perceptual_duplicates += int(perceptual_duplicate)
            rows.append(
                {
                    "frame_key": frame["key"],
                    "expected_group": frame["expected_group"],
                    "exact_duplicate": exact_duplicate,
                    "perceptual_duplicate": perceptual_duplicate,
                    "perceptual_distance": distance,
                }
            )

    expected_duplicate_count = sum(1 for row in rows[1:] if row["expected_group"] == "article_a")
    exact_unique = len(rows) - exact_duplicates
    perceptual_unique = len(rows) - perceptual_duplicates
    result = {
        "benchmark_version": BENCHMARK_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "evidence_scope": "deterministic_synthetic_helper_benchmark",
        "physical_device_capture": False,
        "live_wechat_automation": False,
        "production_readiness_evidence": False,
        "method": {
            "baseline": "exact SHA-256 byte equality",
            "candidate": "production 64-bit difference perceptual hash",
            "perceptual_hamming_threshold": threshold,
            "fixture_count": len(rows),
            "expected_duplicate_count": expected_duplicate_count,
        },
        "summary": {
            "baseline_duplicate_detections": exact_duplicates,
            "perceptual_duplicate_detections": perceptual_duplicates,
            "baseline_duplicate_recall_percent": round(exact_duplicates / expected_duplicate_count * 100),
            "perceptual_duplicate_recall_percent": round(perceptual_duplicates / expected_duplicate_count * 100),
            "baseline_accepted_frames": exact_unique,
            "perceptual_accepted_frames": perceptual_unique,
            "accepted_frame_reduction_percent": round((exact_unique - perceptual_unique) / exact_unique * 100),
        },
        "frames": rows,
        "limitations": [
            "Synthetic UI-like frames only; no personal WeChat content is loaded.",
            "This measures helper behavior, not end-to-end collector success or physical-device performance.",
            "Threshold changes require a new benchmark version and human review before rollout.",
        ],
    }
    digest_payload = {key: value for key, value in result.items() if key != "generated_at"}
    result["report_digest"] = hashlib.sha256(
        json.dumps(digest_payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return result


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    rows = "\n".join(
        "| {frame_key} | {expected_group} | {exact_duplicate} | {perceptual_duplicate} | {distance} |".format(
            distance=row["perceptual_distance"] if row["perceptual_distance"] is not None else "-",
            **row,
        )
        for row in report["frames"]
    )
    return f"""# WeChat collector synthetic dedupe benchmark

This generated evidence packet compares exact-byte screenshot deduplication with the production perceptual-hash helper on deterministic synthetic UI-like frames.

- Benchmark: `{report['benchmark_version']}`
- Scope: `{report['evidence_scope']}`
- Input frames: `{report['method']['fixture_count']}`
- Expected near-duplicate variants: `{report['method']['expected_duplicate_count']}`
- Exact baseline duplicate recall: `{summary['baseline_duplicate_recall_percent']}%`
- Perceptual duplicate recall: `{summary['perceptual_duplicate_recall_percent']}%`
- Accepted-frame reduction versus exact baseline: `{summary['accepted_frame_reduction_percent']}%`
- Report digest: `{report['report_digest']}`

| Frame | Expected group | Exact duplicate | Perceptual duplicate | Hamming distance |
| --- | --- | ---: | ---: | ---: |
{rows}

## Evidence boundary

This is a deterministic helper benchmark, not a live WeChat, physical-device, production-performance, or release-approval result. Existing accessibility-first navigation, localized template/OCR fallbacks, and route-quality diagnostics remain covered by focused code tests and must still be validated in an attributable operator environment.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--threshold", type=int, default=10)
    args = parser.parse_args()
    if not 0 <= args.threshold <= 64:
        parser.error("--threshold must be between 0 and 64")

    report = run_benchmark(threshold=args.threshold)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "benchmark.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "benchmark.md").write_text(_render_markdown(report), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
