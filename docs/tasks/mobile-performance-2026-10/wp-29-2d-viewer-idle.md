# WP-29: 2D and clip viewers sleep when idle

**Status:** Suggestion · **Priority:** P1 · **Depends on:** WP-25

## User task it protects

*Use examples in teaching* and *Observe deliberately.* A phone or tablet with a move paused on screen, or a Move
Explorer tab left open, should not drain the battery.

## Basis

**Observed problem**
- **The sprite and clip viewers never stop their animation loop.** Both schedule `requestAnimationFrame` on every
  frame, whether playing, paused, folded or scrolled away (`frame-data/sprites2d.js:140-146`,
  `frame-data/clipviewer.js:126-132`). Neither has an `IntersectionObserver` or a `visibilitychange` handler.
  They serve three of the seven games: Street Fighter III, Hollow Knight and Ninja Gaiden Black (sprite sheets) and
  Super Smash Bros. Ultimate (clips).
- **On desktop this was cheap.** Paused, both loops cost about as much as the measuring script itself, 20–30 ms of
  main thread per second ([baseline](../../reports/performance-2026-10/baseline.md), section 4). On a phone, waking the
  CPU 60 or 120 times a second still keeps it out of its lowest power state.
- **iOS gets a clip that cannot be paused.** iOS browsers have no `ImageDecoder`, so the clip viewer falls back to an
  `<img>` that plays the animated WebP forever with all controls disabled (`clipviewer.js:98-103`). It decodes
  continuously, even off screen, and frame stepping is lost. The message names "Chrome, Edge, Firefox", which an
  iPhone user cannot switch to, because every iOS browser uses WebKit.
- **The 3D viewer already does this right.** Since WP-15 it renders only when its picture changes and stops when off
  screen (`frame-data/viewer3d.js:148`).

**Assumptions**
- Battery cost on phones is real but small for one tab; WP-25 checks it before this package is prioritised higher.

## Proposed scope

1. Run the 2D and clip viewer loops only while playing and on screen, using the same pattern as the 3D viewer
   (request a frame when something changes; an `IntersectionObserver` on the stage).
2. iOS clip fallback: hide the clip `<img>` while it is off screen or the panel is folded, so it stops decoding; and
   reword the message so it does not suggest browsers an iPhone cannot use (for example "Frame stepping is not
   available in this browser").

## Out of scope

- Frame stepping for clips on iOS (it would need a different decoder or pre-extracted frames; a separate decision).

## Open questions

- Is frame stepping for Super Smash Bros. Ultimate on iOS worth a separate package, given that iPhones and iPads are
  common in classes?

## Metric

- Emulated phone and desktop, WP-25 and WP-12 idle scenarios: animation frames per second while paused, folded and
  off screen; baseline (about 60 on a 60 Hz display) → 0.
- Main thread busy per second, same states: baseline → the instrumentation floor.

## Done when

- Paused, folded, hidden and off-screen sprite and clip viewers schedule no animation frames, and playing, stepping
  and scrubbing behave as before on desktop.
- On a real iPhone, the clip fallback stops animating when scrolled away, and its message names no other browsers.
