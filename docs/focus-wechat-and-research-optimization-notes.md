# Focus WeChat URL-first + Research Quality Optimization Notes

## 1. WeChat Collection: Chosen Direction

Current practical order:

1. Browser URL directly available
2. WeChat article page share/copy link UI automation
3. Historical true-link recovery
4. OCR fallback

Why this remains the best path:

- Tencent official WorkBuddy/CodeBuddy provides control and delegation, not a personal public-account feed URL API.
- Existing third-party schemes are either unstable, platform-limited, or do not actually solve "enumerate personal WeChat article URLs".
- For this product, the highest-value iteration is not replacing the stack, but making the `share/copy link` path much more robust.

Engineering principles adopted:

- `auto-wait` for browser URL validity instead of immediate reads
- foreground process validation before each critical step
- invalid route circuit-breaker and short backoff
- hotspot profiles for different WeChat article layouts
- hard URL validation before `url/ingest`
- OCR only after URL paths are exhausted

## 2. Research Quality: Chosen Direction

Current direction is based on a multi-stage pipeline:

1. Query scope router
2. Multi-source retrieval
3. Retrieval evaluator
4. Theme convergence
5. Entity graph normalization
6. Cross-source contact enrichment
7. Structured report generation
8. Action-card synthesis

Key ideas adopted:

- Retrieval quality should be measured, not assumed.
- Theme-mismatched sources must be suppressed early.
- Entity outputs should be normalized into a graph so the report stops repeating slightly different names.
- Contact extraction must be entity-aware, so company-specific official/public contacts are ranked ahead of generic site entries.
- If hard evidence is weak, fallback should still output dense, scoped, role-based guidance rather than empty boilerplate.

## 3. Next Iterations

### WeChat URL-first

- Add consecutive wrong-front-process blacklisting
- Add browser URL polling windows per browser
- Add article-page hotspot profiles with per-device presets
- Add live route quality dashboard:
  - direct URL
  - share/copy URL
  - resolved URL
  - OCR fallback

### Research

- Raise official-source ratio in procurement/policy themes
- Add per-entity contact page re-ranking
- Add stronger entity alias clustering
- Add contact-type labeling:
  - official website
  - procurement contact
  - investor relations
  - public service hotline
- Add compare-matrix evidence traceability by entity

## 4. External References

- Playwright actionability / auto-wait:
  - https://playwright.dev/docs/actionability
- GraphRAG:
  - https://github.com/microsoft/graphrag
- CRAG:
  - https://arxiv.org/abs/2401.15884
- RAPTOR:
  - https://arxiv.org/abs/2401.18059
- STORM:
  - https://github.com/stanford-oval/storm
- Browser-use:
  - https://github.com/browser-use/browser-use

## 5. Product Constraints

- No attempt should be made to bypass paid walls or unauthorized login barriers.
- Public contact channels must remain public and business-facing.
- When exact company evidence is weak, the system should degrade to dense, scoped strategic guidance instead of fabricating specifics.
