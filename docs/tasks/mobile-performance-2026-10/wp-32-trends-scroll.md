# WP-32: Smooth scrolling on Trends

**Status:** Suggestion · **Priority:** P2 · **Depends on:** WP-25

## User task it protects

*Compare approaches.* Trends compares games across many charts; on a phone, the learner reads it by scrolling, and
scrolling should not stutter.

## Basis

**Observed problem**
- **Every scroll event schedules a layout-heavy update.** `trends.html:570` adds
  `requestAnimationFrame(spy)` for each `scroll` event, without coalescing, so several `spy` calls can run in one
  frame. `spy` (`trends.html:560-567`):
  - reads the header height and `getBoundingClientRect()` of every `.card`;
  - writes `aria-pressed` on every key;
  - then `placePlayhead()` reads `offsetLeft` again and may start a smooth `scrollTo` on the key row
    (`trends.html:574-580`).
  The read, write, read order forces layout again inside the same frame. Touch scrolling on a phone fires many scroll
  events, and a slower CPU makes each forced layout cost more.
- **The data is large for a phone.** Trends fetches about 5.75 MB of game JSON (about 465 KB compressed), including
  the 2.57 MB Super Smash Bros. Ultimate file, and parses all of it. WP-21 already proposes summary data; this package
  does not repeat it.

**Assumptions**
- The scroll cost is small on desktop (no long tasks were recorded while scrolling there) and may only matter on a
  slower phone. WP-25's Trends scroll run decides whether this package is worth doing.

## Proposed scope

1. Coalesce: schedule at most one `spy` per animation frame.
2. Find the active section with an `IntersectionObserver` on the cards instead of measuring every card on each frame.
3. Do all reads before writes in `spy` and `placePlayhead`, and skip the key-row `scrollTo` while the user is
   scrolling the page.

## Out of scope

- The Trends data size (WP-21).
- The chart tooltip on touch (usability, listed in the round's README).

## Open questions

- None; this package should be dropped if WP-25 shows no long tasks or forced layouts while scrolling Trends on an
  emulated phone.

## Metric

- Emulated phone at 4× and 6× CPU, WP-25 Trends scroll: long tasks, forced layouts and dropped frames; baseline →
  no long tasks and no forced layouts from `spy`.

## Done when

- The active key still follows the section in view, and scrolling Trends on an emulated phone shows no long tasks
  from `spy`.
