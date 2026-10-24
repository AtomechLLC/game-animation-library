# WP-11: Before/after evidence and article

**Status:** Suggestion · **Priority:** Ongoing · **Depends on:** each package that changes the page

## User task and intended outcome

A resource for others. Xelnath: "if you can take screenshots of your before and after, we can create an article
explaining what you did and why as a resource." The article explains each change by the user task it serves.

## Basis

**Done so far**
- The "before" state is commit `e98edb6`: home and Frame Data, first screen and full page. Screenshots are not
  stored in the repository. Shoot "after" with the same settings so the pairs line up: viewport 1920×1080 at
  deviceScaleFactor 2 (3840 px wide), Chrome via Playwright, `index.html` built with `python build_page.py` and
  `frame-data.html` on the default Elden Ring view, network idle plus 5 s before capture.

**Observed gap**
- **No before shots of states.** The before set covers only landing views. The packages change states (search
  results, class view with dock, details sheet, atlas entry with clips) that have no before shot yet.

## Proposed scope

1. Before work starts on each package, capture the missing *before* states it will change. Use the same settings
   and name the files `before/<page>-<state>.png`.
2. After each package, capture the matching `after/` shots, plus the commit hash in the screenshots README table.
3. Maintain an article outline (in this folder or `docs/`). For each change, list:
   - the user task;
   - the problem, with evidence;
   - the change;
   - a before/after pair;
   - what was verified, separating "works" from "measured as easier".
4. Keep the final article in Funsmith club voice, and get Xelnath's approval before publishing.

## Out of scope

- Publishing the article (Xelnath's decision).

## Open questions

- Where will the article be published (Discord, gamedesignskills.com blog, the library itself)?
- Are short screen recordings (GIF/MP4) wanted in addition to stills?

## Done when

- Every adopted package has a before/after pair and an entry in the article outline.
