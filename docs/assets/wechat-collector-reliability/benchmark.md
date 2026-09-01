# WeChat collector synthetic dedupe benchmark

This generated evidence packet compares exact-byte screenshot deduplication with the production perceptual-hash helper on deterministic synthetic UI-like frames.

- Benchmark: `wechat-dedupe-synthetic-v1`
- Scope: `deterministic_synthetic_helper_benchmark`
- Input frames: `6`
- Expected near-duplicate variants: `4`
- Exact baseline duplicate recall: `25%`
- Perceptual duplicate recall: `100%`
- Accepted-frame reduction versus exact baseline: `60%`
- Report digest: `e1764aa6004a8c43709d11d22c2e5a835cd9cf8529165787e5c9e2b61a0d39d2`

| Frame | Expected group | Exact duplicate | Perceptual duplicate | Hamming distance |
| --- | --- | ---: | ---: | ---: |
| base | article_a | False | False | - |
| exact_copy | article_a | True | True | 0 |
| shift_1px | article_a | False | True | 3 |
| shift_3px | article_a | False | True | 9 |
| brightness_92pct | article_a | False | True | 3 |
| different_layout | article_b | False | False | - |

## Evidence boundary

This is a deterministic helper benchmark, not a live WeChat, physical-device, production-performance, or release-approval result. Existing accessibility-first navigation, localized template/OCR fallbacks, and route-quality diagnostics remain covered by focused code tests and must still be validated in an attributable operator environment.
