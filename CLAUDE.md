# Game Animation Library

Use this document as enduring product direction for UX design and implementation. It describes intended outcomes; the current implementation and each task's scope must be assessed separately.

## Repository at a glance

`README.md` is the detailed reference; update it when a workflow changes.

- **Apps and their URLs:** Action Atlas (`action-atlas.html`), Move Explorer (`move-explorer.html`) and Trends (`trends.html`), switched from the shared app bar (`shared/appbar.js`). `index.html` (site root) and `frame-data.html` (Move Explorer's old address, still used by `library.json` links and shared links) are committed redirect pages that keep the `#link`.
- **Action Atlas:** `taxonomy.txt` → `build_index.py` → `index.json` → `merge.py` → `library.json`, the committed source of truth (about 340 animations in 21 categories, with references and clips). `build_page.py` renders `template.html` + `library.json` into `action-atlas.html`. `index.json`, `atlas.html`, `todo.json` and `action-atlas.html` are generated and git-ignored.
- **Clips:** `gifs/` holds local clips. Importers: `add_ufd.py` (Smash Ultimate hitboxes), `add_baston.py` (Street Fighter III: 3rd Strike), `tools/er_gifs/` (Elden Ring renders from the 3D viewer, via Playwright + ffmpeg). Curation records: `gif-screening.json`, `gif-blocklist.json` with `blocklist.py` (any pass that adds clips must skip blocked ones), `marks.json`, `missing-references.json`.
- **Move Explorer:** `move-explorer.html` loads `frame-data/games.json` and per-game JSON (Elden Ring, No Rest for the Wicked, Street Fighter III: 3rd Strike), with icons, 3D models and `frame-data/viewer3d.js`. Extractors live in `tools/frame_data/`; see `frame-data/README.md`. Trends (`trends.html`) compares every game from the same files.
- **Hosting:** GitHub Pages builds and publishes the static page on every push to `main` (`.github/workflows/static.yml`). `server.js` + `lib/*.js` (Node 20+, no dependencies) add voting, clip suggestions and uploads, and the `/admin` review page; see `DEPLOY-XCLOUD.md`. `serve_local.py` (or `serve_local.bat`) is a local review server that writes `marks.json`.
- **Design skill:** `.claude/skills/impeccable` (Impeccable) offers `/impeccable critique`, `audit`, `distill` and other design commands, and hooks run its detector after UI edits. Its advice serves the product direction in this file, which wins where they differ.
- **Workflow:** run Python scripts from the repo root. Changes land through branches and pull requests to `main`.

## Product purpose

Help students learn by observing game animations and comparing how different games approach similar actions and design problems. Build a useful library of examples that helps people understand those differences and apply what they learn.

Support instructors in using these examples during classes. Develop interactive references that can replace difficult-to-use recordings and let students and instructors examine the moments relevant to their learning or explanation.

Support the related business goal of introducing interested visitors to Jacopo's Game Feel class. Consider course discovery alongside the library's educational value and welcoming community experience.

## Intended experience

- **Find relevant examples.** Help learners locate examples appropriate to the action or question they are studying.
- **Observe deliberately.** Let learners inspect and revisit meaningful moments at their own pace.
- **Compare approaches.** Help learners understand how different games handle comparable actions, with enough context to make the comparison meaningful.
- **Use examples in teaching.** Make useful references easy to return to and incorporate into explanations, demonstrations, and follow-up study.
- **Contribute confidently.** Make it approachable to suggest better examples, correct classifications, and help improve the collection.

These are desired user outcomes. Specific layouts, controls, media formats, and technologies are design choices to evaluate against them.

## Content and community direction

Continually improve the relevance, clarity, and accuracy of the examples. Replace weak or misleading examples with material better suited to observation, comparison, and teaching.

Xelnath's motivation for the extractors was to obtain better material to replace low-quality placeholder GIFs. Treat extraction and conversion as ways to improve the learning resources; choose their role according to the product need.

Combine deliberate content improvement with contributions from knowledgeable users. Preserve a friendly, approachable atmosphere in which people feel comfortable exploring the material and helping improve it.

## Principles for UX work

- Explain which user task a proposed change supports and how it advances the intended experience.
- Distinguish Xelnath's stated goals, observed usability problems, and proposed solutions. Keep assumptions visible and update them when evidence changes.
- Evaluate design options against learning, observation, comparison, teaching, and contribution needs. Choose a coherent solution appropriate to the requested scope.
- Use current code and behavior to understand constraints while designing toward the product purpose.
- Verify the affected user flow and report the evidence available. Distinguish working functionality from demonstrated improvements in usability or learning.
- The Move Explorer 3D viewport is a previewer, not a modelling tool: simplicity and elegance come first.
- Apply this direction within the active task. Product goals guide decisions; they do not independently authorize additional features or a wider redesign.

## Terminology

- **Frame** refers only to a single unit of animation time. Name other things differently, for example "Fit to view" for the camera action that brings the whole move into view.

## Basis and interpretation

This direction is grounded in Xelnath's project discussion beginning on 20 October 2026 and his follow-up answers shared by Sungkuk Park. His stated aims include student learning through observation and cross-game comparison, classroom use of interactive references, better examples, easy contribution, and discovery of Jacopo's class.

The UX principles translate that intent into working guidance. Suggestions from other contributors and particular interface solutions remain proposals unless adopted for the relevant task.
