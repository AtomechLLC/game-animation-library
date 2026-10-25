# WP-03: Elden Ring viewport and inspector

**Status:** In progress (mostly implemented) · **Priority:** P1 · **Depends on:** WP-06 (so the inspector does not present misleading
fields)

## User task and intended outcome

*Observe deliberately* and *compare approaches.* A learner studying one move sees the animation, the hitboxes and
the timing phases together, frame by frame, with the numbers and context beside them, on one screen.

## Basis

**Stated goal**
- Xelnath wants interactive references that replace hard-to-use recordings, so students and instructors can
  examine the moments that matter (`CLAUDE.md`).

**Observed problems** (inventory §6)
- **Timing is split across three surfaces.** The table shows some cancels. The details sheet (`openMove`,
  `frame-data.html:459`) shows all cancels, damage level and stamina. The dock (`preview`, `frame-data.html:517`;
  `frame-data/viewer3d.js`) shows hitboxes and the strip but not the numbers.
- **The 3D view does not draw timing windows.** The viewer does not draw cancel, armor or i-frame windows; they
  appear only on the scrub strip and in HUD text (inventory §3.4).
- **Move identity and its atlas entry are elsewhere.** The move id sits in the sheet footer, and the atlas entry a
  move illustrates is not shown at all (see WP-04).

**Already available** (inventory §3.4)
- The viewer plays, pauses, steps one frame at a time, scrubs, runs at 1×, ½×, ¼× and 0.1×, toggles hitboxes and
  ghost hitboxes, and toggles root motion.

**Assumptions to test**
- The unit of study is a *move* (an animation with timing), and the atlas entry is context around it (inventory §7).
- A phase timeline directly under the viewport keeps observation and numbers in sync better than a separate table.

## Proposed scope

1. **Viewport first.** Show the animation and hitboxes, with the phase timeline directly under them: startup,
   active, recovery, dodge and attack cancels, hyper armor. The current frame and phase are always visible.
2. **Inspector beside the viewport.** Gather in one panel:
   - **Identity:** class, weapon, type, grip, plain name, move id.
   - **Timing numbers:** startup, active windows, recovery, every cancel.
   - **First-hit damage:** type, motion value, damage level, stamina. Label clearly that it covers the first hit
     only.
   - **Context:** the linked atlas entry (WP-04), Frame Data Explorer link, weapons that use the move.
3. **Compare slot (optional within this package).** Pin a second move to compare timing side by side, for example
   two weapons' running heavies.

## Out of scope

- Hurtboxes (not in the data).
- Other games' viewers (the dock is shared, so keep changes compatible with them, but don't redesign them).

## Open questions

- One page, or a mode of the existing Frame Data tab?
- How should skill hitboxes without shapes (1,273 of 6,609 hits, judge ≥ 1000) be shown honestly?

## Done when

- For one move, every item in "Proposed scope 1–2" is visible without opening another surface.
- Stepping frames updates the timeline marker, the phase label and the hitbox together.
- Verified on at least: a multi-hit move, a hyper-armor move, a jumping move (no recovery data), a two-handed
  colossal weapon heavy.

## Evidence to capture

- `after/er-viewport-inspector.png` at a mid-active frame, and the same move in the before state (dock and sheet
  screenshots).

## Implementation record (as of 2026-10-25)

Line numbers refer to commit `e67c341`. Most of this landed in PR #62
(branch `ux/elden-ring-viewport-inspector`).

**Implemented**
1. **Phase timeline under the viewport.** The scrubber already showed the phase strip. Cancel windows were added as
   lines inside it, with a colour key (f4eecf2, PR #63; 9a304fe, PR #64; `cancelLanes`, `frame-data.html:625-630`).
   The current frame and phase are always visible in the viewer's heads-up text (`frameState`,
   `frame-data.html:722-725`) and in the inspector (`inspFrame`, `frame-data.html:754-764`).
2. **Inspector beside the viewport** (ec152a6, PR #62; `renderInsp`, `frame-data.html:735-753`):
   - Identity: class › type · grip · weapon · move id.
   - Timing: startup, active, recovery, hyper armor, and every cancel, colour-coded and explained (99b7eab, PR #71).
   - Damage labelled "First hit only" (`frame-data.html:750`).
   - "Used by" weapon icons and the Frame Data Explorer link (`frame-data.html:751-752`).
   - Stepping updates the frame number, phase, highlighted rows and open cancels together. Viewer stepping:
     arrow keys (7ca2e72), Space (7787c88), one-second and first/last jumps (c457a61).

**Not implemented**
- The plain move name in the inspector.
- The linked atlas entry ("Illustrates", depends on WP-04).
- Timing windows drawn in the 3D view itself (they appear only on the strip and in heads-up text).
- The optional compare slot.

**Not verified:** there is no record of the four verification moves in "Done when" (multi-hit, hyper armor,
jumping, two-handed colossal heavy).
