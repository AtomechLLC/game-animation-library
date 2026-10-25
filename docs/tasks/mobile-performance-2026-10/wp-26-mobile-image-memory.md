# WP-26: Sprite sheets and clips within a phone's memory

**Status:** Suggestion · **Priority:** P0 · **Depends on:** WP-25, WP-19 (soft)

## User task it protects

*Observe deliberately* and *Compare approaches.* A learner stepping through Hollow Knight or Super Smash Bros.
Ultimate moves on a phone should not see the tab reload and lose their place.

## Basis

**Observed problem**
- **Sprite sheets are decoded whole and never released.** `frame-data/sprites2d.js:6-7` keeps every loaded file in a
  module-level `cache`, and `loadSheet` (`sprites2d.js:114`) puts each sheet image there. On desktop, WP-19 measured
  about 140 MB of extra GPU memory for one sheet.
- **Some sheets are larger than iOS allows.** Read from the WebP headers under `frame-data/sprites/`:

  | Game | Sheets | Over 16.7 megapixels (iOS image budget) | A side over 4,096 px | Largest decoded |
  |---|---|---|---|---|
  | Hollow Knight | 90 | 7 | 7 | about 130 MiB (`nkg.attack.firebats`, 3708 × 9240) |
  | Ninja Gaiden Black | 24 | 2 | 10 | about 75 MiB |
  | Street Fighter III: 3rd Strike | 1,298 | 1 | 2 | about 65 MiB |

  iOS Safari limits a tab's memory far below a desktop's, and a 9,240 px tall image can also exceed a phone GPU's
  largest texture size, so drawing from it may fail or be downscaled.
- **The clip viewer decodes every frame up front and keeps six clips.** `frame-data/clipviewer.js:30-36` decodes
  each frame of a clip into an `ImageBitmap` (336 × 280, about 376 KB each); the cache evicts by count at six clips
  (`clipviewer.js:42-47`). Median clip about 15 MB, longest about 83 MB, so six clips can reach 100–500 MB. On
  desktop, 10 clips decoded 171 MB of bitmaps. This affects Android; iOS uses the fallback in WP-29.
- **The 2D canvas uses the full pixel ratio.** `sprites2d.js:49` sizes the canvas at `devicePixelRatio` (3 on most
  phones) with no cap, unlike the 3D viewer's cap of 2. The canvas is small on phones, so this is minor.

**Assumptions**
- WP-19's least-recently-used caches fix the growth. What a phone needs on top is a smaller budget, chosen from the
  device, and a plan for sheets that are too large to decode at all.
- `navigator.deviceMemory` (Chromium only) and a small-screen or coarse-pointer check are good enough signals for the
  budget; iOS reports neither memory nor `deviceMemory`, so it gets the small budget by default on touch devices.

## Proposed scope

1. A memory budget for decoded images, shared by the sprite and clip viewers: for example about 300 MB on desktop and
   about 100 MB on phones and tablets. Implement on top of WP-19's byte-counted, least-recently-used caches; evicting
   a sheet drops its image so the browser can free it.
2. Clip viewer on phones: keep the current clip and one neighbour, and show the first frame as soon as it is decoded
   (WP-19 scope 2).
3. Cap the 2D canvas pixel ratio at 2, as the 3D viewer does.
4. Detect a sheet that is over the phone budget before loading it and show a short message in the viewer instead of
   risking a crash, until the open question below is decided.

## Out of scope

- Re-exporting sprite sheets (a media change; see open questions).
- Changing what the viewers show or how they are controlled.

## Open questions

- Should `tools/frame_data/export_baston_sprites.py` and the Hollow Knight and Ninja Gaiden Black exporters cap
  sheets at 4,096 px on a side, splitting larger moves across several sheets? That changes generated media and needs
  its own decision. It would remove the crash risk instead of guarding against it.
- Is a message on a too-large sheet acceptable for a phone, or should such moves be hidden from phone lists?

## Metric

- Real iPhone, from the WP-25 checklist: open the Hollow Knight `nkg.attack.firebats` move and nine more Hollow
  Knight moves; baseline (expected: reload or blank) → no reload.
- Emulated phone, WP-25 memory sequences: GPU process memory after 10 Smash clips and after the Hollow Knight sheet;
  baseline → within the phone budget.
- Desktop: the WP-12 memory sequences are no worse, and stepping back to a recent move is still instant.

## Done when

- Neither real phone reloads or shows a blank viewer during the WP-25 checklist.
- Desktop behaviour and WP-12 numbers are unchanged or better.
