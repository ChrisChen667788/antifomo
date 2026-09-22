# Anti-FOMO · evidence editorial

Concept: a solution architect moves from a crowded collection to a useful next customer conversation. The screenshots provide product context; the typography gives the viewer a clear reason to care.

## Palette

- Canvas: `#f1f4ef` (mineral white)
- Main ink: `#142b30`
- Accent: `#126e65` (petrol teal)
- Secondary ink: `#425f62`
- Hairline: `#cad8cf`
- Window bar: `#e2eae2`
- Window canvas: `#f7f9f4`
- Shadow: `#142b3014`

The product screenshots retain their original pixels and palette.

## Typography

- Display/body: locally bundled Montserrat, aliased as `AntiFOMO Display`, weights 900 / 400.
- Source/route labels: locally bundled IBM Plex Mono, aliased as `AntiFOMO Mono`, weights 700 / 400.
- 72 px display, 30 px body, 23 px scene label. The 17–19 px metadata is intentionally secondary on a 1920 × 1080 canvas.
- Font files and OFL notices live in `assets/fonts/`; no operating-system font paths or runtime font downloads.

## Composition

The left column is the user's job, the right column is an authentic historical UI capture. The masthead and provenance footer anchor the edges. A three-pixel progress rule communicates elapsed video time, never product completion or a business metric.

Main horizontal gutters: 96 px. Split gap: 42 px. Body spacing: 32–48 px. Screenshot corners: 14 px; depth is a single subtle shadow.

## Motion and restraint

- Sequential, seeking-safe timeline; five three-second shots.
- Headline arrival uses `waterfall-entry` (explicit from/to positions, short stagger); the supporting copy resolves after the headline.
- The screenshot uses `coordinate-target-zoom`: separate scale and counter-translation wrappers, restrained to 1.035 × within a fixed crop. The crop is intentional.
- Progress line uses the `stat-bars-and-fills` scaleX mechanism to show video time only.
- Deliberate silence: README autoplay must communicate without narration or music.
- Hard cuts preserve the aligned screenshot frame; no effects library, decorative metric, invented endorsement, mock cursor, or simulated click.

## Evidence boundary

Every scene says `Demo UI · historical captures · v1.9.1 / 2026-07-13`. Source date comes from the screenshot manifest, not this render's date. The overview is a designed montage of existing still images, not a recording of an end-to-end task or a claim that these are the latest screens.
