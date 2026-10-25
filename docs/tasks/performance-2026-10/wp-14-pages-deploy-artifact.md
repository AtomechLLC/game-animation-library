# WP-14: Deploy only what the site serves

**Status:** Suggestion · **Priority:** P0 · **Depends on:** none

## User task it protects

All of them indirectly: the public site must keep publishing as the collection grows. It also keeps server-only and
curation files out of the public site.

## Basis

**Observed problem**
- `.github/workflows/static.yml:41-45` uploads the whole checkout (`path: '.'`, "Upload entire repository"), about
  **671 MB**. `frame-data/` alone is 506 MB (clips 229 MB, models 175 MB, sprites 92 MB).
- GitHub Pages limits a published site to **1 GB**. The media keeps growing with each importer, so the site will hit
  that limit.
- The workflow runs on every push to `main` (`static.yml:4-7`) with no `paths` filter, so a README edit re-uploads
  and redeploys everything.
- The artifact publishes files the site never loads: `server.js`, `lib/`, `tools/`, `docs/`, `taxonomy.txt`,
  `gif-screening.json`, `missing-references.json`, and `library.json` (already inlined into `index.html`).

**Assumptions**
- The site needs only: `index.html`, `frame-data.html`, `trends.html`, the shared icons, `gifs/`, and the parts of
  `frame-data/` the pages load. The exact list must be checked against the pages' `fetch` and `import` calls.

## Proposed scope

1. A workflow step that copies the needed files into `_site/` and uploads that folder instead of `.`.
2. A `paths-ignore` filter for files that never affect the site (for example `docs/**`, `**/*.md`, `lib/**`,
   `server.js`, `tools/**`), keeping `workflow_dispatch` for manual runs.
3. A check in the workflow that fails clearly when `_site/` approaches the 1 GB limit.

## Out of scope

- Moving media out of the repository (WP-23).
- Changing what the Node host serves.

## Open questions

- Is any file outside the expected list linked from the site, for example `frame-data/README.md` from a footer? The
  Trends footer links to it on GitHub, not on Pages, but every link should be checked.

## Metric

- Pages artifact size: about 671 MB → the served files only. The saving is modest today (server, tools, docs and
  curation files are small next to the media); the main gain is an explicit list and a tracked distance to 1 GB.
- Workflow runs triggered by documentation-only pushes: every one → none.
- Measured from the workflow's artifact size and run time (WP-12).

## Done when

- The deployed site works for all three apps and every game in Move Explorer (spot check one move per game).
- `server.js`, `lib/` and the curation JSON files return `404` on Pages.
- A push that changes only `docs/` does not start a deployment.
