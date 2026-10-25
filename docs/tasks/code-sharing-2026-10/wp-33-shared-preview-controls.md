# WP-33: One set of preview controls

**Status:** Suggestion · **Priority:** P1 · **Depends on:** none

## User task it protects

*Observe deliberately* and *Compare approaches.* A student steps through an Elden Ring move in the 3D preview, then a
Street Fighter III move in the hitbox clip preview. Play, step a frame, scrub, the keys and a shared link should work
the same in both, so attention stays on the animation.

## Basis

**Observed problem**
- Move Explorer docks one of three preview modules, depending on the game: `frame-data/viewer3d.js` (3D models),
  `frame-data/sprites2d.js` (sprite sheets) and `frame-data/clipviewer.js` (recorded hitbox clips). The controls
  around the picture are copied into all three: 31 identical lines in all three modules, 6 more in the 3D and sprite
  previews ([report, section 3](../../reports/duplicated-app-code.md#3-preview-controls-in-the-three-preview-modules)).

| Part | viewer3d.js | sprites2d.js | clipviewer.js |
|---|---|---|---|
| Play, ±1 frame buttons and scrub bar markup | 86 | 33 | 13 |
| Key help line (`.v3d-keys`) | 92 | 39 | 19 |
| `setPlaying` | 255 | 87 | 66 |
| `go` (move to a frame) | 256 | 78 | 58 |
| `onKey` (Space, `,` `.`, arrows, Ctrl and Shift jumps) | 263 | 94 | 72 |
| Link state: `toggles`, `view`, `setView` | 381–384 | 130–133 | 115–118 |

- When arrow keys were added for stepping frames (`7ca2e72`), the same lines had to go into all three modules. That
  time none was missed; the next change (keys, help line, link format) has to be repeated the same way.
- Drift so far is one line: the 3D preview's `onKey` leaves Numpad `.` to its camera ("Fit to view").

**Assumptions**
- The three modules already share one interface toward the page (`createViewer` → `show`, `prefetch`, `dispose`,
  documented in `frame-data/README.md`; `view` and `setView` were added later and are not documented there), so the
  controls can move without the page changing.
- What differs between previews is drawing and loading, not the transport: frame count, frames per second and how to
  draw frame *f*.

## Proposed scope

1. A module `frame-data/transport.js`, beside `speed.js` and in its style, that owns:
   - the transport markup (play, ±1 frame, scrub bar, speed menu via `speed.js`, key help line);
   - playback state and the animation tick, `setPlaying` and `go`;
   - the keyboard handler, with a hook for a preview's own extra keys (the 3D preview's Numpad `.`);
   - the link state (`view`, `setView`, the overlay toggles).
2. Each preview module keeps only what is its own: loading, drawing a frame, overlays, and for the 3D preview the
   camera. It hands the transport a frame count, frames per second and a draw callback.
3. Bump `?v=` on the three modules and on `frame-data.html`'s imports.
4. Update `frame-data/README.md`, which describes the preview interface.

## Out of scope

- Any new control or key, or a change to what an existing one does.
- Merging the three previews into one module: their loading and drawing really differ.
- The ruler and the Moveset Inspector keys in `frame-data.html` (the ruler is already shared).

## Open questions

- Should the clip preview's link state (it also stores which clip, `clipviewer.js:116`) become a general "extra view
  fields" hook, or stay in the clip module?
- Is a separate `transport.js` right, or should the controls join `speed.js` as one "controls" module?

## Metric

- Identical transport lines across the three modules: 31 (+6) → 0.
- Places to edit to change frame stepping keys: 3 → 1.

## Done when

- The three modules import the transport and no longer define `onKey`, `setPlaying`, `go`, `view` or `setView`
  themselves.
- In Move Explorer, for one game of each type (Elden Ring 3D, a sprite game, Street Fighter III clips): play, pause,
  ±1 frame, scrub, Space, `,` `.`, Left/Right with focus, Ctrl and Shift jumps, speed, and a shared link restoring
  frame, speed and overlays all behave as before. Numpad `.` still fits the 3D move to the view.
- No console errors.
