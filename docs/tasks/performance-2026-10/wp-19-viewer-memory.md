# WP-19: Bounded memory in the viewers

**Status:** Suggestion · **Priority:** P1 · **Depends on:** WP-12

## User task it protects

*Compare approaches.* Comparing means browsing many moves, weapons and games in one sitting. Memory should stay
flat, so the tab never slows down, reloads or shows blank images after a long study session.

## Basis

**Observed problem**
- **3D caches are never emptied.** `frame-data/viewer3d.js:10-11` keeps every loaded model, animation and class file
  in a module-level `cache` for the whole session, across games. Elden Ring alone has 451 weapon models and 3,990
  animation files.
- **Nothing is disposed on the GPU.** Swapping weapons removes the old clone without disposing it, and `dispose()`
  (`viewer3d.js:395-398`) frees the renderer and helper shapes but not the models' geometry, materials and textures,
  and does not call `renderer.forceContextLoss()`. Switching games repeatedly can pile up WebGL contexts (browsers
  cap them at about 16). On a game switch the new viewer starts before the old `dispose()` resolves.
- **Clip decoding is all-at-once and large.** `frame-data/clipviewer.js:27-39` decodes every frame of a clip before
  showing the first one. `ROBGyroEnd` (363×280, 221 frames) is about 90 MB of decoded bitmaps; a median clip about
  16 MB. The cache keeps six clips by count, not by size, so 100–500 MB is reachable.
- **Sprite sheets are decoded whole and kept forever.** `frame-data/sprites2d.js:6` caches every decoded sheet
  without eviction. The Hollow Knight `nkg.attack.firebats.webp` sheet is 3708×9240 px (about 137 MB decoded); the
  Street Fighter III `gill.super.034.webp` sheet is 3840×4480 px (about 69 MB). Hover prefetch decodes more.

**Assumptions**
- A small cache (the current move, its neighbours, and recently used weapons) keeps stepping fast (WP-16) while
  bounding memory.

## Proposed scope

1. Least-recently-used limits for the 3D model and animation caches, disposing geometry, materials and textures of
   evicted models. `forceContextLoss()` in `dispose()`, and wait for the old viewer to dispose before a new one starts
   (or reuse one renderer across games).
2. Clip viewer: show frame 1 as soon as it decodes and decode the rest progressively; limit the cache by decoded
   bytes instead of count.
3. Sprite viewer: least-recently-used limit by decoded bytes, `img.decode()` before drawing.

## Out of scope

- Re-exporting sprite sheets into smaller tiles (a media change; see open questions).

## Open questions

- Should `tools/frame_data/export_baston_sprites.py` and the Hollow Knight exporter cap sheets at 4096 px or trim
  cells? That changes generated media and needs its own decision.

## Metric

- JavaScript heap and GPU memory after the WP-12 sequences (20 weapons, 10 clips, the large sheet, five game
  switches): baseline → flat within a set budget (for example under 300 MB total).
- Time to the first frame of `ROBGyroEnd`: baseline → the time to decode one frame.
- WebGL context warnings after ten game switches: none.

## Done when

- The WP-12 memory sequences stay within the budget, and stepping back to a recent move is still instant.
