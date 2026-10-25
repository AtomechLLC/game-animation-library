# WP-12: Measure before changing

**Status:** Done (2026-10-25) · **Priority:** P0 (first) · **Depends on:** none

**Result:** [Performance baseline, 2026-10-25](../../reports/performance-2026-10/baseline.md)

## User task it protects

All of them. Without a baseline, no other performance package can show that it helped learners rather than only
changed code, which is what `CLAUDE.md` asks: "Distinguish working functionality from demonstrated improvements".

## Basis

**Observed problem**
- The audit measured file sizes, but no browser or server profile exists. Costs like "the 3D viewer renders while
  paused" or "a search keystroke rebuilds 330 cards" are reasoned from the code, not timed.
- The code has no `performance.mark` calls and no record of load or interaction timings.

**Assumptions**
- Desktop Chrome with Lighthouse and the DevTools Performance panel is enough for a first baseline. A throttled run
  (Fast 3G network, 4× CPU slowdown) stands in for a student laptop on school Wi-Fi.

## Proposed scope

1. A short script or checklist (`docs/reports/performance-2026-10/baseline.md`) that records, for the commit
   measured:
   - **Cold and repeat load** of `/` (Action Atlas), `/frame-data.html` (Move Explorer, Elden Ring default) and
     `/trends.html`, on GitHub Pages and on the Node host: bytes transferred, request count, Largest Contentful
     Paint, Total Blocking Time, and for Move Explorer the time to the first frame in the 3D viewer.
   - **Interactions:** typing a ten-character search in the Action Atlas; picking an Elden Ring class; dragging the
     startup slider; holding Down for two seconds in the Moveset Inspector. Record long tasks and Interaction to
     Next Paint.
   - **Idle cost:** frames rendered per second and CPU use while the 3D viewer is paused, folded, and scrolled off
     screen.
   - **Memory:** JavaScript heap and GPU memory after 20 Elden Ring weapons, after 10 Super Smash Bros. Ultimate
     clips, after opening the Hollow Knight `nkg.attack.firebats` sheet, and after five game switches.
   - **Action Atlas scroll:** bytes transferred after scrolling the whole card grid.
   - **Node host:** time of the first `GET /` after a restart; event-loop delay during 100 votes.
   - **Hosting:** Pages artifact size and workflow run time; `git count-objects -vH`.
2. Optional `performance.mark` / `measure` calls around `renderAll`, `renderTable`, `fit` and `show` in Move
   Explorer and `render` in the Action Atlas, behind a `?perf` flag, so later packages reuse the same numbers.

## Out of scope

- Fixing anything. This package only measures.
- Automated performance tests in continuous integration (could follow if the manual baseline proves useful).

## Open questions

- Which host do students and classes mostly use: GitHub Pages or the Node host? This decides which numbers matter.
- Should the baseline include a mid-range phone, or stay desktop-only for now?

## Metric

This package produces the metrics; there is no target.

## Done when

- `docs/reports/performance-2026-10/baseline.md` lists every measurement above with the commit, browser version,
  machine and throttling used, and the steps to repeat it.
- Each later package can cite its baseline numbers from that report.

## Implementation record (as of 2026-10-25)

**Implemented**
- `tools/perf/baseline.mjs` drives an installed Chrome over the DevTools protocol (Node 22+, no dependencies). It
  measures page loads (cold and repeat, unthrottled and throttled), the Action Atlas full scroll, the four
  interactions at 1× and 4× CPU, the idle cost of each viewer kind (3D, sprite sheets, clips) when playing, paused,
  folded, hidden and off screen, hover prefetch over 50 rows, the four memory sequences, and the hosting and
  repository sizes. It records which Pages deployment it measured and flags a redeploy during the run. It writes
  one JSON file.
- Scope item 2 (timing page functions) is done from the script instead of the app code. The script wraps
  `renderAll`, `renderTable`, `preview`, `stepMove`, `dock`, the viewer's `show` and the Action Atlas's `render`
  in the page, so the apps stay unchanged.
- The report and raw data are in `docs/reports/performance-2026-10/`.

**Changed from the scope**
- **Node host measurements dropped.** GitHub Pages is the production host: the workflow deploys every push to
  `main`, and `LIBRARY_API_URL` is not set. This answers the first open question; the baseline report notes what it
  means for WP-13 and WP-22.
- **No Lighthouse.** The same metrics (paint timings, blocking time, event timings) are collected directly, so no
  package has to be installed.
- **Desktop only,** answering the second open question for now.


