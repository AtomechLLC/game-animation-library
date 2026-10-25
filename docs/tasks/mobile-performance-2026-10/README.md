# Work packages: mobile performance (suggestions)

Every file in this folder is a **suggestion**. None is an adopted decision until Xelnath or Sungkuk marks it so.
This round looks at the three apps on **phones and tablets**: low memory limits, small GPUs, high pixel density, touch
input, cellular data and battery. The [performance round](../performance-2026-10/README.md) was desktop-first, and its
[baseline](../../reports/performance-2026-10/baseline.md) lists "A phone" under "Not measured". Numbering continues
from it, so a package number always means one package.

## Why mobile performance matters here

Desktop still comes first for design and verification. These packages record what a phone would hit, so the
decision to work on it can be made with evidence. They map to the intended experience in
[`CLAUDE.md`](../../../CLAUDE.md):

- **Find relevant examples:** a student who follows a class link on a phone should see the Action Atlas and Move
  Explorer without a long wait or a large cellular download.
- **Observe deliberately:** stepping through a move on a phone must not reload or crash the tab. On iOS, a tab that
  runs out of memory reloads and loses the learner's place.
- **Use examples in teaching:** instructors may show a move from a tablet; the preview must survive the tablet
  sleeping or switching apps.
- **Compare approaches:** browsing several moves and games in one sitting must stay within a phone's memory.

## Sources

- A read-only audit of the code at commit `352f1f0` (2026-10-25): Move Explorer (`frame-data.html`,
  `frame-data/*.js`), Action Atlas (`template.html`), Trends (`trends.html`) and `tools/perf/baseline.mjs`.
- Sizes measured from the working tree (`ls -l`, `gzip -9`, WebP and GLB headers). Sprite sheet dimensions were read
  from every WebP header under `frame-data/sprites/`.
- The desktop baseline's throttled run (4× CPU, Lighthouse mobile network) on a 1440 × 900 window is the closest
  existing measurement. **No phone, phone emulation or real-device profile exists yet.** Decode memory and frame
  costs on phones are reasoned from the code and file sizes; [WP-25](wp-25-mobile-baseline.md) measures them first.

As in earlier rounds, each package keeps apart the **observed problem**, the **assumptions** and the **proposed
solution**.

## What the layout already does well

These are not problems; packages should not undo them.

- All three apps have `width=device-width, initial-scale=1, viewport-fit=cover` and use safe-area insets.
- Below 820 px wide, each app has a single-column layout. Move Explorer shows a compact sticky dock and hides the
  Moveset Inspector (`frame-data.html:380-412`).
- The Action Atlas and Trends key rows already leave touch drags to native scrolling (`template.html:487`,
  `trends.html:594`), and so does the Move Explorer table scroller (`frame-data.html:924`).
- The 3D viewer caps its pixel ratio at 2 (`frame-data/viewer3d.js:100`) and, since WP-15, renders only when its
  picture changes and while it is on screen (`viewer3d.js:148`).

## Relation to the performance round

Several desktop packages fix mobile problems too. This round does not repeat them; it adds what is specific to phones.

| Desktop package | Mobile relevance | Mobile package that builds on it |
|---|---|---|
| [WP-19](../performance-2026-10/wp-19-viewer-memory.md) bounded memory | On iOS, unbounded memory is a crash, not a slowdown | WP-26, WP-27 |
| [WP-20](../performance-2026-10/wp-20-atlas-card-grid.md) still posters | The biggest cellular saving on the Action Atlas | WP-31 |
| [WP-16](../performance-2026-10/wp-16-move-switch-cost.md) move switch cost | Hover prefetch also fires on touch | WP-28 |
| [WP-18](../performance-2026-10/wp-18-move-explorer-cold-load.md) first-load chain | Throttled first 3D frame: 21.1 s | WP-30 |
| [WP-21](../performance-2026-10/wp-21-trends-data.md) Trends summary data | 5.75 MB of JSON parsed on a phone | WP-32 |
| [WP-24](../performance-2026-10/wp-24-fonts-and-shared-assets.md) fonts | A render-blocking round trip to two other origins on cellular | none (WP-24 as written) |

## Constraints from the project direction

- The Move Explorer 3D viewport is a previewer. Mobile work must not add modelling features to it.
- Desktop stays the primary target. A mobile change must not make desktop slower or change its behaviour.
- Packages that would change data or media files (models, sprite sheets, clips, per-game JSON) list that change as an
  open question. It needs a separate decision.
- Every package claims an improvement only against the WP-25 baseline, with the same measurement.

## Not in this round

Found during the audit, but they are usability work rather than performance:

- Touch camera controls in the 3D viewer: pinch to zoom, two-finger pan, and tap buttons for "Fit to view" and the
  default camera. Today zoom needs a wheel and pan needs Shift or the right button (`frame-data/navigation3d.js:51-96`),
  and `touch-action:none` on the canvas (`frame-data.html:229`) also blocks the browser's own pinch.
- Touch targets under 44 px: the scrubber strip (26 px) and frame-step buttons (30 px).
- Explanations shown only as `title=` tooltips, which touch users never see (Action Atlas badges, Trends statistics),
  and the Trends chart tooltip, which follows `pointermove` only (`trends.html:626`).
- Node host caching and compression: the Node host is not the production host ([WP-13](../performance-2026-10/wp-13-server-caching-compression.md)).

## Status values

`Suggestion` → `Adopted` → `In progress` → `Done`. A package can also be `Parked` or `Rejected`, with a reason.

## Packages

| # | Package | App or area | Priority | Depends on | Status |
|---|---|---|---|---|---|
| 25 | [Measure on a phone first](wp-25-mobile-baseline.md) | All | P0, first | 12 | Suggestion |
| 26 | [Sprite sheets and clips within a phone's memory](wp-26-mobile-image-memory.md) | Move Explorer | P0 | 25, 19 (soft) | Suggestion |
| 27 | [Recover from a lost 3D context](wp-27-webgl-context-loss.md) | Move Explorer | P0 | 25 | Suggestion |
| 28 | [Touch does not trigger prefetch](wp-28-touch-prefetch.md) | Move Explorer | P1 | 25 | Suggestion |
| 29 | [2D and clip viewers sleep when idle](wp-29-2d-viewer-idle.md) | Move Explorer | P1 | 25 | Suggestion |
| 30 | [A lighter first view on phones](wp-30-mobile-first-view.md) | Move Explorer | P1 | 25, 18 (soft) | Suggestion |
| 31 | [Action Atlas grid on phones](wp-31-atlas-grid-mobile.md) | Action Atlas | P0 | 25, 20 | Suggestion |
| 32 | [Smooth scrolling on Trends](wp-32-trends-scroll.md) | Trends | P2 | 25 | Suggestion |

**Suggested order.** WP-25 first. Then the two crash risks, WP-26 and WP-27. Then the cheap changes that change no
data: WP-28 and WP-29. WP-31 goes together with WP-20. WP-30 needs a decision on what a phone loads by default.
WP-32 is small and can wait.

## Template

```
# WP-NN: Title
Status · Priority · Depends on
## User task it protects
## Basis (observed problem / assumptions)
## Proposed scope
## Out of scope
## Open questions
## Metric (baseline → target, how measured)
## Done when
```
