# WP-27: Recover from a lost 3D context

**Status:** Suggestion · **Priority:** P0 · **Depends on:** WP-25

## User task it protects

*Use examples in teaching* and *Observe deliberately.* An instructor's tablet goes to sleep or switches apps during a
class; when they come back, the move they were showing should still be there.

## Basis

**Observed problem**
- **Nothing handles a lost WebGL context.** No `webglcontextlost` or `webglcontextrestored` listener exists in
  `frame-data.html` or `frame-data/*.js`. Mobile browsers, iOS Safari in particular, drop WebGL contexts when the
  browser is backgrounded or memory runs low. The 3D stage then stays blank or frozen, and only a page reload brings
  it back, which loses the current move, weapon and frame unless they are in the address.
- **Old contexts are not released on a game switch.** `frame-data.html:797` creates a new viewer for each game and
  disposes the old one asynchronously. `dispose()` (`frame-data/viewer3d.js:412-415`) calls `renderer.dispose()` but
  not `renderer.forceContextLoss()`, so the old context lives until garbage collection. On desktop, five game switches
  left six WebGL contexts alive ([baseline](../../reports/performance-2026-10/baseline.md), section 6). Browsers cap
  live contexts (about 16 in Chromium, fewer in Safari) and drop the oldest when over the cap, which could be the one
  on screen.

**Assumptions**
- The viewer already keeps enough state (current move, weapon, frame, camera) to rebuild the scene after a restore,
  because it can already show a move from scratch.

## Proposed scope

1. On `webglcontextlost`, call `preventDefault()` so the browser may restore the context, stop rendering, and show a
   short "Preview paused, restoring" state in the stage.
2. On `webglcontextrestored`, rebuild GPU resources and show the same move, weapon, frame and camera again. If the
   context is not restored within a few seconds, offer a "Reload preview" button that recreates only the viewer.
3. In `dispose()`, call `renderer.forceContextLoss()` after `renderer.dispose()`, and let the new viewer start only
   after the old one has disposed (or reuse one renderer across games, as WP-19 scope 1 suggests).

## Out of scope

- Keeping the 3D preview alive in the background.
- Any change to what the viewer shows.

## Open questions

- Should the move, weapon and frame always be in the address, so that even a full reload returns to the same place?
  (Some of it already is, through `history.replaceState`.)

## Metric

- Real iPhone and Android phone, WP-25 checklist: background the browser for one minute with the 3D viewer on screen
  and return; baseline (blank or frozen stage?) → the same move and frame are shown again.
- Desktop, forced with the `WEBGL_lose_context` extension: the stage recovers with the same move and frame.
- Live WebGL contexts after ten game switches: baseline (one per switch) → one or two.

## Done when

- Losing and restoring the context, forced on desktop and by backgrounding on both real phones, returns to the same
  move and frame without a page reload.
- Ten game switches leave no more than two WebGL contexts and no browser warning.
