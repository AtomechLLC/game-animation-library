# WP-05: Teaching links to an exact moment

**Status:** In progress (scope implemented; "Done when" not verified) · **Priority:** P2 · **Depends on:** WP-03, WP-04

## User task and intended outcome

*Use examples in teaching.* An instructor can copy a link that opens the exact move, frame, speed and overlay
settings they want to discuss, and paste it into slides, Discord or homework.

## Basis

**Stated goal**
- Support instructors using examples in class, and make references easy to return to (`CLAUDE.md`).

**Observed problem**
- The hash stores browsing state only: game, family, class, weapon, types, grip, sort (`writeHash`,
  `frame-data.html:530`). It does not store the move, frame, speed, hitbox toggle or ghost toggle (see the viewer
  controls in `frame-data/viewer3d.js:62-65`).

**Assumption to test**
- Instructors share links more than screenshots when a link reliably opens the right moment.

## Proposed scope

1. Extend the hash with the move (`m`, from WP-04), frame (`fr`), speed (`sp`), hitboxes (`hb`) and ghost hitboxes
   (`gh`).
2. Add a "Copy link to this frame" button in the viewport.
3. Opening such a link loads paused on that frame, so the moment is visible immediately.

## Out of scope

- Annotations or drawing on frames (a possible later package).
- Accounts or saved collections.

## Open questions

- Should a link also be able to open a two-move comparison (if WP-03 adds one)?

## Done when

- A copied link opened in a fresh browser shows the same move, frame, speed and overlays, paused.
- Links without the new parameters still behave as today.

## Evidence to capture

- The copy-link control, and the result of opening a link in a new window.

## Implementation record (as of 2026-10-25)

**Implemented** (e7ca02e, PR #62)
- The link carries the move (`m`), frame (`fr`), speed (`sp`), clip index (`cl`) and overlay toggles as `show` and
  `hide` lists instead of separate keys.
- A "Copy link" button (`frame-data.html:450`; `copyLink`, `frame-data.html:846-854`).
- The link opens paused on the frame: `setView` pauses and then goes to the frame (`frame-data/viewer3d.js:372-377`).
  The same interface exists in `frame-data/sprites2d.js:131-148` and `frame-data/clipviewer.js:116-143`.
- Old links still work; only `m` triggers the new handling.

**Not verified:** the fresh-browser check in "Done when" has not been run.
