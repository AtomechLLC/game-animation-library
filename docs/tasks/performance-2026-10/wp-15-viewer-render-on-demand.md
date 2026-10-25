# WP-15: 3D viewer renders only when something changes

**Status:** Suggestion · **Priority:** P0 · **Depends on:** WP-12

**In-app check:** the render stats overlay (`` ` `` in the 3D view; `frame-data/renderstats.js`, described in
`frame-data/README.md`). It shows renders per second next to the playback state and whether the view is on screen.
Before this package, renders per second match the loop rate whether the move is playing, paused, folded or hidden.

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
