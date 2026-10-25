# WP-15: 3D viewer renders only when something changes

**Status:** Done (2026-10-25) · **Priority:** P0 · **Depends on:** WP-12

**Result:** [WP-15 before and after](../../reports/performance-2026-10/wp-15-render-on-demand.md)

**In-app check:** the render stats overlay (`` ` `` in the 3D view; `frame-data/renderstats.js`, described in
`frame-data/README.md`). It shows renders per second next to the playback state and whether the view is on screen.
Before this package, renders per second matched the loop rate whether the move was playing, paused, folded or
hidden. Now they read 0 whenever nothing changes.

## User task it protects

*Observe deliberately* and *use examples in teaching*. A learner or instructor often pauses on one frame and talks
over it. A paused move should cost nothing, so laptops on a projector stay cool and quiet and the rest of the page
stays responsive.

## Basis

**Observed problem**
- `tick` in `frame-data/viewer3d.js:379-386` calls `renderer.render(scene, camera)` on every animation frame,
  unconditionally. It keeps rendering:
  - while paused, and when `prefers-reduced-motion` starts it paused;
  - while the dock is folded (`.dock.min .study{display:none}`) or hidden;
  - while the viewer is scrolled off screen.
- The renderer uses `antialias: true` and a pixel ratio up to 2 (`viewer3d.js:97-98`), and the Elden Ring armor alone
  is 34 skinned draw calls with `frustumCulled = false`.
- The overlays on the viewer use `backdrop-filter: blur(6px)` (`frame-data.html` around lines 233-242). A blur over
  a canvas that changes every frame is recomposited every frame.
- The sprite and clip viewers' loops (`frame-data/sprites2d.js`, `frame-data/clipviewer.js`) also run forever,
  though they draw only while playing.

**Assumptions**
- Rendering on demand changes nothing the learner sees: every visible change already goes through `go()`, the
  navigation callbacks, a toggle, or a resize.

## Proposed scope

1. Render on demand in `viewer3d.js`: a `needsRender` flag set by `go()`, camera navigation, overlay toggles and
   resize; the loop renders only when the flag is set or the move is playing.
2. Stop the loop entirely when the viewer is not visible: an `IntersectionObserver` on the viewer, the dock's
   folded and hidden states, and `visibilitychange`. Resume on the next change.
3. The same stop-when-idle rule for the sprite and clip viewers' loops.
4. Check whether the `backdrop-filter` overlays still cost anything once the canvas is static; replace them with a
   solid translucent background only if they do.

## Out of scope

- Lower-quality rendering modes or a quality setting (the viewport is a previewer; keep it simple).
- Any visible change to the viewer.

## Open questions

- None known. If a hidden visual depends on continuous rendering (for example an eased camera), it needs the flag too.

## Metric

- Frames rendered per second while paused, folded, or scrolled off screen: about 60 → 0.
- CPU and GPU use over ten seconds paused on a move (DevTools Performance, WP-12 setup).

## Done when

- Paused, folded and off-screen viewers render nothing, and resume correctly on play, scrub, step, camera move,
  overlay toggle and resize.
- Verified on Elden Ring, No Rest for the Wicked (3D), Street Fighter III (sprites) and Super Smash Bros. Ultimate
  (clips).

## Implementation record (as of 2026-10-25)

**Implemented** (branch `perf/wp-15-render-on-demand`)
- **Scope 1, render on demand,** in `frame-data/viewer3d.js`:
  - `requestRender()` marks the picture stale and wakes the animation-frame loop for one render.
  - These call it: `go()` (play, scrub, frame keys, the overlay checkboxes, `setView`, `show`, Bounds), the grid
    toggle, resize, and starting playback.
  - Camera moves call it through a new `onChange` option of `createBlenderNavigation`
    (`frame-data/navigation3d.js`, from `place()` and `shift()`).
  - The loop renders only when the picture is stale, and keeps running only while a move plays on screen.
  - A side effect: while playing, it renders only when the pose changes, which is 15 renders/s at 0.5× instead of
    the display rate.
- **Scope 2, stop when not visible:**
  - An `IntersectionObserver` on the stage stops the loop when the view is off screen, folded or hidden, and
    renders again when the view comes back.
  - Hidden browser tabs already stop animation frames, so `visibilitychange` was not needed.
- **Outside changes:** `createViewer` now returns `requestRender` for code that changes the scene from outside.
  `tools/er_gifs/render.html` calls it after showing or hiding the grid and the weapons.
- **Cache versions:** `viewer3d.js?v=19` and `navigation3d.js?v=9`.

**Changed from the scope**
- **Scope 3 dropped.** The baseline showed that the sprite and clip viewers already stop drawing when paused (0
  frames/s); their remaining cost is at the measurement floor.
- **Scope 4 not needed.** With the canvas static, the `backdrop-filter` overlays have nothing to recomposite. The
  paused view's GPU-process CPU fell from about 350 to 25–30 ms/s with them in place.

**Result**
- Paused, folded, hidden and off screen: 160–200 → **0** renders/s.
- Playing at 0.5×: 228 → 15 renders/s.
- Details: [`wp-15-render-on-demand.md`](../../reports/performance-2026-10/wp-15-render-on-demand.md).
