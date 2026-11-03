# Work packages: one local server (suggestions)

Every file in this folder is a **suggestion**. None is an adopted decision until Xelnath or Sungkuk marks it so.
This round looks at the two ways the site runs locally, `serve_local.py` and `server.js`, which overlap. Numbering
continues from the [code-sharing round](../code-sharing-2026-10/README.md), so a package number always means one
package.

## Why this matters here

Replacing weak or misleading clips is part of the content direction in [`CLAUDE.md`](../../../CLAUDE.md), and so is
*Contribute confidently*. Today a weak clip can be marked for replacement in two places that do not know about each
other, so what gets followed up depends on which server the owner happened to run.

## Sources

- The comparison table in the [README](../../../README.md#running-a-local-server).
- History: `046f77b` (2026-10-18) added the PHP community backend and `serve_local.py` together; `43e366a` added
  `serve_local.bat`; `32bec09` (2026-10-20) replaced the PHP backend with `server.js`.
- Code on `main` at `48ffc78`: `serve_local.py`, `server.js`, `lib/store.js` (`needs`), `lib/api.js`
  (`action=need`), `lib/admin.js` (the marked list), `template.html` (`CFG.local` and `CFG.marks`, around lines
  221, 431 and 474), `build_page.py` (`render({'local': True, ...})`).

As in earlier rounds, each package keeps apart the **observed problem**, the **assumptions** and the **proposed
solution**.

## Constraints

- **The deployed site behaves the same.** Votes, suggestions, proposals and the `/admin` review stay as they are.
- **No data files.** No package changes `library.json`, per-game JSON, models or media.
- **The Claude replacement workflow keeps working.** "Search for better GIFs for my marks" must still find the marks.
- Desktop first, as for all current work.

## Status values

`Suggestion` → `Adopted` → `In progress` → `Done`. A package can also be `Parked` or `Rejected`, with a reason.

## Packages

| # | Package | App or area | Priority | Depends on | Status |
|---|---|---|---|---|---|
| 38 | [One local server](wp-38-one-local-server.md) | Local tooling, Action Atlas | P2 | none | Suggestion |

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
