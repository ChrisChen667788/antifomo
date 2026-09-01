from __future__ import annotations

import importlib.util
from pathlib import Path
import sys


MODULE_PATH = Path(__file__).resolve().parents[2] / "scripts" / "wechat_collector_reliability_benchmark.py"
SPEC = importlib.util.spec_from_file_location("wechat_collector_reliability_benchmark", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC and SPEC.loader
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def test_synthetic_perceptual_dedupe_outperforms_exact_baseline() -> None:
    report = MODULE.run_benchmark(threshold=10)

    assert report["method"]["fixture_count"] == 6
    assert report["method"]["expected_duplicate_count"] == 4
    assert report["summary"]["baseline_duplicate_detections"] == 1
    assert report["summary"]["perceptual_duplicate_detections"] == 4
    assert report["summary"]["perceptual_duplicate_recall_percent"] == 100
    assert report["summary"]["accepted_frame_reduction_percent"] == 60
    assert report["physical_device_capture"] is False
    assert report["production_readiness_evidence"] is False
