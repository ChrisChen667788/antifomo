# Marketing render validation

Validated on 2026-09-22. The exact rendering timestamp and content hashes are in `manifest.json`.

- HyperFrames 0.8.60 `check`: no lint/runtime warnings or errors; zero layout findings across nine samples; 55 / 55 text contrast checks passed.
- Six composition files: one host plus five independently seekable three-second scenes. Midpoint snapshots and the final encoded contact sheet were visually inspected: no cropped headline, content overlap, missing screenshot or obscured source label.
- Fonts: initial automatic font loading was replaced by four bundled licensed fonts. The final composition has no remote font URL or OS-specific font path.
- MP4: 1920 × 1080, H.264, 450 frames, 30 fps, 15.000 seconds; no audio stream. GIF: 760 × 428, 120 frames, 8 fps target (GIF time quantization gives approximately 15.01 seconds). Actual bytes and ffprobe records are retained in the manifest.
- Poster: 1920 × 1080. Social card: 1200 × 630. Review contact sheet: 1920 × 720, sampled from the final MP4 at scene midpoints and near its end.
- Source and rendered-output SHA-256 values were compared with files on disk after Studio assigned its editor IDs. Studio can modify the source when a user edits it; rerun the rendering command after edits to regenerate truthful hashes.
- The animation-map helper was reviewed. It enumerates registered child timelines recursively and again through the host, yielding duplicate entries (136 reported entries for 46 authored tweens) and heuristic collision/pace flags. Inspection of the source and rendered frames confirmed unique scene-prefixed targets and one paused timeline per composition. This is a reviewed diagnostic, not a zero-warning motion benchmark.
- Palette, typography, corners, spacing and shadow were checked against `videos/anti-fomo-promo/frame.md`. Screenshot pixels intentionally retain the historical product palette.

## Evidence limitation

This is a historical demo screenshot montage using v1.9.1 captures from the 2026-07-13 screenshot manifest. It does not demonstrate a live task, latest UI, external-service integration, customer outcome, performance SLA or production acceptance. The date this video was rendered does not update the screenshot capture date.

## Rebuild

Run `npm run marketing:overview` from the repository root. The command runs the composition checks, renders the MP4, derives all preview assets and replaces the output manifest after successful duration/size-budget checks. The checked-in source uses HyperFrames 0.8.60; the CLI/browser may be downloaded on the first run. Byte-identical encoding across different systems is not promised.
