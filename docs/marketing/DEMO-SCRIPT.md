# Anti-FOMO · 15-second product overview

A solution architect's journey: **collect a useful signal → build a view → compare changes → prepare the conversation → take a deliberate next step**. The structure borrows WindComic's value-first, source-backed marketing style.

[Watch the MP4](../assets/marketing/antifomo-overview.mp4) · [README GIF](../assets/marketing/antifomo-overview.gif) · [Poster](../assets/marketing/poster.png) · [Social card](../assets/marketing/social-card.png) · [Source project](../../videos/anti-fomo-promo/) · [Asset provenance](../assets/marketing/manifest.json)

| Time | On-screen headline | Product context | 中文表达 |
| --- | --- | --- | --- |
| 0–3 s | Too much saved. Too little decided. | Home signal dashboard | 收藏很多，判断却还没开始。 |
| 3–6 s | Build a view you can explain. | Inbox research workspace | 把问题推进成有依据、能解释的判断。 |
| 6–9 s | See the change. Keep the context. | Research compare workspace | 看清变化，也保留上下文。 |
| 9–12 s | Meet the customer with context. | Account intelligence | 带着背景和更好的问题去见客户。 |
| 12–15 s | Make your next move deliberate. | Focus session workspace; Quick Start → Issue → PR | 让下一步行动更有把握，从一个真实问题开始。 |

## What this asset proves

The video is an editable **historical demo screenshot montage**. Its five frozen source images are bound to the archived [v1.9.1 screenshot manifest](../../videos/anti-fomo-promo/assets/screenshot-manifest-v1.9.1.json), generated at `2026-07-13T12:34:05.482Z`; refreshing the current product gallery does not change this older montage. Every shot carries `Demo UI · historical captures · v1.9.1 / 2026-07-13`. The render timestamp is recorded separately in the asset manifest.

It is not a live recording of one completed workflow, a claim that the UI is current, proof of production acceptance, a customer success story, or a demonstration of the planned WorkBuddy features. The screenshots retain their original product data and display states; no mouse click, customer endorsement, or ROI metric has been fabricated.

The broader architecture, current evidence boundaries and future integration plan are documented separately. This short overview is meant to invite the viewer to try a real task, not substitute for acceptance testing.

## Reproduce or edit

From the repository root:

```sh
npm run marketing:overview
```

The command validates and renders the checked-in HyperFrames project, then derives the GIF and static cards with FFmpeg. It requires Node.js, npm, FFmpeg/ffprobe and the pinned HyperFrames `0.8.60` toolchain. A first run may download the CLI/browser; composition fonts, GSAP and screenshots are bundled locally. No render-time network source or machine-specific font path is required.

Edit `videos/anti-fomo-promo/compositions/*.html` for shot content/motion, `frame.md` for visual rules, and `index.html` for timing. Preview with `npm run dev` inside that directory.

Output contract: 15 s; 1920 × 1080 / 30 fps MP4; 760 × 428 / 8 fps GIF; 1920 × 1080 poster; 1200 × 630 social card. The GIF budget is 6 MiB and the MP4 budget is 20 MiB. Deliberate silence supports README autoplay.

The generated manifest records exact source and output hashes, dimensions, frame counts, rendering time and evidence flags. Deterministic seek behavior does not imply byte-identical MP4 output across OS/browser/encoder versions.
