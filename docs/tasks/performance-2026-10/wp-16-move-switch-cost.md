# WP-16: Fast move stepping

**Status:** Suggestion · **Priority:** P0 · **Depends on:** WP-12

## User task it protects

*Compare approaches* and *observe deliberately*. Stepping through a moveset with Up/Down or Left/Right in the
Moveset Inspector (PR #70, #75, #76) is how learners scan and compare moves. Each step should show the new move
immediately, also while a key is held.

## Basis

**Observed problem**
- **`fit()` poses the whole move on every switch.** `fit()` (`frame-data/viewer3d.js:273-299`) calls `pose(k)` for
  every frame of the move (line 278). Each `pose()` runs `scene.updateMatrixWorld(true)`, several
  `querySelector` calls, writes the frame number, state and scrub value, sets a CSS custom property, and calls the
  page's `inspFrame` (`frame-data.html:754-764`), which runs two `querySelectorAll` calls. A 150-frame move does
  about 150 rounds of DOM writes before its first frame shows. `show()` always calls `fit()`.
- **Each step searches all moves linearly.** `stepMove` (`frame-data.html:949-957`) rebuilds the row list from the
  DOM and calls `moveOf` per row; `moveOf` (`frame-data.html:765`) is `D.moves.find` over 3,865 Elden Ring moves.
  About 92 × 3,865 comparisons per key press. `openMove` and the hover handler use the same lookup.
- **`preview()` forces layout and writes history every step** (`frame-data.html` around lines 799-818): class
  toggles across all rows, then `offsetTop`/`clientHeight` reads (line 806), then `writeHash()` →
  `history.replaceState` (line 808). Chrome throttles `replaceState` after about 100 calls in 10 seconds.
- **Holding a key is not coalesced:** auto-repeat at about 30 Hz runs about 30 full switches a second.
- **Hover prefetch fires on every `pointerover`** (`frame-data.html:973`), which bubbles from every cell, and can
  download class JSON and weapon models for rows the learner only passes over.

**Assumptions**
- The fitted camera box for a move depends only on the animation and weapon, so it can be cached.

## Proposed scope

1. Split `pose()` into the skeleton pose and the interface update; skip the interface update while fitting. Cache
   the fit box per animation and weapon.
2. Build a `Map` from `class|id` to move once in `loadGame`; use it in `moveOf`, `openMove`, the hover handler and
   `stepMove`. Keep the navigable row list as an array instead of re-querying the DOM.
3. Coalesce previews to one per animation frame while a key is held; debounce `writeHash`.
4. Read layout before writing classes in `preview()`, or use `scrollIntoView({block: 'nearest'})`.
5. Hover prefetch: `pointerenter` per row or dedupe on the last row, with a short intent delay (about 150 ms).

## Out of scope

- Changing what a step shows or how keys behave.

## Open questions

- None known.

## Metric

- Time from Down key to the new move's first rendered frame (Elden Ring colossal weapon class): baseline from WP-12
  → under one frame of main-thread work beyond the model download.
- Long tasks while holding Down for two seconds: baseline → none over 50 ms.
- Bytes fetched while sweeping the pointer over 50 table rows: baseline → only rows rested on.

## Done when

- Holding Down steps smoothly through an Elden Ring class without long tasks, and the final move, camera fit, URL
  and inspector match the move reached.
- No `replaceState` throttling warning appears in the console.
