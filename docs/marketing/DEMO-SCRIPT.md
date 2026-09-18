# Anti-FOMO 30-second Demo Script

This script follows the WindComic/HyperFrames pattern `Hook → Value → Mechanism → Proof → CTA`. Use real, sanitized UI captures where available. If a frame is conceptual, label it `planned` or `demo`; do not add fake customer names, fake metrics, or hidden production chrome.

| Time | Frame | Voiceover / subtitle | Required proof |
| --- | --- | --- | --- |
| 0–3s | Hook: noisy sources | “收藏很多，不代表判断更快。” | Web/WeChat/file source labels only |
| 3–7s | Intake and health | “先让来源进入可恢复队列，失败和过期都留在视野里。” | Actual ready/failed/stale states or clearly marked fixture |
| 7–12s | Evidence lens | “关键判断回到来源版本、引用和新鲜度。” | Source revision, digest and HOLD reason |
| 12–16s | Compare | “变化可见，争议点也可见。” | Real compare/field diff surface |
| 16–22s | Architecture | “研究继续推进成架构层、风险、客户问题和验证动作。” | Actual workbench/blueprint surface |
| 22–27s | Human review | “需要写入或交付时，先审阅、再批准。” | Review state, acceptance/rejection, audit receipt |
| 27–30s | CTA | “Anti-FOMO：Collect / Research / Compare / Act。” | Repo URL, Quick Start, contribution link |

## Rendering guardrails

- 15–30s, silent GIF plus narrated MP4; GIF target ≤ 6 MB, MP4 target ≤ 20 MB.
- 1920×1080 master, 1080×1920 vertical cutdown, 760×309 GIF preview (the source loop is intentionally wide).
- Use local fonts and deterministic timing; no `Date.now()`, `Math.random()` or network-only assets.
- Animate `transform` and `opacity`; keep subtitles inside the bottom 17% safe area.
- Record viewport, source mode, frame hashes and `production_claim=false` in an asset manifest.
