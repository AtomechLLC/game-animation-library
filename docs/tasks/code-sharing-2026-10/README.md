# Work packages: code shared across the apps (suggestions)

Every file in this folder is a **suggestion**. None is an adopted decision until Xelnath or Sungkuk marks it so.
This round turns the findings of the [duplicated app code report](../../reports/duplicated-app-code.md) into work:
code that each app, or each preview, carries its own copy of. Numbering continues from the
[mobile performance round](../mobile-performance-2026-10/README.md), so a package number always means one package.

## Why this matters here

#76 scoped Left/Right to the focused zone on the Move Explorer ruler. Action Atlas and Trends never got it, because
each app had its own copy of the ruler; #84 fixed that by moving the ruler into `shared/`. The same can happen
anywhere else code is copied. These packages protect the intended experience in [`CLAUDE.md`](../../../CLAUDE.md):

- **Observe deliberately:** the preview controls (play, step a frame, scrub, keys) should behave the same whichever
  game type is on screen.
- **Compare approaches:** two apps should agree about the same move. Today Move Explorer and Trends can compute its
  last active frame differently.
- **Use examples in teaching:** an instructor moving between apps in class should meet the same header, switcher,
  colours and sheet behaviour.

## Sources

- The [duplicated app code report](../../reports/duplicated-app-code.md), measured on `main` at `7310cb2`
  (2026-10-25): identical lines across files, CSS selectors with differing rules, same-named definitions compared.
- Line references in the packages come from that commit.

As in earlier rounds, each package keeps apart the **observed problem**, the **assumptions** and the **proposed
solution**.

## What already works this way

These are the pattern to follow; packages should not undo them.

- `shared/ruler.css` and `shared/ruler.js` (#84): one ruler for all three apps, loaded by relative path with `?v=`.
- `frame-data/speed.js`: one speed menu, imported by all three preview modules.
- `frame-data/navigation3d.js` and `frame-data/renderstats.js`: 3D-only modules kept apart from the viewer.

## Constraints

- **Behaviour stays the same.** A package that moves code changes no behaviour, except where it says so and the
  difference has been decided first (WP-36, WP-37).
- **Shared files are served, not inlined.** Action Atlas is built by `build_page.py` from `template.html`; the other
  two apps are static. A shared file is loaded by relative path so one copy serves all three.
- **New folders need routes.** `server.js` and `serve_local.py` only serve listed paths. `/shared/` already has
  routes and is the default home for anything used by more than one app; `frame-data/` is for Move Explorer only.
- **Cache-busting.** Shared files are cached for an hour; each page links them with `?v=` and the number is bumped on
  every change.
- **No data files.** None of these packages changes `library.json`, per-game JSON, models or media.
- **The 3D viewport stays a previewer.** WP-33 moves controls; it adds none.
- Desktop first, as for all current work.

## Not in this round

- Python tools, importers and the server code (`server.js`, `lib/`): not examined by the report.
- Duplication inside a single app.
- Any visual redesign of the shell, switcher or sheet. These packages make one copy; changing how it looks is a
  separate decision.

## Status values

`Suggestion` → `Adopted` → `In progress` → `Done`. A package can also be `Parked` or `Rejected`, with a reason.

## Packages

| # | Package | App or area | Priority | Depends on | Status |
|---|---|---|---|---|---|
| 33 | [One set of preview controls](wp-33-shared-preview-controls.md) | Move Explorer previews | P1 | none | Suggestion |
| 34 | [One page shell stylesheet](wp-34-shared-shell-styles.md) | All | P1 | none | Suggestion |
| 35 | [One app switcher](wp-35-shared-app-switcher.md) | All | P2 | 34 (soft) | Suggestion |
| 36 | [One filter rail and detail sheet](wp-36-shared-rail-and-sheet.md) | Action Atlas, Move Explorer | P2 | 34 (soft) | Suggestion |
| 37 | [Shared helpers and one meaning for frame data](wp-37-shared-helpers-frame-data.md) | All | P1 | none | Suggestion |

**Suggested order.** WP-37's `lastActive` decision first: it is the one place where two apps already disagree, and it
is small. Then WP-33, the controls students use most to observe moves. WP-34 next, then WP-35 on top of it. WP-36
needs decisions about which differences are deliberate and can wait for them.

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
