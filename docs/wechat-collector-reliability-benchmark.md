# WeChat collector reliability evidence

GitHub issue #3 asked for accessibility-first navigation, perceptual screenshot deduplication, localized visual fallback, route diagnostics, and a reproducible before/after note. The implementation and evidence are deliberately split:

| Requirement | Repository evidence | Current boundary |
| --- | --- | --- |
| Accessibility-first navigation | `scripts/wechat_pc_full_auto_agent.py` probes structured accessibility candidates before visual action points; focused cases live in `backend/tests/test_wechat_pc_agent_helpers.py`. | Deterministic mocks validate ordering and fallback behavior; attributable live macOS/WeChat evidence is still environment-specific. |
| Perceptual screenshot dedupe | Production helpers `file_perceptual_hash` and `find_similar_perceptual_hash`; generated packet in [`assets/wechat-collector-reliability/benchmark.md`](./assets/wechat-collector-reliability/benchmark.md). | Synthetic fixtures only; not a claim about a specific user account or physical device. |
| Localized visual fallback | The agent combines named accessibility actions, localized menu keywords, template matches, and targeted OCR fallback. | Visual/OCR fallbacks remain lower-priority than URL/accessibility paths. |
| Route diagnostics | Batch API exposes URL-first/OCR share, accessibility/template hit rates, route stability, duplicate escapes, and perceptual-duplicate counts; settings and session summary render these fields. | Metrics explain routing behavior but do not themselves prove successful article ingestion. |

## Reproduce the fixed benchmark

```bash
backend/.venv311/bin/python scripts/wechat_collector_reliability_benchmark.py
backend/.venv311/bin/python -m pytest -q \
  backend/tests/test_wechat_collector_reliability_benchmark.py \
  backend/tests/test_wechat_pc_agent_helpers.py \
  backend/tests/test_collector_route_quality.py
```

The packet compares an exact SHA-256 baseline against the same perceptual-hash helper used by the collector. It generates six UI-like frames: one base, four expected near-duplicate variants, and one different layout. No WeChat process is opened and no private screenshot is read.

## Interpretation

The synthetic benchmark is suitable for regression detection and the requested before/after note. It is not live WeChat acceptance, end-to-end collection success, physical-device testing, production performance, or release approval. A real operator run should attach environment/version identity, the batch report digest, and the relevant route diagnostics before making any external reliability claim.
