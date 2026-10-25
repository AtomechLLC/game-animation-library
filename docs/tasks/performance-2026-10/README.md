# Work packages: performance (suggestions)

Every file in this folder is a **suggestion**. None is an adopted decision until Xelnath or Sungkuk marks it so.
This round looks at the project from a **performance** angle: how fast the three apps load and respond, how much
memory and battery they use, and how much the hosting and repository carry. The earlier UX round, with a record of
what was implemented, is archived in [`ux-2026-10/`](../ux-2026-10/README.md). Numbering continues from it, so a
package number always means one package.

## Why performance matters here

Performance is not a goal on its own; it protects the intended experience in [`CLAUDE.md`](../../../CLAUDE.md):

- **Find relevant examples:** the Action Atlas and Move Explorer must open quickly, also on classroom and student
  machines and connections.
- **Observe deliberately:** stepping through moves and frames must feel immediate, or learners stop exploring.
- **Use examples in teaching:** an instructor's laptop on a projector should not run hot or drop frames while a move
  sits paused.
- **Contribute confidently:** voting, proposals and uploads must stay responsive on the Node host.

## Sources

- A read-only audit of the code at commit `e67c341` (2026-10-25): Move Explorer runtime (`frame-data.html` and
  `frame-data/*.js`), the Action Atlas and Trends pages, `server.js` and `lib/*.js`, the Pages workflow, the build
  scripts and the repository.
- Sizes were measured from the working tree (`du`, `gzip -9`, WebP and GLB headers, `git count-objects -vH`).
  **No browser profile has been recorded yet.** Costs such as decode time or frames rendered while paused are
  reasoned from the code; [WP-12](wp-12-performance-baseline.md) measures them before anything changes.

As in the UX round, each package keeps apart the **observed problem** (evidence from code or measurement), the
**assumptions** and the **proposed solution**.

## Constraints from the project direction

- The Move Explorer 3D viewport is a previewer. Performance work must not add features to it.
- Design and verify for desktop first; note mobile effects but do not block on them.
- Packages that would change data or media files (`library.json`, per-game JSON, models, clips, sprite sheets)
  list that change as an open question. It needs a separate decision.
- Every package claims an improvement only against the WP-12 baseline, with the same measurement.

## Status values

`Suggestion` → `Adopted` → `In progress` → `Done`. A package can also be `Parked` or `Rejected`, with a reason.

## Packages

| # | Package | App or area | Priority | Depends on | Status |
|---|---|---|---|---|---|
| 12 | [Measure before changing](wp-12-performance-baseline.md) | All | P0, first | none | Done ([report](../../reports/performance-2026-10/baseline.md)) |
| 13 | [Compress and revalidate on the Node host](wp-13-server-caching-compression.md) | Node host | P0 | 12 | Suggestion |
| 14 | [Deploy only what the site serves](wp-14-pages-deploy-artifact.md) | GitHub Pages | P0 | none | Suggestion |
| 15 | [3D viewer renders only when something changes](wp-15-viewer-render-on-demand.md) | Move Explorer | P0 | 12 | Suggestion |
| 16 | [Fast move stepping](wp-16-move-switch-cost.md) | Move Explorer | P0 | 12 | Suggestion |
| 17 | [Re-render only what changed](wp-17-move-explorer-rendering.md) | Move Explorer | P1 | 12 | Suggestion |
| 18 | [Shorter first-load chain](wp-18-move-explorer-cold-load.md) | Move Explorer | P1 | 12, 13 (soft) | Suggestion |
| 19 | [Bounded memory in the viewers](wp-19-viewer-memory.md) | Move Explorer | P1 | 12 | Suggestion |
| 20 | [Still posters on Action Atlas cards](wp-20-atlas-card-grid.md) | Action Atlas | P0 | 12 | Suggestion |
| 21 | [Trends loads summary data only](wp-21-trends-data.md) | Trends | P2 | 12 | Suggestion |
| 22 | [Keep the Node host responsive](wp-22-server-event-loop.md) | Node host | P1 | 12 | Suggestion |
| 23 | [Repository size and a home for media](wp-23-repository-and-media-hosting.md) | Repository, hosting | P2, needs decision | 14 | Suggestion |
| 24 | [Fonts and shared header assets](wp-24-fonts-and-shared-assets.md) | All | P3 | 12 | Suggestion |

**Suggested order.** WP-12 first. Then the cheap, high-impact packages that change no data: WP-15, WP-16, WP-13,
WP-14. WP-20 has the biggest single byte saving but needs poster images, a new kind of generated asset. WP-23 is a
decision, not an implementation.

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
