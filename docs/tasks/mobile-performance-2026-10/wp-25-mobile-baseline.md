# WP-25: Measure on a phone first

**Status:** Suggestion · **Priority:** P0 (first) · **Depends on:** WP-12

## User task it protects

All of them. Like WP-12 for desktop, this package makes later mobile packages show that they helped, instead of only
changing code.

## Basis

**Observed problem**
- **The baseline script measures desktop only.** `tools/perf/baseline.mjs` starts Chrome with
  `--window-size=1440,900` (`baseline.mjs:34`) and sets `Emulation.setDeviceMetricsOverride` to 1440 × 900, device
  scale 1, `mobile: false` (`baseline.mjs:120`). Its throttled run uses Lighthouse's mobile network and 4× CPU on that
  desktop window.
- **The costs a phone hits depend on the phone's screen.** Pixel density (usually 3 on phones) changes canvas sizes;
  the phone layout below 820 px changes how many cards and rows are on screen; touch changes which events fire (for
  example `pointerover` on finger-down, WP-28). None of this appears in the desktop numbers.
- **Some limits exist only on real devices.** iOS Safari's per-tab memory limit, its decoded-image budget, WebGL
  context loss when the app is backgrounded, and its lack of `ImageDecoder` (the clip viewer's fallback) cannot be
  reproduced in Chromium emulation.

**Assumptions**
- Chromium emulation (390 × 844, device scale 3, touch, 4–6× CPU) is a fair stand-in for a mid-range Android phone's
  layout and main-thread cost, not for its memory or GPU.
- One real iPhone and one real Android phone, checked by hand, are enough to catch crashes and context loss.

## Proposed scope

1. A `--device phone` option in `tools/perf/baseline.mjs`:
   - `Emulation.setDeviceMetricsOverride({width: 390, height: 844, deviceScaleFactor: 3, mobile: true})`;
   - `Emulation.setTouchEmulationEnabled({enabled: true, maxTouchPoints: 5})` and a phone user agent;
   - CPU throttling at 4× and 6×, with the existing Lighthouse mobile network profile;
   - touch scrolling with `Input.synthesizeScrollGesture` instead of `scrollBy`, one screen height per step.
2. Phone scenarios, reusing the existing ones where they apply:
   - cold and repeat loads of the three apps;
   - Action Atlas: scroll the whole grid; bytes, decoded image memory and GPU process CPU while idle;
   - Move Explorer: default view load; touch-scroll 50 table rows (prefetch requests, WP-28); idle cost of each
     viewer kind; the WP-12 memory sequences (Hollow Knight sheet, 10 Super Smash Bros. Ultimate clips, five game
     switches);
   - Trends: scroll the page (long tasks and layout time, WP-32).
3. A short manual checklist for a real iPhone (Safari Web Inspector) and Android phone (Chrome remote debugging):
   open a large Hollow Knight sheet, browse ten Smash clips, background the browser for a minute with the 3D viewer
   on screen and return, scroll the Action Atlas grid. Record crashes, reloads and blank viewers.
4. A report in `docs/reports/mobile-performance-2026-10/baseline.md`, with the raw data beside it.

## Out of scope

- Fixing anything. This package only measures.
- Automated tests on real devices or a device farm.

## Open questions

- Which phones do students and instructors actually use? Without analytics, pick one recent iPhone and one mid-range
  Android phone.
- Is a tablet (iPad wider than 820 px gets the desktop layout) worth its own run?

## Metric

This package produces the metrics; there is no target.

## Done when

- The report lists every measurement above with the commit, browser, device or emulation settings, and the steps to
  repeat it.
- The manual checklist has been run once on each real phone and its results are in the report.
- Each later mobile package can cite its baseline numbers from that report.
