# WP-28: Touch does not trigger prefetch

**Status:** Suggestion · **Priority:** P1 · **Depends on:** WP-25

## User task it protects

*Find relevant examples.* Scrolling through a move list on a phone should cost only the data for the moves the learner
opens, not for every row a finger passes over.

## Basis

**Observed problem**
- **Prefetch listens for `pointerover`, which touch also sends.** `frame-data.html:980` prefetches the move under any
  `pointerover` on a `tr[data-m]` row while the dock is open. Touch browsers send `pointerover` when a finger lands on
  an element, so every scroll gesture that starts on a row prefetches that row's move.
- **What a prefetch downloads.** For 3D games, the animation file, the weapon model (up to 670 KB) and possibly a class
  file (`frame-data/viewer3d.js:408-411`). For Super Smash Bros. Ultimate, the whole animated clip (median about
  69 KB, up to about 425 KB); the clip viewer only warms the HTTP cache (`frame-data/clipviewer.js:144`).
- **Desktop measured it.** Sweeping the pointer over 50 rows downloaded 3,780 KB in Super Smash Bros. Ultimate and
  398 KB in Elden Ring ([baseline](../../reports/performance-2026-10/baseline.md), section 5). On a phone this would
  be cellular data, and the warm-up rarely helps, because a finger that scrolls is not about to tap that row.
- **No data-saving signal is read.** Nothing checks `navigator.connection.saveData` or the `Save-Data` preference.

**Assumptions**
- On touch, a tap opens the move quickly enough without a prefetch (WP-25 measures a tap-to-first-frame time to
  check this).

## Proposed scope

1. Prefetch only when `e.pointerType` is `mouse` or `pen`, not `touch`.
2. Skip prefetching entirely when `navigator.connection?.saveData` is true.
3. Optionally, on touch, prefetch the neighbouring moves after a tap (the moves Down and Up would open), which helps
   stepping without fetching rows the learner only scrolled past. This overlaps WP-16; do it there if WP-16 is adopted.

## Out of scope

- Changing desktop hover prefetch.
- A general data-saver mode.

## Open questions

- None beyond the overlap with WP-16.

## Metric

- Emulated phone, WP-25: touch-scroll 50 rows of Super Smash Bros. Ultimate (Kazuya) and Elden Ring; baseline bytes
  and requests → no prefetch requests.
- Desktop, WP-12 hover sweep: unchanged.
- Tap to first frame on an emulated phone: no worse than baseline.

## Done when

- Touch scrolling a move list on a phone sends no prefetch requests, and desktop hover prefetch still works.
