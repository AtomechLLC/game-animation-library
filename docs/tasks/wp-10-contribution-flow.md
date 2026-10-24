# WP-10: Approachable contribution flow

**Status:** Suggestion · **Priority:** P3 · **Depends on:** WP-08

## User task and intended outcome

*Contribute confidently.* A knowledgeable visitor can suggest a better clip, upload one, or flag a wrong
classification, knows what happens next, and feels welcome doing it.

## Basis

**Stated goals**
- Xelnath: the page should work as a community space, for example uploading GIFs.
- `CLAUDE.md`: combine deliberate content improvement with contributions in a friendly atmosphere.

**Observed state**
- **The atlas has a submit form.** It offers "Submit a GIF" (`template.html:189`, `:273`) and per-entry
  "Submit a better GIF" (`:334`). File upload and voting appear only when a backend is configured (`CFG.api`,
  `template.html:414-426`).
- **The public build may have no backend.** GitHub Pages builds with an optional `LIBRARY_API_URL` repository
  variable (`.github/workflows/static.yml:35-38`). It is not yet confirmed whether the public page has the backend,
  and therefore uploads and voting.
- **Frame Data has no contribution path.** For example, there is no "this move is misnamed" or "wrong
  classification" action.

## Proposed scope

1. **Audit first.** Confirm which contribution features the public page actually offers today. Record the result
   in this file.
2. Make the contribution entry points visible and consistent on both pages. Say what happens after a submission
   (review by whom, how long, where to follow up: the Discord).
3. Add a lightweight "Report an issue with this move" on Frame Data. It could be a Discord link or a prefilled
   suggestion, depending on the audit.

## Out of scope

- New moderation tooling beyond `/admin` (`server.js`, `lib/*.js`).

## Open questions

- Is the xCloud backend (`DEPLOY-XCLOUD.md`) deployed for the public page?
- Should contributions route to Discord, the form, or both?

## Done when

- The audit result is recorded.
- From any atlas entry and any Elden Ring move, a contributor can find how to suggest a correction in one step.

## Evidence to capture

- The submit flow from start to confirmation, on the public build.
